"""ML 낙찰가율 추론 서비스 (Private)

싱글턴 패턴으로 모델을 메모리에 유지하며 추론을 제공한다.
모델 파일이 없으면 기존 룩업 테이블(rule_v1)로 fallback.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from app.services.prediction.config import PROPERTY_TYPE_MAP, PredictionConfig

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """단건 추론 결과"""

    predicted_ratio: float          # 예측 낙찰가율 (0~1.5)
    predicted_price: int            # 예측 낙찰가 (원)
    confidence: str                 # "high" | "medium" | "low"
    model_version: str              # "ml_v1" | "rule_v1"
    top_factors: list[str]          # 상위 영향 피처 (최대 3개)
    fallback_reason: str | None     # fallback 사유 (ML 사용 시 None)


class WinningBidPredictor:
    """낙찰가율 예측 싱글턴

    Usage:
        predictor = WinningBidPredictor.get_instance()
        result = predictor.predict(
            appraised_value=500_000_000,
            minimum_bid=350_000_000,
            fail_count=2,
            property_type="아파트",
            court_office_code="B000210",
            address="서울특별시 강남구 역삼동",
            rolling_avg=0.72,
            rolling_count=15,
        )
    """

    _instance: WinningBidPredictor | None = None

    def __init__(self, config: PredictionConfig | None = None) -> None:
        self.config = config or PredictionConfig()
        self.model: CatBoostRegressor | None = None
        self.model_version: str = "rule_v1"
        self.feature_importances: dict[str, float] = {}
        self._load_model()

    @classmethod
    def get_instance(cls, config: PredictionConfig | None = None) -> WinningBidPredictor:
        """싱글턴 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """싱글턴 초기화 (테스트/재학습 후 리로드용)"""
        cls._instance = None

    def _load_model(self) -> None:
        """모델 파일 로드 시도 → 실패 시 fallback"""
        model_dir = Path(self.config.MODEL_DIR)
        model_path = model_dir / "model_v1.cbm"
        meta_path = model_dir / "metadata_v1.json"

        if not model_path.exists():
            logger.info("모델 파일 없음 (%s) → rule_v1 fallback", model_path)
            return

        try:
            self.model = CatBoostRegressor()
            self.model.load_model(str(model_path))
            self.model_version = "ml_v1"

            # 메타데이터에서 피처 중요도 로드
            if meta_path.exists():
                import json
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                self.feature_importances = meta.get("feature_importances", {})

            logger.info("ML 모델 로드 완료: %s", model_path)
        except Exception:
            logger.exception("모델 로드 실패 → rule_v1 fallback")
            self.model = None
            self.model_version = "rule_v1"

    def predict(
        self,
        *,
        appraised_value: int,
        minimum_bid: int,
        fail_count: int,
        property_type: str,
        court_office_code: str,
        address: str,
        rolling_avg: float | None = None,
        rolling_count: int | None = None,
        tenant_count: int = 0,
        total_deposit: int = 0,
    ) -> PredictionResult:
        """단건 추론

        ML 모델이 로드되었으면 ML 예측, 아니면 룩업 테이블 fallback.
        """
        if self.model is None:
            return self._predict_rule_v1(
                appraised_value=appraised_value,
                minimum_bid=minimum_bid,
                fail_count=fail_count,
                property_type=property_type,
            )

        return self._predict_ml(
            appraised_value=appraised_value,
            minimum_bid=minimum_bid,
            fail_count=fail_count,
            property_type=property_type,
            court_office_code=court_office_code,
            address=address,
            rolling_avg=rolling_avg,
            rolling_count=rolling_count,
            tenant_count=tenant_count,
            total_deposit=total_deposit,
        )

    def _predict_ml(
        self,
        *,
        appraised_value: int,
        minimum_bid: int,
        fail_count: int,
        property_type: str,
        court_office_code: str,
        address: str,
        rolling_avg: float | None,
        rolling_count: int | None,
        tenant_count: int,
        total_deposit: int,
    ) -> PredictionResult:
        """CatBoost ML 추론"""
        from datetime import datetime

        now = datetime.now()

        # 피처 구성
        discount_rate = (
            minimum_bid / appraised_value if appraised_value > 0 else 0.0
        )
        appraised_value_log = float(np.log1p(appraised_value))

        # 주소 파싱
        addr_parts = (address or "").strip().split()
        sido = addr_parts[0] if addr_parts else "미상"
        sgg = addr_parts[1] if len(addr_parts) > 1 else "미상"

        # 물건유형 병합
        property_type_merged = PROPERTY_TYPE_MAP.get(property_type, "기타")

        # 보증금 비율
        total_deposit_ratio = min(
            total_deposit / appraised_value if appraised_value > 0 else 0.0,
            5.0,
        )

        features = {
            "fail_count": fail_count,
            "appraised_value_log": appraised_value_log,
            "discount_rate": discount_rate,
            "tenant_count": tenant_count,
            "total_deposit_ratio": total_deposit_ratio,
            "quarter": now.quarter if hasattr(now, "quarter") else (now.month - 1) // 3 + 1,
            "year_month": now.year * 100 + now.month,
            "rolling_avg_3m": rolling_avg if rolling_avg is not None else discount_rate,
            "rolling_count_3m": rolling_count if rolling_count is not None else 0,
            "property_type_merged": property_type_merged,
            "court_office_code": court_office_code,
            "sido": sido,
            "sgg": sgg,
        }

        # DataFrame 구성 (피처 순서 맞춤)
        feature_names = self.config.NUMERIC_FEATURES + self.config.CATEGORICAL_FEATURES
        row = {k: features.get(k, 0) for k in feature_names}
        df = pd.DataFrame([row])

        for col in self.config.CATEGORICAL_FEATURES:
            df[col] = df[col].astype(str)

        # 예측
        pred = float(self.model.predict(df)[0])
        pred = max(0.0, min(pred, self.config.TARGET_MAX))  # 클램프

        predicted_price = int(pred * appraised_value)

        # 신뢰도 판단
        confidence = self._assess_confidence(
            fail_count=fail_count,
            rolling_count=rolling_count,
            discount_rate=discount_rate,
        )

        # 상위 영향 피처 (중요도 기준)
        top_factors = self._get_top_factors(features)

        return PredictionResult(
            predicted_ratio=round(pred, 4),
            predicted_price=predicted_price,
            confidence=confidence,
            model_version=self.model_version,
            top_factors=top_factors,
            fallback_reason=None,
        )

    def _predict_rule_v1(
        self,
        *,
        appraised_value: int,
        minimum_bid: int,
        fail_count: int,
        property_type: str,
    ) -> PredictionResult:
        """기존 룩업 테이블 fallback"""
        from app.services.rules.total_scorer import TotalScorer

        property_type_merged = PROPERTY_TYPE_MAP.get(property_type, "기타")

        # TotalScorer._calc_predicted_ratio (static method)
        pred = TotalScorer._calc_predicted_ratio(property_type_merged, fail_count)

        predicted_price = int(pred * appraised_value)

        return PredictionResult(
            predicted_ratio=round(pred, 4),
            predicted_price=predicted_price,
            confidence="low",
            model_version="rule_v1",
            top_factors=["유찰횟수", "물건유형"],
            fallback_reason="ML 모델 파일 없음 → 룩업 테이블 사용",
        )

    def _assess_confidence(
        self,
        *,
        fail_count: int,
        rolling_count: int | None,
        discount_rate: float,
    ) -> str:
        """예측 신뢰도 판단

        - high: 유찰 0~2회 + rolling 데이터 10건+
        - medium: 유찰 3~4회 또는 rolling 데이터 부족
        - low: 유찰 5회+ 또는 discount_rate 극단
        """
        rc = rolling_count or 0

        if fail_count >= 5 or discount_rate < 0.2 or discount_rate > 0.95:
            return "low"
        if fail_count >= 3 or rc < 5:
            return "medium"
        if rc >= 10:
            return "high"
        return "medium"

    def _get_top_factors(self, features: dict) -> list[str]:
        """피처 중요도 기준 상위 3개 영향 요인 (한국어)"""
        if not self.feature_importances:
            return ["할인율", "유찰횟수", "물건유형"]

        FEATURE_LABELS = {
            "discount_rate": "할인율",
            "fail_count": "유찰횟수",
            "property_type_merged": "물건유형",
            "court_office_code": "법원",
            "sido": "시도",
            "sgg": "시군구",
            "rolling_avg_3m": "유사물건 평균",
            "rolling_count_3m": "유사물건 건수",
            "appraised_value_log": "감정가",
            "tenant_count": "임차인수",
            "total_deposit_ratio": "보증금비율",
            "quarter": "분기",
            "year_month": "시기",
        }

        sorted_features = sorted(
            self.feature_importances.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            FEATURE_LABELS.get(f, f)
            for f, _ in sorted_features[:3]
        ]
