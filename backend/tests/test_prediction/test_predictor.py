"""WinningBidPredictor 단위 테스트 (Phase 8-3)

mock 모델로 추론 파이프라인 검증.
DB 불필요.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.prediction.config import PredictionConfig
from app.services.prediction.predictor import PredictionResult, WinningBidPredictor


# ──────────────────────────────────────
# Fixtures
# ──────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singleton():
    """매 테스트마다 싱글턴 초기화"""
    WinningBidPredictor.reset_instance()
    yield
    WinningBidPredictor.reset_instance()


def _base_kwargs() -> dict:
    """공통 추론 인자"""
    return {
        "appraised_value": 500_000_000,
        "minimum_bid": 350_000_000,
        "fail_count": 2,
        "property_type": "아파트",
        "court_office_code": "B000210",
        "address": "서울특별시 강남구 역삼동 123-4",
        "rolling_avg": 0.72,
        "rolling_count": 15,
    }


# ──────────────────────────────────────
# rule_v1 fallback 테스트
# ──────────────────────────────────────


class TestRuleV1Fallback:
    def test_fallback_when_no_model(self):
        """모델 파일 없으면 rule_v1 fallback"""
        predictor = WinningBidPredictor(PredictionConfig())
        assert predictor.model is None
        assert predictor.model_version == "rule_v1"

    def test_fallback_returns_result(self):
        """rule_v1 fallback 결과 구조 검증"""
        predictor = WinningBidPredictor(PredictionConfig())
        result = predictor.predict(**_base_kwargs())

        assert isinstance(result, PredictionResult)
        assert result.model_version == "rule_v1"
        assert result.fallback_reason is not None
        assert 0 < result.predicted_ratio < 1.5
        assert result.predicted_price > 0
        assert result.confidence == "low"
        # top_factors: dict 형식
        assert len(result.top_factors) == 2
        assert all("feature" in f and "importance" in f for f in result.top_factors)
        assert any("유찰" in f["feature"] for f in result.top_factors)

    def test_fallback_property_type_mapping(self):
        """rule_v1: 물건유형별 다른 예측값"""
        predictor = WinningBidPredictor(PredictionConfig())

        kwargs_apt = _base_kwargs()
        kwargs_apt["property_type"] = "아파트"
        kwargs_apt["fail_count"] = 1

        kwargs_land = _base_kwargs()
        kwargs_land["property_type"] = "전답"
        kwargs_land["fail_count"] = 1

        apt_result = predictor.predict(**kwargs_apt)
        land_result = predictor.predict(**kwargs_land)

        # 아파트와 토지의 예측값은 다를 수 있음
        assert apt_result.predicted_ratio != land_result.predicted_ratio


# ──────────────────────────────────────
# ML 추론 테스트 (mock 모델)
# ──────────────────────────────────────


class TestMLPredict:
    def _make_predictor_with_mock_model(self) -> WinningBidPredictor:
        """mock CatBoost 모델이 장착된 predictor 생성"""
        config = PredictionConfig()
        predictor = WinningBidPredictor(config)

        # mock 모델 주입
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.75])
        predictor.model = mock_model
        predictor.model_version = "ml_v1"
        predictor.feature_importances = {
            "discount_rate": 67.5,
            "fail_count": 15.3,
            "property_type_merged": 5.0,
        }
        return predictor

    def test_ml_predict_returns_result(self):
        """ML 예측 결과 구조 검증"""
        predictor = self._make_predictor_with_mock_model()
        result = predictor.predict(**_base_kwargs())

        assert isinstance(result, PredictionResult)
        assert result.model_version == "ml_v1"
        assert result.fallback_reason is None
        assert result.predicted_ratio == 0.75
        assert result.predicted_price == int(0.75 * 500_000_000)

    def test_ml_predict_top_factors(self):
        """ML: 상위 영향 피처 한국어 변환 + 값 포함"""
        predictor = self._make_predictor_with_mock_model()
        result = predictor.predict(**_base_kwargs())

        assert len(result.top_factors) == 3
        # dict 형식: {"feature": "할인율 70%", "importance": 67.5}
        assert all("feature" in f and "importance" in f for f in result.top_factors)
        features = [f["feature"] for f in result.top_factors]
        assert any("할인율" in f for f in features)
        assert any("유찰" in f for f in features)

    def test_ml_predict_clamp(self):
        """ML: 예측값 클램프 (0 ~ TARGET_MAX)"""
        predictor = self._make_predictor_with_mock_model()
        predictor.model.predict.return_value = np.array([2.5])

        result = predictor.predict(**_base_kwargs())
        assert result.predicted_ratio == 1.5  # TARGET_MAX

    def test_ml_predict_negative_clamp(self):
        """ML: 음수 예측값 → 0으로 클램프"""
        predictor = self._make_predictor_with_mock_model()
        predictor.model.predict.return_value = np.array([-0.1])

        result = predictor.predict(**_base_kwargs())
        assert result.predicted_ratio == 0.0


# ──────────────────────────────────────
# 신뢰도 판단 테스트
# ──────────────────────────────────────


class TestConfidence:
    def test_high_confidence(self):
        """유찰 1회 + rolling 15건 → high"""
        predictor = WinningBidPredictor(PredictionConfig())
        conf = predictor._assess_confidence(
            fail_count=1, rolling_count=15, discount_rate=0.7,
        )
        assert conf == "high"

    def test_medium_confidence_few_data(self):
        """유찰 1회 + rolling 3건 → medium"""
        predictor = WinningBidPredictor(PredictionConfig())
        conf = predictor._assess_confidence(
            fail_count=1, rolling_count=3, discount_rate=0.7,
        )
        assert conf == "medium"

    def test_low_confidence_many_failures(self):
        """유찰 5회 → low"""
        predictor = WinningBidPredictor(PredictionConfig())
        conf = predictor._assess_confidence(
            fail_count=5, rolling_count=20, discount_rate=0.5,
        )
        assert conf == "low"

    def test_low_confidence_extreme_discount(self):
        """극단 할인율 → low"""
        predictor = WinningBidPredictor(PredictionConfig())
        conf = predictor._assess_confidence(
            fail_count=1, rolling_count=20, discount_rate=0.15,
        )
        assert conf == "low"


# ──────────────────────────────────────
# 싱글턴 테스트
# ──────────────────────────────────────


class TestSingleton:
    def test_singleton_same_instance(self):
        """get_instance는 동일 객체 반환"""
        a = WinningBidPredictor.get_instance()
        b = WinningBidPredictor.get_instance()
        assert a is b

    def test_singleton_reset(self):
        """reset 후 새 인스턴스"""
        a = WinningBidPredictor.get_instance()
        WinningBidPredictor.reset_instance()
        b = WinningBidPredictor.get_instance()
        assert a is not b
