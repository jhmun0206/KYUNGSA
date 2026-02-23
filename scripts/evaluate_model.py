"""모델 평가 + 기존 룩업 테이블 비교

ML 모델과 naive baseline(유형×유찰 평균)을 비교하여 개선도를 측정한다.

사용법:
    # 서버
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/evaluate_model.py
    PYTHONPATH=backend .venv/bin/python scripts/evaluate_model.py --model models/prediction/model_v1.cbm

    # Mac
    PYTHONPATH=backend python scripts/evaluate_model.py --model models/prediction/model_v1.cbm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
)

from app.database import SessionLocal  # noqa: E402
from app.services.prediction.config import PredictionConfig  # noqa: E402
from app.services.prediction.data_pipeline import PredictionDataPipeline  # noqa: E402
from app.services.prediction.feature_engineer import FeatureEngineer  # noqa: E402
from app.services.prediction.trainer import PredictionTrainer  # noqa: E402


def _header(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def naive_baseline_predict(df: pd.DataFrame) -> pd.Series:
    """Naive baseline: 동일 유형×유찰횟수의 전체 데이터 평균

    ML이 이겨야 할 최소 기준선 (LOO 아니므로 약간 낙관적).
    """
    group_means = df.groupby(["property_type_merged", "fail_count"])["target"].mean()

    def _lookup(row: pd.Series) -> float:
        key = (row["property_type_merged"], row["fail_count"])
        if key in group_means.index:
            return group_means[key]
        return df["target"].mean()

    return df.apply(_lookup, axis=1)


def run_evaluation(model_path: str | None = None) -> None:
    config = PredictionConfig()

    # 1. 데이터 추출 + 피처 엔지니어링
    _header("1. 데이터 준비")
    db = SessionLocal()
    try:
        pipeline = PredictionDataPipeline(db)
        raw_df = pipeline.extract_training_data()
    finally:
        db.close()

    if raw_df.empty:
        print("  데이터 없음. 종료.")
        return

    fe = FeatureEngineer(config)
    df = fe.transform(raw_df)
    print(f"  전체: {len(df):,}건")

    # 시간순 80/20 분할 (학습과 동일)
    split_idx = int(len(df) * 0.8)
    df_train = df.iloc[:split_idx]
    df_test = df.iloc[split_idx:]
    print(f"  학습: {len(df_train):,}건, 테스트: {len(df_test):,}건")

    features = config.NUMERIC_FEATURES + config.CATEGORICAL_FEATURES

    # 2. ML 모델 예측
    _header("2. ML 모델 예측")
    if model_path:
        model = PredictionTrainer.load_model(model_path)
        print(f"  모델: {model_path}")
    else:
        # 모델 파일 없으면 즉석 학습
        print("  모델 파일 미지정 → 즉석 학습")
        trainer = PredictionTrainer(config)
        model = trainer.train(df)

    X_test = df_test[features].copy()
    for col in config.CATEGORICAL_FEATURES:
        X_test[col] = X_test[col].astype(str)

    ml_preds = model.predict(X_test)
    y_test = df_test["target"].values

    # 3. Baseline 예측 (전체 데이터 평균 — 약간 낙관적이지만 공정 비교)
    baseline_preds = naive_baseline_predict(df_test)

    # 4. 전체 비교
    _header("3. ML vs Baseline 전체 비교")
    ml_mape = mean_absolute_percentage_error(y_test, ml_preds)
    ml_mae = mean_absolute_error(y_test, ml_preds)
    ml_rmse = float(np.sqrt(mean_squared_error(y_test, ml_preds)))

    bl_mape = mean_absolute_percentage_error(y_test, baseline_preds)
    bl_mae = mean_absolute_error(y_test, baseline_preds)
    bl_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_preds)))

    print(f"  {'지표':<10} {'Baseline':>12} {'CatBoost ML':>14} {'개선':>10}")
    print(f"  {'-' * 10} {'-' * 12} {'-' * 14} {'-' * 10}")
    print(f"  {'MAPE':<10} {_pct(bl_mape):>12} {_pct(ml_mape):>14} "
          f"{_pct(bl_mape - ml_mape):>10}")
    print(f"  {'MAE':<10} {bl_mae:>12.4f} {ml_mae:>14.4f} "
          f"{bl_mae - ml_mae:>10.4f}")
    print(f"  {'RMSE':<10} {bl_rmse:>12.4f} {ml_rmse:>14.4f} "
          f"{bl_rmse - ml_rmse:>10.4f}")

    # 5. 물건유형별 MAPE 비교
    _header("4. 물건유형별 MAPE 비교")
    df_eval = df_test.copy()
    df_eval["ml_pred"] = ml_preds
    df_eval["bl_pred"] = baseline_preds.values

    print(f"  {'유형':<12} {'건수':>6} {'Baseline':>10} {'ML':>10} {'개선':>8}")
    print(f"  {'-' * 12} {'-' * 6} {'-' * 10} {'-' * 10} {'-' * 8}")

    for ptype in df_eval["property_type_merged"].unique():
        mask = df_eval["property_type_merged"] == ptype
        subset = df_eval[mask]
        if len(subset) < 5:
            continue
        y_sub = subset["target"]
        bl_sub = mean_absolute_percentage_error(y_sub, subset["bl_pred"])
        ml_sub = mean_absolute_percentage_error(y_sub, subset["ml_pred"])
        print(f"  {ptype:<12} {len(subset):>6} {_pct(bl_sub):>10} "
              f"{_pct(ml_sub):>10} {_pct(bl_sub - ml_sub):>8}")

    # 6. 유찰횟수별 MAPE 비교
    _header("5. 유찰횟수별 MAPE 비교")
    print(f"  {'유찰':>4} {'건수':>6} {'Baseline':>10} {'ML':>10} {'개선':>8}")
    print(f"  {'-' * 4} {'-' * 6} {'-' * 10} {'-' * 10} {'-' * 8}")

    for fc in sorted(df_eval["fail_count"].unique()):
        mask = df_eval["fail_count"] == fc
        subset = df_eval[mask]
        if len(subset) < 5:
            continue
        y_sub = subset["target"]
        bl_sub = mean_absolute_percentage_error(y_sub, subset["bl_pred"])
        ml_sub = mean_absolute_percentage_error(y_sub, subset["ml_pred"])
        print(f"  {fc:>4} {len(subset):>6} {_pct(bl_sub):>10} "
              f"{_pct(ml_sub):>10} {_pct(bl_sub - ml_sub):>8}")

    # 7. discount_rate 제외 실험
    _header("6. discount_rate 제외 실험")
    config_no_dr = PredictionConfig()
    config_no_dr.NUMERIC_FEATURES = [
        f for f in config_no_dr.NUMERIC_FEATURES if f != "discount_rate"
    ]
    config_no_dr.CATBOOST_PARAMS = config_no_dr.CATBOOST_PARAMS.copy()
    config_no_dr.CATBOOST_PARAMS["verbose"] = 0

    trainer_no_dr = PredictionTrainer(config_no_dr)
    trainer_no_dr.train(df)

    features_no_dr = config_no_dr.NUMERIC_FEATURES + config_no_dr.CATEGORICAL_FEATURES
    X_test_no_dr = df_test[features_no_dr].copy()
    for col in config_no_dr.CATEGORICAL_FEATURES:
        X_test_no_dr[col] = X_test_no_dr[col].astype(str)

    preds_no_dr = trainer_no_dr.model.predict(X_test_no_dr)
    mape_no_dr = mean_absolute_percentage_error(y_test, preds_no_dr)

    print(f"  discount_rate 포함: MAPE={_pct(ml_mape)}")
    print(f"  discount_rate 제외: MAPE={_pct(mape_no_dr)} "
          f"(+{_pct(mape_no_dr - ml_mape)} 악화)")

    print(f"\n{'═' * 60}")
    print(f"  평가 완료")
    print(f"{'═' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(description="모델 평가 + baseline 비교")
    parser.add_argument("--model", type=str, default=None, help="모델 파일 경로 (.cbm)")
    args = parser.parse_args()
    run_evaluation(model_path=args.model)


if __name__ == "__main__":
    main()
