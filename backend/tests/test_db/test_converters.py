"""Pydantic ↔ SQLAlchemy 양방향 변환 테스트

핵심: roundtrip 무손실 검증 (EnrichedCase → DB → EnrichedCase).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.models.auction import AuctionCaseDetail
from app.models.db.converters import (
    auction_detail_to_orm,
    auction_orm_to_detail,
    auction_orm_to_enriched,
    filter_dto_to_orm,
    filter_orm_to_dto,
    registry_analysis_dto_to_orm,
    registry_analysis_orm_to_dto,
    registry_event_dto_to_orm,
    registry_event_orm_to_dto,
    save_enriched_case,
)
from app.models.db.auction import Auction
from app.models.db.registry import RegistryEventORM
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
    EventType,
    HardStopFlag,
    RegistryAnalysisResult,
    RegistryDocument,
    RegistryEvent,
    RightClassification,
    SectionType,
)


def _sample_detail() -> AuctionCaseDetail:
    return AuctionCaseDetail(
        case_number="2026타경99999",
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울 강남구 역삼동 123-4 ○○아파트 101동 301호",
        appraised_value=500_000_000,
        minimum_bid=350_000_000,
        auction_date=date(2026, 3, 15),
        status="진행",
        bid_count=2,
        court_office_code="B000210",
        internal_case_number="20260130099999",
    )


def _sample_filter_result() -> FilterResult:
    return FilterResult(
        color=FilterColor.YELLOW,
        passed=True,
        matched_rules=[
            RuleMatch(rule_id="Y001", rule_name="3회이상유찰", description="유찰 3회"),
        ],
    )


def _sample_registry_event() -> RegistryEvent:
    return RegistryEvent(
        section=SectionType.EULGU,
        rank_no=1,
        purpose="근저당권설정",
        event_type=EventType.MORTGAGE,
        accepted_at="2024.01.15",
        receipt_no="제12345호",
        cause="2024년1월15일 설정계약",
        holder="국민은행",
        amount=200_000_000,
        canceled=False,
        raw_text="1  근저당권설정  2024년1월15일 접수 제12345호 ...",
    )


def _sample_enriched_case() -> EnrichedCase:
    """전체 필드가 채워진 EnrichedCase"""
    detail = _sample_detail()
    mortgage = _sample_registry_event()
    seizure = RegistryEvent(
        section=SectionType.GAPGU,
        rank_no=2,
        purpose="경매개시결정",
        event_type=EventType.AUCTION_START,
        accepted_at="2025.06.01",
        raw_text="2 경매개시결정 ...",
    )

    doc = RegistryDocument(
        gapgu_events=[seizure],
        eulgu_events=[mortgage],
        all_events=[mortgage, seizure],
        parse_confidence=Confidence.HIGH,
        source="codef",
    )
    analysis = RegistryAnalysisResult(
        document=doc,
        cancellation_base_event=mortgage,
        cancellation_base_reason="최선순위 근저당",
        extinguished_rights=[
            AnalyzedRight(event=mortgage, classification=RightClassification.EXTINGUISHED, reason="말소기준 이후")
        ],
        surviving_rights=[],
        uncertain_rights=[],
        hard_stop_flags=[],
        has_hard_stop=False,
        confidence=Confidence.HIGH,
        summary="안전한 물건",
    )

    return EnrichedCase(
        case=detail,
        coordinates={"x": "127.0365", "y": "37.4994"},
        building=BuildingInfo(main_purpose="공동주택", violation=False),
        land_use=LandUseInfo(zones=["제3종일반주거지역"], is_greenbelt=False),
        market_price=MarketPriceInfo(avg_price_per_m2=12_000_000, trade_count=5),
        filter_result=_sample_filter_result(),
        registry_analysis=analysis,
        registry_unique_no="1234-5678-90",
        registry_match_confidence=0.95,
    )


class TestAuctionDetailConversion:
    """AuctionCaseDetail ↔ Auction ORM"""

    def test_to_orm(self):
        detail = _sample_detail()
        orm = auction_detail_to_orm(detail)
        assert orm.case_number == "2026타경99999"
        assert orm.court == "서울중앙지방법원"
        assert orm.appraised_value == 500_000_000
        assert orm.detail is not None  # JSONB 스냅샷

    def test_to_orm_with_enrichment(self):
        detail = _sample_detail()
        building = BuildingInfo(main_purpose="업무시설")
        orm = auction_detail_to_orm(
            detail,
            coordinates={"x": "127.0"},
            building=building,
        )
        assert orm.coordinates == {"x": "127.0"}
        assert orm.building_info["main_purpose"] == "업무시설"

    def test_orm_to_detail_from_jsonb(self, db_session):
        detail = _sample_detail()
        orm = auction_detail_to_orm(detail)
        db_session.add(orm)
        db_session.commit()

        restored = auction_orm_to_detail(orm)
        assert restored.case_number == detail.case_number
        assert restored.court == detail.court
        assert restored.appraised_value == detail.appraised_value
        assert restored.internal_case_number == detail.internal_case_number

    def test_roundtrip_lossless(self, db_session):
        detail = _sample_detail()
        orm = auction_detail_to_orm(detail)
        db_session.add(orm)
        db_session.commit()

        restored = auction_orm_to_detail(orm)
        assert restored.model_dump(mode="json") == detail.model_dump(mode="json")


class TestFilterResultConversion:
    """FilterResult ↔ FilterResultORM"""

    def test_to_orm(self, db_session):
        auction = auction_detail_to_orm(_sample_detail())
        db_session.add(auction)
        db_session.flush()

        fr = _sample_filter_result()
        fr_orm = filter_dto_to_orm(fr, auction.id)
        db_session.add(fr_orm)
        db_session.commit()

        assert fr_orm.color == "YELLOW"
        assert fr_orm.passed is True

    def test_orm_to_dto(self, db_session):
        auction = auction_detail_to_orm(_sample_detail())
        db_session.add(auction)
        db_session.flush()

        fr = _sample_filter_result()
        fr_orm = filter_dto_to_orm(fr, auction.id)
        db_session.add(fr_orm)
        db_session.commit()

        restored = filter_orm_to_dto(fr_orm)
        assert restored.color == FilterColor.YELLOW
        assert restored.passed is True
        assert len(restored.matched_rules) == 1
        assert restored.matched_rules[0].rule_id == "Y001"


class TestRegistryEventConversion:
    """RegistryEvent ↔ RegistryEventORM"""

    def test_to_orm(self, db_session):
        auction = auction_detail_to_orm(_sample_detail())
        db_session.add(auction)
        db_session.flush()

        evt = _sample_registry_event()
        evt_orm = registry_event_dto_to_orm(evt, auction.id)
        db_session.add(evt_orm)
        db_session.commit()

        assert evt_orm.section == "EULGU"
        assert evt_orm.amount == 200_000_000

    def test_orm_to_dto(self, db_session):
        auction = auction_detail_to_orm(_sample_detail())
        db_session.add(auction)
        db_session.flush()

        evt = _sample_registry_event()
        evt_orm = registry_event_dto_to_orm(evt, auction.id)
        db_session.add(evt_orm)
        db_session.commit()

        restored = registry_event_orm_to_dto(evt_orm)
        assert restored.section == SectionType.EULGU
        assert restored.event_type == EventType.MORTGAGE
        assert restored.amount == 200_000_000
        assert restored.holder == "국민은행"
        assert restored.accepted_at == "2024.01.15"


class TestRegistryAnalysisConversion:
    """RegistryAnalysisResult ↔ RegistryAnalysisORM"""

    def test_to_orm(self, db_session):
        auction = auction_detail_to_orm(_sample_detail())
        db_session.add(auction)
        db_session.flush()

        enriched = _sample_enriched_case()
        analysis = enriched.registry_analysis
        ra_orm = registry_analysis_dto_to_orm(
            analysis, auction.id, unique_no="1234-5678-90", match_confidence=0.95
        )
        db_session.add(ra_orm)
        db_session.commit()

        assert ra_orm.has_hard_stop is False
        assert ra_orm.confidence == "HIGH"
        assert ra_orm.registry_unique_no == "1234-5678-90"

    def test_orm_to_dto(self, db_session):
        auction = auction_detail_to_orm(_sample_detail())
        db_session.add(auction)
        db_session.flush()

        enriched = _sample_enriched_case()
        analysis = enriched.registry_analysis

        # 이벤트 먼저 저장
        events_orm = []
        for evt in analysis.document.all_events:
            evt_orm = registry_event_dto_to_orm(evt, auction.id)
            db_session.add(evt_orm)
            db_session.flush()
            events_orm.append(evt_orm)

        ra_orm = registry_analysis_dto_to_orm(analysis, auction.id)
        db_session.add(ra_orm)
        db_session.commit()

        restored = registry_analysis_orm_to_dto(ra_orm, events_orm)
        assert restored.has_hard_stop is False
        assert restored.confidence == Confidence.HIGH
        assert len(restored.extinguished_rights) == 1
        assert restored.extinguished_rights[0].classification == RightClassification.EXTINGUISHED


class TestSaveEnrichedCase:
    """save_enriched_case 통합 테스트"""

    def test_save_new(self, db_session):
        enriched = _sample_enriched_case()
        auction = save_enriched_case(db_session, enriched)

        assert auction.case_number == "2026타경99999"
        assert db_session.query(Auction).count() == 1

        # filter_result 확인
        from app.models.db.filter_result import FilterResultORM
        fr = db_session.query(FilterResultORM).first()
        assert fr is not None
        assert fr.color == "YELLOW"

        # registry_events 확인
        events = db_session.query(RegistryEventORM).all()
        assert len(events) == 2  # mortgage + seizure

    def test_upsert_update(self, db_session):
        enriched = _sample_enriched_case()
        save_enriched_case(db_session, enriched)

        # 두 번째 저장 (업데이트)
        enriched.case.minimum_bid = 300_000_000
        enriched.filter_result = FilterResult(
            color=FilterColor.GREEN, passed=True, matched_rules=[]
        )
        save_enriched_case(db_session, enriched)

        assert db_session.query(Auction).count() == 1
        auction = db_session.query(Auction).first()
        assert auction.minimum_bid == 300_000_000

        from app.models.db.filter_result import FilterResultORM
        fr = db_session.query(FilterResultORM).first()
        assert fr.color == "GREEN"

    def test_save_without_registry(self, db_session):
        enriched = EnrichedCase(
            case=_sample_detail(),
            filter_result=_sample_filter_result(),
        )
        auction = save_enriched_case(db_session, enriched)

        assert auction.case_number == "2026타경99999"
        assert db_session.query(RegistryEventORM).count() == 0


class TestRoundtripEnrichedCase:
    """EnrichedCase → DB → EnrichedCase 무손실 roundtrip"""

    def test_full_roundtrip(self, db_session):
        original = _sample_enriched_case()
        save_enriched_case(db_session, original)

        # ORM에서 복원
        auction = db_session.query(Auction).first()
        restored = auction_orm_to_enriched(auction)

        # 핵심 필드 비교
        assert restored.case.case_number == original.case.case_number
        assert restored.case.court == original.case.court
        assert restored.case.appraised_value == original.case.appraised_value
        assert restored.coordinates == original.coordinates
        assert restored.building.main_purpose == original.building.main_purpose
        assert restored.land_use.is_greenbelt == original.land_use.is_greenbelt
        assert restored.filter_result.color == original.filter_result.color
        assert restored.filter_result.passed == original.filter_result.passed
        assert restored.registry_unique_no == original.registry_unique_no
        assert restored.registry_match_confidence == original.registry_match_confidence
        assert restored.registry_analysis is not None
        assert restored.registry_analysis.has_hard_stop == original.registry_analysis.has_hard_stop
        assert restored.registry_analysis.confidence == original.registry_analysis.confidence
        assert len(restored.registry_analysis.extinguished_rights) == len(original.registry_analysis.extinguished_rights)
