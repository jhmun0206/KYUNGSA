"""API 응답/요청 스키마

내부 모델(EnrichedCase, RegistryAnalysisResult 등)을 API 응답용으로 래핑.
내부 모델을 직접 노출하지 않아 향후 변경 자유도를 확보한다.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enriched_case import EnrichedCase, FilterColor
from app.models.registry import Confidence, HardStopFlag, RegistryAnalysisResult
from app.services.registry.pipeline import RegistryPipelineResult


# ── 목록 조회 ──────────────────────────────────────────────────


class AuctionItemSummary(BaseModel):
    """경매 물건 요약 (목록용)"""

    case_number: str
    court_name: str
    address: str
    appraisal_value: int
    minimum_bid: int
    auction_date: str | None = None
    filter_result: str  # "GREEN" / "YELLOW" / "RED"
    filter_reasons: list[str] = Field(default_factory=list)
    has_registry: bool = False
    registry_hard_stop: bool | None = None


class AuctionListResponse(BaseModel):
    """경매 물건 목록 응답"""

    items: list[AuctionItemSummary]
    total: int
    page: int
    page_size: int


# ── 상세 조회 ──────────────────────────────────────────────────


class HardStopDetail(BaseModel):
    """Hard Stop 상세"""

    rule_id: str
    name: str
    description: str


class AnalyzedRightSummary(BaseModel):
    """분석된 권리 요약"""

    event_type: str
    classification: str  # "소멸" / "인수" / "불확실"
    amount: int | None = None
    holder: str | None = None
    reason: str


class RegistryAnalysisSummary(BaseModel):
    """등기부 분석 결과 요약 (API 응답용)"""

    unique_no: str = ""
    match_confidence: float | None = None
    has_hard_stop: bool = False
    hard_stop_reasons: list[HardStopDetail] = Field(default_factory=list)
    cancellation_base: str | None = None  # 말소기준권리 설명
    surviving_rights: list[AnalyzedRightSummary] = Field(default_factory=list)
    extinguished_rights: list[AnalyzedRightSummary] = Field(default_factory=list)
    uncertain_rights: list[AnalyzedRightSummary] = Field(default_factory=list)
    total_encumbrance: int = 0  # 총 부담액
    confidence: str = ""  # "HIGH" / "MEDIUM" / "LOW"
    summary: str = ""
    analyzed_at: datetime | None = None


class FilterDetailResponse(BaseModel):
    """1단 필터 상세"""

    color: str
    passed: bool
    rules: list[dict] = Field(default_factory=list)
    building: dict | None = None
    land_use: dict | None = None
    market_price: dict | None = None


class AuctionDetailResponse(BaseModel):
    """경매 물건 상세 (1단 + 2단)"""

    case_number: str
    court_name: str
    address: str
    appraisal_value: int
    minimum_bid: int
    auction_date: str | None = None
    # 1단 분석
    filter_result: str
    filter_reasons: list[str] = Field(default_factory=list)
    filter_details: FilterDetailResponse | None = None
    # 2단 분석
    registry: RegistryAnalysisSummary | None = None
    registry_error: str | None = None


# ── 등기부 단독 조회 ──────────────────────────────────────────


class RegistryAnalysisResponse(BaseModel):
    """등기부 분석 단독 응답"""

    unique_no: str
    address: str
    analysis: RegistryAnalysisSummary
    raw_events_count: int = 0


# ── 즉시 분석 요청 ────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    """단일 물건 즉시 분석 요청"""

    address: str
    appraisal_value: int | None = None
    minimum_bid: int | None = None


# ── 변환 함수 ─────────────────────────────────────────────────


def _hard_stop_to_detail(flag: HardStopFlag) -> HardStopDetail:
    return HardStopDetail(
        rule_id=flag.rule_id,
        name=flag.name,
        description=flag.description,
    )


def _analysis_to_summary(
    analysis: RegistryAnalysisResult,
    unique_no: str = "",
    match_confidence: float | None = None,
    analyzed_at: datetime | None = None,
) -> RegistryAnalysisSummary:
    """RegistryAnalysisResult → API 요약"""
    # 말소기준권리 설명
    cancellation_base = None
    if analysis.cancellation_base_event:
        base = analysis.cancellation_base_event
        cancellation_base = (
            f"{base.event_type.value} ({base.accepted_at or '날짜 불명'})"
        )

    # 권리 요약 변환
    def _right_summary(analyzed_right):
        return AnalyzedRightSummary(
            event_type=analyzed_right.event.event_type.value,
            classification=analyzed_right.classification.value,
            amount=analyzed_right.event.amount,
            holder=analyzed_right.event.holder,
            reason=analyzed_right.reason,
        )

    surviving = [_right_summary(r) for r in analysis.surviving_rights]
    extinguished = [_right_summary(r) for r in analysis.extinguished_rights]
    uncertain = [_right_summary(r) for r in analysis.uncertain_rights]

    # 총 부담액: 인수 권리 금액 합산
    total_encumbrance = sum(
        r.event.amount for r in analysis.surviving_rights
        if r.event.amount
    )

    return RegistryAnalysisSummary(
        unique_no=unique_no,
        match_confidence=match_confidence,
        has_hard_stop=analysis.has_hard_stop,
        hard_stop_reasons=[_hard_stop_to_detail(f) for f in analysis.hard_stop_flags],
        cancellation_base=cancellation_base,
        surviving_rights=surviving,
        extinguished_rights=extinguished,
        uncertain_rights=uncertain,
        total_encumbrance=total_encumbrance,
        confidence=analysis.confidence.value,
        summary=analysis.summary,
        analyzed_at=analyzed_at,
    )


def enriched_to_summary(e: EnrichedCase) -> AuctionItemSummary:
    """EnrichedCase → API 목록 응답"""
    fr = e.filter_result
    color = fr.color.value if fr else "GREEN"
    reasons = [rm.description or rm.rule_name for rm in fr.matched_rules] if fr else []

    has_registry = e.registry_analysis is not None
    registry_hard_stop = None
    if e.registry_analysis:
        registry_hard_stop = e.registry_analysis.has_hard_stop

    auction_date_str = None
    if e.case.auction_date:
        auction_date_str = e.case.auction_date.isoformat()

    return AuctionItemSummary(
        case_number=e.case.case_number,
        court_name=e.case.court,
        address=e.case.address,
        appraisal_value=e.case.appraised_value,
        minimum_bid=e.case.minimum_bid,
        auction_date=auction_date_str,
        filter_result=color,
        filter_reasons=reasons,
        has_registry=has_registry,
        registry_hard_stop=registry_hard_stop,
    )


def enriched_to_detail(e: EnrichedCase) -> AuctionDetailResponse:
    """EnrichedCase → API 상세 응답"""
    fr = e.filter_result
    color = fr.color.value if fr else "GREEN"
    reasons = [rm.description or rm.rule_name for rm in fr.matched_rules] if fr else []

    # 1단 필터 상세
    filter_details = None
    if fr:
        rules = [
            {"rule_id": rm.rule_id, "name": rm.rule_name, "description": rm.description}
            for rm in fr.matched_rules
        ]
        filter_details = FilterDetailResponse(
            color=color,
            passed=fr.passed,
            rules=rules,
            building=e.building.model_dump() if e.building else None,
            land_use=e.land_use.model_dump() if e.land_use else None,
            market_price=e.market_price.model_dump() if e.market_price else None,
        )

    # 2단 등기부 분석
    registry_summary = None
    if e.registry_analysis:
        registry_summary = _analysis_to_summary(
            analysis=e.registry_analysis,
            unique_no=e.registry_unique_no or "",
            match_confidence=e.registry_match_confidence,
        )

    auction_date_str = None
    if e.case.auction_date:
        auction_date_str = e.case.auction_date.isoformat()

    return AuctionDetailResponse(
        case_number=e.case.case_number,
        court_name=e.case.court,
        address=e.case.address,
        appraisal_value=e.case.appraised_value,
        minimum_bid=e.case.minimum_bid,
        auction_date=auction_date_str,
        filter_result=color,
        filter_reasons=reasons,
        filter_details=filter_details,
        registry=registry_summary,
        registry_error=e.registry_error,
    )


def pipeline_result_to_registry(r: RegistryPipelineResult) -> RegistryAnalysisResponse:
    """RegistryPipelineResult → API 등기부 응답"""
    return RegistryAnalysisResponse(
        unique_no=r.unique_no,
        address=r.address,
        analysis=_analysis_to_summary(
            analysis=r.analysis,
            unique_no=r.unique_no,
            analyzed_at=r.queried_at,
        ),
        raw_events_count=len(r.registry_document.all_events),
    )
