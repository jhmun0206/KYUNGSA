"""PredictionTrainer 단위 테스트 (Phase 8-2)

mock DataFrame으로 CatBoost 학습/CV/저장/로드 검증.
DB 불필요.
"""

import json

import numpy as np
import pandas as pd
import pytest

from app.services.prediction.config import PredictionConfig
from app.services.prediction.trainer import PredictionTrainer


# ──────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────


def _make_training_data(n: int = 300) -> pd.DataFrame:
    """테스트용 mock 학습 데이터 생성"""
    rng = np.random.RandomState(42)
    return pd.DataFrame({
        "fail_count": rng.randint(0, 6, n),
        "appraised_value_log": rng.uniform(18, 22, n),
        "discount_rate": rng.uniform(0.3, 1.0, n),
        "tenant_count": rng.randint(0, 3, n),
        "total_deposit_ratio": rng.uniform(0, 0.5, n),
        "quarter": rng.randint(1, 5, n),
        "year_month": rng.randint(202201, 202612, n),
        "rolling_avg_3m": rng.uniform(0.5, 0.9, n),
        "rolling_count_3m": rng.randint(0, 20, n),
        "property_type_merged": rng.choice(
            ["아파트", "다세대연립", "오피스텔", "토지"], n,
        ),
        "court_office_code": rng.choice(["B000210", "B000213", "B000214"], n),
        "sido": rng.choice(["서울특별시", "경기도", "인천광역시"], n),
        "sgg": rng.choice(["강남구", "수원시", "부평구"], n),
        "target": rng.uniform(0.3, 1.2, n),
        "winning_date": pd.date_range("2022-01-01", periods=n, freq="D"),
    })


def _fast_config() -> PredictionConfig:
    """테스트용 빠른 설정"""
    config = PredictionConfig()
    config.CATBOOST_PARAMS = config.CATBOOST_PARAMS.copy()
    config.CATBOOST_PARAMS["iterations"] = 50
    config.CATBOOST_PARAMS["verbose"] = 0
    return config


# ──────────────────────────────────────
# 학습 기본 테스트
# ──────────────────────────────────────


class TestTrainBasic:
    def test_train_returns_model(self):
        """기본 학습 → 모델 반환"""
        df = _make_training_data(300)
        trainer = PredictionTrainer(_fast_config())
        model = trainer.train(df)

        assert model is not None
        assert trainer.feature_importances is not None
        assert len(trainer.feature_importances) == len(
            trainer.config.NUMERIC_FEATURES + trainer.config.CATEGORICAL_FEATURES,
        )

    def test_train_predict(self):
        """학습 후 예측 동작"""
        df = _make_training_data(300)
        trainer = PredictionTrainer(_fast_config())
        trainer.train(df)

        features = trainer.config.NUMERIC_FEATURES + trainer.config.CATEGORICAL_FEATURES
        X_test = df[features].iloc[:5].copy()
        for col in trainer.config.CATEGORICAL_FEATURES:
            X_test[col] = X_test[col].astype(str)

        preds = trainer.model.predict(X_test)
        assert len(preds) == 5
        assert all(isinstance(p, (float, np.floating)) for p in preds)

    def test_feature_importances_sum(self):
        """피처 중요도 합계 ≈ 100"""
        df = _make_training_data(200)
        trainer = PredictionTrainer(_fast_config())
        trainer.train(df)

        total_imp = sum(trainer.feature_importances.values())
        assert abs(total_imp - 100.0) < 1.0


# ──────────────────────────────────────
# 교차검증 테스트
# ──────────────────────────────────────


class TestCrossValidate:
    def test_cv_returns_folds(self):
        """TimeSeriesSplit CV → fold 개수 맞음"""
        df = _make_training_data(500)
        config = _fast_config()
        config.CV_N_SPLITS = 3

        trainer = PredictionTrainer(config)
        results = trainer.cross_validate(df)

        assert len(results) == 3
        assert all("mape" in r for r in results)
        assert all("mae" in r for r in results)
        assert all("rmse" in r for r in results)

    def test_cv_metrics_positive(self):
        """CV 메트릭 값이 양수"""
        df = _make_training_data(500)
        config = _fast_config()
        config.CV_N_SPLITS = 3

        trainer = PredictionTrainer(config)
        results = trainer.cross_validate(df)

        assert all(r["mape"] > 0 for r in results)
        assert all(r["n_train"] > 0 for r in results)
        assert all(r["n_val"] > 0 for r in results)

    def test_cv_train_size_increasing(self):
        """TimeSeriesSplit: 학습 데이터가 fold마다 증가"""
        df = _make_training_data(500)
        config = _fast_config()
        config.CV_N_SPLITS = 3

        trainer = PredictionTrainer(config)
        results = trainer.cross_validate(df)

        train_sizes = [r["n_train"] for r in results]
        assert train_sizes == sorted(train_sizes)


# ──────────────────────────────────────
# 저장/로드 테스트
# ──────────────────────────────────────


class TestSaveLoad:
    def test_save_creates_files(self, tmp_path):
        """모델 + 메타데이터 파일 생성"""
        df = _make_training_data(200)
        config = _fast_config()
        config.MODEL_DIR = str(tmp_path)

        trainer = PredictionTrainer(config)
        trainer.train(df)
        model_path = trainer.save_model(tag="test")

        assert model_path.exists()
        assert (tmp_path / "metadata_test.json").exists()

    def test_metadata_content(self, tmp_path):
        """메타데이터 JSON 구조 검증"""
        df = _make_training_data(200)
        config = _fast_config()
        config.MODEL_DIR = str(tmp_path)

        trainer = PredictionTrainer(config)
        trainer.train(df)
        trainer.save_model(tag="test")

        meta_path = tmp_path / "metadata_test.json"
        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["tag"] == "test"
        assert "created_at" in meta
        assert "feature_importances" in meta
        assert "config" in meta
        assert "score_features_note" in meta

    def test_load_and_predict(self, tmp_path):
        """저장 → 로드 → 예측"""
        df = _make_training_data(200)
        config = _fast_config()
        config.MODEL_DIR = str(tmp_path)

        trainer = PredictionTrainer(config)
        trainer.train(df)
        model_path = trainer.save_model(tag="test")

        loaded = PredictionTrainer.load_model(model_path)
        features = config.NUMERIC_FEATURES + config.CATEGORICAL_FEATURES
        X = df[features].iloc[:3].copy()
        for col in config.CATEGORICAL_FEATURES:
            X[col] = X[col].astype(str)

        preds = loaded.predict(X)
        assert len(preds) == 3

    def test_save_without_train_raises(self):
        """학습 없이 저장 시도 → ValueError"""
        trainer = PredictionTrainer(_fast_config())
        with pytest.raises(ValueError, match="학습되지 않았습니다"):
            trainer.save_model()


# ──────────────────────────────────────
# Config 검증
# ──────────────────────────────────────


class TestConfigValidation:
    def test_score_features_excluded(self):
        """현 시점에서 점수 피처는 NUMERIC_FEATURES에 미포함"""
        config = PredictionConfig()
        assert "legal_score" not in config.NUMERIC_FEATURES
        assert "location_score" not in config.NUMERIC_FEATURES
        assert "occupancy_score" not in config.NUMERIC_FEATURES
        assert "total_score" not in config.NUMERIC_FEATURES
        assert "price_score" not in config.NUMERIC_FEATURES

    def test_year_month_included(self):
        """year_month 피처 포함 확인"""
        config = PredictionConfig()
        assert "year_month" in config.NUMERIC_FEATURES
