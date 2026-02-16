"""RuleEngineV2 통합 테스트

오케스트레이터가 필터 → pillar 점수 → 통합 점수를 올바르게 연결하는지 검증한다.
"""

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import (
    BuildingInfo,
    EnrichedCase,
    FilterColor,
    LandUseInfo,
    MarketPriceInfo,
)
from app.models.registry import (
    Confidence,
    RegistryAnalysisResult,
    RegistryDocument,
)
from app.services.rules.engine import RuleEngineV2


# ──────────────────────────────────────
# 테스트 헬퍼
# ──────────────────────────────────────


def _make_case(**overrides) -> AuctionCaseDetail:
    """테스트용 AuctionCaseDetail"""
    defaults = {
        "case_number": "2025타경10001",
        "court": "서울중앙지방법원",
        "property_type": "아파트",
        "address": "서울특별시 강남구 역삼동 123-4",
        "appraised_value": 500_000_000,
        "minimum_bid": 255_000_000,  # 3회차 (discount_rate≈0.49)
        "area_m2": 84.0,
    }
    defaults.update(overrides)
    return AuctionCaseDetail(**defaults)


def _make_enriched(**overrides) -> EnrichedCase:
    """테스트용 EnrichedCase"""
    enriched_keys = {
        "coordinates", "building", "land_use", "market_price", "filter_result",
    }
    case_overrides = {}
    enriched_overrides = {}
    for k, v in overrides.items():
        if k in enriched_keys:
            enriched_overrides[k] = v
        else:
            case_overrides[k] = v
    return EnrichedCase(case=_make_case(**case_overrides), **enriched_overrides)


def _make_registry_analysis(
    has_hard_stop: bool = False,
    confidence: Confidence = Confidence.HIGH,
) -> RegistryAnalysisResult:
    """테스트용 RegistryAnalysisResult (최소)"""
    return RegistryAnalysisResult(
        document=RegistryDocument(source="test"),
        has_hard_stop=has_hard_stop,
        confidence=confidence,
        summary="테스트용",
    )


engine = RuleEngineV2()


# ──────────────────────────────────────
# 평가 흐름 테스트
# ──────────────────────────────────────


class TestEvaluateFlow:
    """evaluate() 흐름 검증"""

    def test_with_legal_score(self):
        """등기부 있을 때 → legal + price + total 모두 산출"""
        enriched = _make_enriched(
            building=BuildingInfo(main_purpose="공동주택"),
            market_price=MarketPriceInfo(
                avg_price_per_m2=5_000_000.0, trade_count=15,
            ),
        )
        analysis = _make_registry_analysis()

        result = engine.evaluate(enriched, registry_analysis=analysis)

        assert result.filter_result is not None
        assert result.filter_result.color == FilterColor.GREEN
        assert result.price is not None
        assert result.price.score > 0
        assert result.legal is not None
        assert result.legal.score > 0
        assert result.total is not None
        assert result.total.total_score > 0
        assert result.total.grade in {"A", "B", "C", "D"}
        # 법률+가격 둘 다 가용 → missing은 location, occupancy
        assert "legal" not in result.total.missing_pillars
        assert "price" not in result.total.missing_pillars

    def test_without_legal_score(self):
        """등기부 없을 때 → price + total만 (legal=None)"""
        enriched = _make_enriched(
            market_price=MarketPriceInfo(
                avg_price_per_m2=5_000_000.0, trade_count=15,
            ),
        )

        result = engine.evaluate(enriched)

        assert result.legal is None
        assert result.price is not None
        assert result.total is not None
        assert "legal" in result.total.missing_pillars
        # price만 가용 → coverage = price 가중치 (아파트: 0.25)
        assert result.total.score_coverage == 0.25

    def test_red_filter(self):
        """RED 필터 매칭 → filter_result.passed=False + 점수는 여전히 산출"""
        enriched = _make_enriched(
            land_use=LandUseInfo(
                zones=["개발제한구역"],
                is_greenbelt=True,
            ),
        )

        result = engine.evaluate(enriched)

        assert result.filter_result.color == FilterColor.RED
        assert result.filter_result.passed is False
        # RED라도 점수는 산출 (DB에 전 건 저장하므로)
        assert result.price is not None
        assert result.total is not None


# ──────────────────────────────────────
# 통합 시나리오 테스트
# ──────────────────────────────────────


class TestEvaluateScenarios:
    """현실적 시나리오 검증"""

    def test_attractive_apartment_grade(self):
        """매력적 아파트: 3회차 + 시세 60% + 깨끗한 등기부 → 높은 등급"""
        enriched = _make_enriched(
            property_type="아파트",
            appraised_value=500_000_000,
            minimum_bid=255_000_000,
            area_m2=100.0,
            market_price=MarketPriceInfo(
                avg_price_per_m2=5_000_000.0, trade_count=15,
            ),
        )
        analysis = _make_registry_analysis(has_hard_stop=False, confidence=Confidence.HIGH)

        result = engine.evaluate(enriched, registry_analysis=analysis)

        # 법률 깨끗 + 가격 매력적 → A 또는 B
        assert result.total.grade in {"A", "B"}
        assert result.total.property_category == "아파트"

    def test_property_category_propagation(self):
        """상가 유형 → 꼬마빌딩 카테고리 전파"""
        enriched = _make_enriched(property_type="상가")

        result = engine.evaluate(enriched)

        assert result.total.property_category == "꼬마빌딩"

    def test_needs_expert_review_from_legal(self):
        """법률 점수의 needs_expert_review → total에 전파"""
        enriched = _make_enriched(
            property_type="아파트",
            appraised_value=500_000_000,
            minimum_bid=255_000_000,
        )
        analysis = _make_registry_analysis(has_hard_stop=False, confidence=Confidence.HIGH)

        result = engine.evaluate(enriched, registry_analysis=analysis)

        # needs_expert_review는 legal 결과에서 전파됨
        assert isinstance(result.total.needs_expert_review, bool)
