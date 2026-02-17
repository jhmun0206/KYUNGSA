"""RuleEngine v2 오케스트레이터 (5E)

1단 색상 필터 → pillar 점수(가격/법률) → 통합 점수 → 등급을 일괄 산출한다.
DB 저장은 호출자(batch_collector, pipeline)의 책임.

흐름:
  1. FilterEngine.evaluate() → RED/YELLOW/GREEN
  2. PriceScorer.score() → 가격 매력도 (항상)
  3. LegalScorer.score() → 법률 리스크 (등기부 있을 때만)
  4. TotalScorer.score() → 통합 점수 + 등급
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from app.models.enriched_case import (
    EnrichedCase,
    FilterResult,
)
from app.models.registry import RegistryAnalysisResult
from app.models.scores import (
    LegalScoreResult,
    LocationScoreResult,
    PriceScoreResult,
    TotalScoreResult,
)
from app.services.filter_engine import FilterEngine
from app.services.rules.legal_scorer import LegalScorer
from app.services.rules.location_scorer import LocationScorer
from app.services.rules.price_scorer import PriceScorer
from app.services.rules.total_scorer import TotalScorer

logger = logging.getLogger(__name__)


class EvaluationResult(BaseModel):
    """RuleEngineV2 전체 평가 결과"""

    filter_result: FilterResult
    legal: LegalScoreResult | None = None
    price: PriceScoreResult | None = None
    location: LocationScoreResult | None = None
    total: TotalScoreResult


class RuleEngineV2:
    """통합 룰 엔진 — 필터 + pillar 점수 + 통합 합산"""

    def __init__(
        self,
        filter_engine: FilterEngine | None = None,
        legal_scorer: LegalScorer | None = None,
        price_scorer: PriceScorer | None = None,
        location_scorer: LocationScorer | None = None,
        total_scorer: TotalScorer | None = None,
    ) -> None:
        self._filter = filter_engine or FilterEngine()
        self._legal_scorer = legal_scorer or LegalScorer()
        self._price_scorer = price_scorer or PriceScorer()
        self._location_scorer = location_scorer or LocationScorer()
        self._total_scorer = total_scorer or TotalScorer()

    def evaluate(
        self,
        enriched: EnrichedCase,
        *,
        registry_analysis: RegistryAnalysisResult | None = None,
    ) -> EvaluationResult:
        """전체 평가 수행

        Args:
            enriched: 보강된 경매 물건
            registry_analysis: 등기부 분석 결과 (있으면 법률 점수 산출)

        Returns:
            EvaluationResult
        """
        case = enriched.case

        # 1. 색상 필터
        filter_result = self._filter.evaluate(enriched)

        # 2. 가격 점수 (항상 산출)
        price_result = self._price_scorer.score(
            case=case,
            market_price=enriched.market_price,
        )

        # 3. 법률 점수 (등기부 있을 때만)
        legal_result: LegalScoreResult | None = None
        needs_expert = False

        if registry_analysis is not None:
            legal_result = self._legal_scorer.score(
                case=case,
                registry_analysis=registry_analysis,
            )
            needs_expert = legal_result.needs_expert_review

        # 4. 입지 점수 (좌표 있을 때만 — location_data 기반)
        location_result = self._location_scorer.score(
            case=case,
            location_data=enriched.location_data,
            land_use=enriched.land_use,
        )

        # 5. 통합 점수 (fail_count = bid_count - 1, 유찰 횟수)
        fail_count = max(0, (case.bid_count or 1) - 1)
        total_result = self._total_scorer.score(
            property_type=case.property_type,
            legal_score=legal_result.score if legal_result else None,
            price_score=price_result.score,
            location_score=location_result.score if location_result else None,
            needs_expert_review=needs_expert,
            fail_count=fail_count,
        )

        return EvaluationResult(
            filter_result=filter_result,
            legal=legal_result,
            price=price_result,
            location=location_result,
            total=total_result,
        )
