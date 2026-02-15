"""API 스키마 변환 함수 테스트"""

from datetime import date, datetime

import pytest

from app.api.schemas import (
    AnalyzeRequest,
    AuctionDetailResponse,
    AuctionItemSummary,
    RegistryAnalysisResponse,
    enriched_to_detail,
    enriched_to_summary,
    pipeline_result_to_registry,
)
from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import (
    BuildingInfo,
    EnrichedCase,
    FilterColor,
    FilterResult,
    LandUseInfo,
    MarketPriceInfo,
    RuleMatch,
)
from app.models.registry import (
    AnalyzedRight,
    Confidence,
    HardStopFlag,
    RegistryAnalysisResult,
    RegistryDocument,
    RegistryEvent,
    EventType,
    RightClassification,
    SectionType,
)
from app.services.registry.pipeline import RegistryPipelineResult


# ── 헬퍼 ──────────────────────────────────────────────────────


def _make_detail() -> AuctionCaseDetail:
    return AuctionCaseDetail(
        case_number="2025타경10001",
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123-4",
        appraised_value=500_000_000,
        minimum_bid=320_000_000,
        auction_date=date(2026, 3, 15),
    )


def _make_enriched(
    color: FilterColor = FilterColor.GREEN,
    with_registry: bool = False,
) -> EnrichedCase:
    detail = _make_detail()
    rules = []
    if color == FilterColor.RED:
        rules = [RuleMatch(rule_id="R001", rule_name="개발제한구역", description="그린벨트")]
    elif color == FilterColor.YELLOW:
        rules = [RuleMatch(rule_id="Y001", rule_name="유찰3회", description="3회 이상 유찰")]

    enriched = EnrichedCase(
        case=detail,
        building=BuildingInfo(main_purpose="공동주택", violation=False),
        land_use=LandUseInfo(zones=["제1종일반주거지역"]),
        market_price=MarketPriceInfo(avg_price_per_m2=5_000_000, trade_count=3),
        filter_result=FilterResult(
            color=color,
            passed=color != FilterColor.RED,
            matched_rules=rules,
        ),
    )

    if with_registry:
        mock_event = RegistryEvent(
            section=SectionType.EULGU,
            purpose="근저당권설정",
            event_type=EventType.MORTGAGE,
            accepted_at="2020.03.15",
            amount=600_000_000,
            holder="○○은행",
            raw_text="근저당권설정 테스트",
        )
        enriched.registry_analysis = RegistryAnalysisResult(
            document=RegistryDocument(source="codef"),
            cancellation_base_event=mock_event,
            cancellation_base_reason="근저당 (최선순위 담보)",
            extinguished_rights=[
                AnalyzedRight(
                    event=mock_event,
                    classification=RightClassification.EXTINGUISHED,
                    reason="말소기준 이후 설정",
                )
            ],
            has_hard_stop=False,
            confidence=Confidence.HIGH,
            summary="서울특별시 강남구 역삼동 — Hard Stop 없음",
        )
        enriched.registry_unique_no = "11460000012345"
        enriched.registry_match_confidence = 1.0

    return enriched


# ============================================================
# TestEnrichedToSummary — 목록 변환
# ============================================================


class TestEnrichedToSummary:
    """enriched_to_summary 변환 검증"""

    def test_basic_fields(self) -> None:
        """기본 필드 매핑"""
        enriched = _make_enriched()
        summary = enriched_to_summary(enriched)

        assert summary.case_number == "2025타경10001"
        assert summary.court_name == "서울중앙지방법원"
        assert summary.address == "서울특별시 강남구 역삼동 123-4"
        assert summary.appraisal_value == 500_000_000
        assert summary.minimum_bid == 320_000_000
        assert summary.auction_date == "2026-03-15"

    def test_green_filter(self) -> None:
        """GREEN 필터 결과"""
        summary = enriched_to_summary(_make_enriched(FilterColor.GREEN))
        assert summary.filter_result == "GREEN"
        assert summary.filter_reasons == []

    def test_red_filter_with_reasons(self) -> None:
        """RED 필터 + 사유"""
        summary = enriched_to_summary(_make_enriched(FilterColor.RED))
        assert summary.filter_result == "RED"
        assert len(summary.filter_reasons) == 1
        assert "그린벨트" in summary.filter_reasons[0]

    def test_registry_absent(self) -> None:
        """등기부 분석 없음"""
        summary = enriched_to_summary(_make_enriched(with_registry=False))
        assert summary.has_registry is False
        assert summary.registry_hard_stop is None

    def test_registry_present(self) -> None:
        """등기부 분석 있음"""
        summary = enriched_to_summary(_make_enriched(with_registry=True))
        assert summary.has_registry is True
        assert summary.registry_hard_stop is False


# ============================================================
# TestEnrichedToDetail — 상세 변환
# ============================================================


class TestEnrichedToDetail:
    """enriched_to_detail 변환 검증"""

    def test_basic_fields(self) -> None:
        """기본 필드"""
        detail = enriched_to_detail(_make_enriched())
        assert detail.case_number == "2025타경10001"
        assert detail.filter_result == "GREEN"

    def test_filter_details_present(self) -> None:
        """필터 상세 포함"""
        detail = enriched_to_detail(_make_enriched(FilterColor.RED))
        assert detail.filter_details is not None
        assert detail.filter_details.color == "RED"
        assert detail.filter_details.passed is False
        assert len(detail.filter_details.rules) == 1

    def test_building_info_in_details(self) -> None:
        """건축물 정보 포함"""
        detail = enriched_to_detail(_make_enriched())
        assert detail.filter_details is not None
        assert detail.filter_details.building is not None
        assert detail.filter_details.building["main_purpose"] == "공동주택"

    def test_registry_none_when_absent(self) -> None:
        """등기부 없으면 null"""
        detail = enriched_to_detail(_make_enriched(with_registry=False))
        assert detail.registry is None
        assert detail.registry_error is None

    def test_registry_present(self) -> None:
        """등기부 있으면 요약 반환"""
        detail = enriched_to_detail(_make_enriched(with_registry=True))
        assert detail.registry is not None
        assert detail.registry.unique_no == "11460000012345"
        assert detail.registry.match_confidence == 1.0
        assert detail.registry.has_hard_stop is False
        assert "근저당" in (detail.registry.cancellation_base or "")

    def test_registry_rights_populated(self) -> None:
        """권리 분류 결과 포함"""
        detail = enriched_to_detail(_make_enriched(with_registry=True))
        assert detail.registry is not None
        assert len(detail.registry.extinguished_rights) == 1
        assert detail.registry.extinguished_rights[0].event_type == "근저당권설정"

    def test_registry_error_preserved(self) -> None:
        """registry_error 전달"""
        enriched = _make_enriched()
        enriched.registry_error = "CODEF 검색 결과 없음"
        detail = enriched_to_detail(enriched)
        assert detail.registry_error == "CODEF 검색 결과 없음"


# ============================================================
# TestPipelineResultToRegistry — 등기부 단독 변환
# ============================================================


class TestPipelineResultToRegistry:
    """pipeline_result_to_registry 변환 검증"""

    def test_basic_conversion(self) -> None:
        """정상 변환"""
        doc = RegistryDocument(source="codef")
        analysis = RegistryAnalysisResult(
            document=doc,
            confidence=Confidence.HIGH,
            summary="테스트 요약",
        )
        result = RegistryPipelineResult(
            unique_no="11460000012345",
            address="서울특별시 강남구 역삼동 123-45",
            registry_document=doc,
            analysis=analysis,
        )
        response = pipeline_result_to_registry(result)

        assert response.unique_no == "11460000012345"
        assert response.address == "서울특별시 강남구 역삼동 123-45"
        assert response.analysis.confidence == "HIGH"
        assert response.analysis.summary == "테스트 요약"
        assert response.raw_events_count == 0

    def test_events_count(self) -> None:
        """이벤트 수 반영"""
        event = RegistryEvent(
            section=SectionType.EULGU,
            purpose="근저당권설정",
            raw_text="test",
        )
        doc = RegistryDocument(
            source="codef",
            all_events=[event, event],
        )
        analysis = RegistryAnalysisResult(document=doc, summary="요약")
        result = RegistryPipelineResult(
            unique_no="X",
            registry_document=doc,
            analysis=analysis,
        )
        response = pipeline_result_to_registry(result)
        assert response.raw_events_count == 2


# ============================================================
# TestAnalyzeRequest — 요청 유효성
# ============================================================


class TestAnalyzeRequest:
    """AnalyzeRequest 유효성"""

    def test_valid_request(self) -> None:
        """정상 요청"""
        req = AnalyzeRequest(address="서울특별시 강남구 역삼동 123-4")
        assert req.address == "서울특별시 강남구 역삼동 123-4"
        assert req.appraisal_value is None

    def test_with_values(self) -> None:
        """감정가 포함 요청"""
        req = AnalyzeRequest(
            address="서울 강남구 역삼동 123-4",
            appraisal_value=500_000_000,
            minimum_bid=320_000_000,
        )
        assert req.appraisal_value == 500_000_000
        assert req.minimum_bid == 320_000_000
