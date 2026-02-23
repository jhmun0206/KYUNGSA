"""CatBoost 낙찰가율 예측 모델 학습기 (Private)

학습, 교차검증, 모델 저장/로드를 담당한다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit

from app.services.prediction.config import PredictionConfig

logger = logging.getLogger(__name__)


class PredictionTrainer:
    """CatBoost 낙찰가율 예측 모델 학습기"""

    def __init__(self, config: PredictionConfig | None = None) -> None:
        self.config = config or PredictionConfig()
        self.model: CatBoostRegressor | None = None
        self.feature_importances: dict[str, float] | None = None
        self.cv_results: list[dict] | None = None

    def train(self, df: pd.DataFrame) -> CatBoostRegressor:
        """전체 데이터로 최종 모델 학습

        시간순 80/20 분할 (마지막 20% = validation, early stopping).

        Returns:
            학습된 CatBoostRegressor
        """
        features = self.config.NUMERIC_FEATURES + self.config.CATEGORICAL_FEATURES
        X = df[features].copy()
        y = df[self.config.TARGET].copy()

        for col in self.config.CATEGORICAL_FEATURES:
            X[col] = X[col].astype(str)

        # 시간순 분할 (df는 winning_date ASC 정렬 상태)
        split_idx = int(len(df) * 0.8)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        cat_indices = [
            features.index(f) for f in self.config.CATEGORICAL_FEATURES
        ]

        train_pool = Pool(X_train, y_train, cat_features=cat_indices)
        val_pool = Pool(X_val, y_val, cat_features=cat_indices)

        self.model = CatBoostRegressor(**self.config.CATBOOST_PARAMS)
        self.model.fit(
            train_pool,
            eval_set=val_pool,
            use_best_model=True,
        )

        # 피처 중요도
        self.feature_importances = dict(
            zip(features, self.model.get_feature_importance()),
        )

        return self.model

    def cross_validate(self, df: pd.DataFrame) -> list[dict]:
        """TimeSeriesSplit 교차검증

        df는 winning_date ASC 정렬 상태여야 함.
        각 fold: 이전 데이터로 학습 → 다음 데이터로 검증.

        Returns:
            fold별 MAPE/MAE/RMSE 리스트
        """
        features = self.config.NUMERIC_FEATURES + self.config.CATEGORICAL_FEATURES
        X = df[features].copy()
        y = df[self.config.TARGET].copy()

        for col in self.config.CATEGORICAL_FEATURES:
            X[col] = X[col].astype(str)

        cat_indices = [
            features.index(f) for f in self.config.CATEGORICAL_FEATURES
        ]

        tscv = TimeSeriesSplit(n_splits=self.config.CV_N_SPLITS)
        results = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
            X_tr, X_vl = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_vl = y.iloc[train_idx], y.iloc[val_idx]

            train_pool = Pool(X_tr, y_tr, cat_features=cat_indices)
            val_pool = Pool(X_vl, y_vl, cat_features=cat_indices)

            params = self.config.CATBOOST_PARAMS.copy()
            model = CatBoostRegressor(**params)
            model.fit(
                train_pool, eval_set=val_pool,
                use_best_model=True, verbose=0,
            )

            preds = model.predict(X_vl)

            mape = mean_absolute_percentage_error(y_vl, preds)
            mae = mean_absolute_error(y_vl, preds)
            rmse = float(np.sqrt(mean_squared_error(y_vl, preds)))

            # 검증 기간
            val_period = ""
            date_col = "winning_date" if "winning_date" in df.columns else None
            if date_col:
                val_dates = pd.to_datetime(
                    df.iloc[val_idx][date_col], errors="coerce",
                ).dropna()
                if len(val_dates) > 0:
                    val_period = f"{val_dates.min():%Y-%m} ~ {val_dates.max():%Y-%m}"

            results.append({
                "fold": fold,
                "mape": round(mape, 4),
                "mae": round(mae, 4),
                "rmse": round(rmse, 4),
                "n_train": len(train_idx),
                "n_val": len(val_idx),
                "val_period": val_period,
            })

        self.cv_results = results
        return results

    def save_model(self, tag: str | None = None) -> Path:
        """모델 + 메타데이터 저장

        파일: models/prediction/model_{tag}.cbm + metadata_{tag}.json
        """
        if self.model is None:
            raise ValueError("모델이 학습되지 않았습니다.")

        tag = tag or datetime.now().strftime("%Y%m%d")
        model_dir = Path(self.config.MODEL_DIR)
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / f"model_{tag}.cbm"
        meta_path = model_dir / f"metadata_{tag}.json"

        self.model.save_model(str(model_path))

        metadata = {
            "tag": tag,
            "created_at": datetime.now().isoformat(),
            "cv_results": self.cv_results,
            "feature_importances": self.feature_importances,
            "config": {
                "numeric_features": self.config.NUMERIC_FEATURES,
                "categorical_features": self.config.CATEGORICAL_FEATURES,
                "catboost_params": {
                    k: v for k, v in self.config.CATBOOST_PARAMS.items()
                    if k != "cat_features"
                },
            },
            "score_features_note": (
                "점수 피처(legal/price/location/occupancy/total)는 "
                "낙찰 데이터에 점수가 충분히 쌓이기 전이므로 제외. "
                "재추가 기준: 해당 점수 보유 낙찰 건수 500건 이상."
            ),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info("모델 저장: %s", model_path)
        return model_path

    @staticmethod
    def load_model(model_path: str | Path) -> CatBoostRegressor:
        """저장된 모델 로드"""
        model = CatBoostRegressor()
        model.load_model(str(model_path))
        return model
