"""RegistryAnalyzer 단위 테스트

등기부등본 분석 로직을 검증한다:
- 말소기준권리 판별
- 인수/소멸/불확실 분류
- Hard Stop 5종 탐지
- 신뢰도 산출
"""

import os

import pytest

from app.models.registry import (
    AnalyzedRight,
    Confidence,
    EventType,
    HardStopFlag,
    RegistryDocument,
    RegistryEvent,
    RegistryAnalysisResult,
    RightClassification,
    SectionType,
    TitleSection,
)
from app.services.parser.registry_analyzer import RegistryAnalyzer
from app.services.parser.registry_parser import RegistryParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _make_event(
    section: SectionType = SectionType.EULGU,
    rank_no: int = 1,
    purpose: str = "근저당권설정",
    event_type: EventType = EventType.MORTGAGE,
    accepted_at: str | None = "2020.01.01",
    receipt_no: str | None = "10000",
    amount: int | None = None,
    canceled: bool = False,
    raw_text: str = "",
    holder: str | None = None,
) -> RegistryEvent:
    """테스트용 이벤트 헬퍼"""
    return RegistryEvent(
        section=section,
        rank_no=rank_no,
        purpose=purpose,
        event_type=event_type,
        accepted_at=accepted_at,
        receipt_no=receipt_no,
        amount=amount,
        canceled=canceled,
        raw_text=raw_text or purpose,
        holder=holder,
    )


def _make_doc(
    events: list[RegistryEvent] | None = None,
    parse_confidence: Confidence = Confidence.HIGH,
    parse_warnings: list[str] | None = None,
    title: TitleSection | None = None,
) -> RegistryDocument:
    """테스트용 RegistryDocument 헬퍼"""
    events = events or []
    gapgu = [e for e in events if e.section == SectionType.GAPGU]
    eulgu = [e for e in events if e.section == SectionType.EULGU]
    all_sorted = sorted(events, key=lambda e: e.accepted_at or "")
    return RegistryDocument(
        title=title,
        gapgu_events=gapgu,
        eulgu_events=eulgu,
        all_events=all_sorted,
        parse_confidence=parse_confidence,
        parse_warnings=parse_warnings or [],
    )


@pytest.fixture
def analyzer():
    return RegistryAnalyzer()


@pytest.fixture
def parser():
    return RegistryParser()


# === TestCancellationBase ===


class TestCancellationBase:
    """말소기준권리 판별 테스트"""

    def test_mortgage_is_base(self, analyzer):
        """경매개시 이전 최선순위 근저당 → 말소기준"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage, auction])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is mortgage
        assert "담보권" in result.cancellation_base_reason

    def test_provisional_seizure_as_base_when_no_mortgage(self, analyzer):
        """근저당 없으면 가압류가 말소기준"""
        seizure = _make_event(
            event_type=EventType.PROVISIONAL_SEIZURE,
            accepted_at="2020.01.01",
            section=SectionType.GAPGU,
            purpose="가압류",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[seizure, auction])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is seizure
        assert "가압류" in result.cancellation_base_reason

    def test_seizure_as_base(self, analyzer):
        """압류가 말소기준 (근저당, 가압류 없을 때)"""
        seizure = _make_event(
            event_type=EventType.SEIZURE,
            accepted_at="2020.01.01",
            section=SectionType.GAPGU,
            purpose="압류",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="강제경매개시결정",
        )
        doc = _make_doc(events=[seizure, auction])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is seizure
        assert "압류" in result.cancellation_base_reason

    def test_auction_start_as_base_when_no_prior(self, analyzer):
        """경매개시 이전 담보/압류 없으면 경매개시 자체가 기준"""
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[auction])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is auction
        assert "경매개시결정" in result.cancellation_base_reason

    def test_canceled_mortgage_excluded(self, analyzer):
        """말소된 근저당은 기준에서 제외"""
        canceled_mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
            canceled=True,
        )
        seizure = _make_event(
            event_type=EventType.PROVISIONAL_SEIZURE,
            accepted_at="2020.01.01",
            section=SectionType.GAPGU,
            purpose="가압류",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[canceled_mortgage, seizure, auction])
        result = analyzer.analyze(doc)

        # 말소된 근저당은 스킵, 가압류가 기준
        assert result.cancellation_base_event is seizure

    def test_earliest_mortgage_selected(self, analyzer):
        """여러 근저당 중 최선순위(가장 빠른 접수일)가 기준"""
        mortgage1 = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2019.06.01",
            section=SectionType.EULGU,
            rank_no=2,
        )
        mortgage2 = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
            rank_no=1,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage1, mortgage2, auction])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is mortgage2

    def test_no_auction_start(self, analyzer):
        """경매개시결정 없으면 기준 판단 불가"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        doc = _make_doc(events=[mortgage])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is None
        assert "찾을 수 없" in result.cancellation_base_reason


# === TestRightClassification ===


class TestRightClassification:
    """인수/소멸/불확실 분류 테스트"""

    def _base_events(self):
        """기준 이벤트셋: 근저당(2018) + 경매개시(2023)"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
            rank_no=1,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
            rank_no=3,
        )
        return mortgage, auction

    def test_mortgage_before_base_extinguished(self, analyzer):
        """기준 이전 근저당 → 소멸"""
        base, auction = self._base_events()
        extra_mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2020.01.01",
            section=SectionType.EULGU,
            rank_no=2,
        )
        doc = _make_doc(events=[base, extra_mortgage, auction])
        result = analyzer.analyze(doc)

        # extra_mortgage는 기준 이후 설정 → 소멸
        ext_events = [ar.event for ar in result.extinguished_rights]
        assert extra_mortgage in ext_events

    def test_lease_before_base_surviving(self, analyzer):
        """기준 이전 전세권 → 인수"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2020.01.01",
            section=SectionType.EULGU,
            rank_no=1,
        )
        lease = _make_event(
            event_type=EventType.LEASE_RIGHT,
            accepted_at="2019.01.01",
            section=SectionType.EULGU,
            purpose="전세권설정",
            rank_no=2,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
            rank_no=3,
        )
        doc = _make_doc(events=[mortgage, lease, auction])
        result = analyzer.analyze(doc)

        surv_events = [ar.event for ar in result.surviving_rights]
        assert lease in surv_events

    def test_after_base_extinguished(self, analyzer):
        """기준 이후 설정 → 소멸"""
        base, auction = self._base_events()
        after_mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2022.01.01",
            section=SectionType.EULGU,
            rank_no=2,
        )
        doc = _make_doc(events=[base, after_mortgage, auction])
        result = analyzer.analyze(doc)

        ext_events = [ar.event for ar in result.extinguished_rights]
        assert after_mortgage in ext_events

    def test_ownership_uncertain(self, analyzer):
        """소유권 관련 → UNCERTAIN"""
        base, auction = self._base_events()
        ownership = _make_event(
            event_type=EventType.OWNERSHIP_TRANSFER,
            accepted_at="2015.01.01",
            section=SectionType.GAPGU,
            purpose="소유권이전",
            rank_no=1,
        )
        doc = _make_doc(events=[ownership, base, auction])
        result = analyzer.analyze(doc)

        unc_events = [ar.event for ar in result.uncertain_rights]
        assert ownership in unc_events

    def test_canceled_event_skipped(self, analyzer):
        """말소된 이벤트는 분류 안 함"""
        base, auction = self._base_events()
        canceled = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2019.01.01",
            section=SectionType.EULGU,
            rank_no=2,
            canceled=True,
        )
        doc = _make_doc(events=[base, canceled, auction])
        result = analyzer.analyze(doc)

        all_classified = (
            result.extinguished_rights
            + result.surviving_rights
            + result.uncertain_rights
        )
        classified_events = [ar.event for ar in all_classified]
        assert canceled not in classified_events

    def test_base_event_itself_skipped(self, analyzer):
        """말소기준권리 자체는 분류 안 함"""
        base, auction = self._base_events()
        doc = _make_doc(events=[base, auction])
        result = analyzer.analyze(doc)

        all_classified = (
            result.extinguished_rights
            + result.surviving_rights
            + result.uncertain_rights
        )
        classified_events = [ar.event for ar in all_classified]
        assert base not in classified_events


# === TestHardStop ===


class TestHardStop:
    """Hard Stop 탐지 테스트"""

    def test_preliminary_notice_hs001(self, analyzer):
        """예고등기 → HS001"""
        notice = _make_event(
            event_type=EventType.PRELIMINARY_NOTICE,
            section=SectionType.GAPGU,
            purpose="예고등기",
            raw_text="예고등기",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[notice, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is True
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS001" in rule_ids

    def test_trust_hs002(self, analyzer):
        """신탁 → HS002"""
        trust = _make_event(
            event_type=EventType.TRUST,
            section=SectionType.GAPGU,
            purpose="신탁",
            raw_text="신탁 수탁자 한국토지신탁",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[trust, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is True
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS002" in rule_ids

    def test_provisional_disposition_hs003(self, analyzer):
        """가처분 → HS003"""
        disposition = _make_event(
            event_type=EventType.PROVISIONAL_DISPOSITION,
            section=SectionType.GAPGU,
            purpose="가처분",
            raw_text="처분금지가처분",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[disposition, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is True
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS003" in rule_ids

    def test_repurchase_hs004(self, analyzer):
        """환매특약 → HS004"""
        repurchase = _make_event(
            event_type=EventType.REPURCHASE,
            section=SectionType.GAPGU,
            purpose="환매특약",
            raw_text="환매특약등기",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[repurchase, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is True
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS004" in rule_ids

    def test_statutory_superficies_hs005(self, analyzer):
        """법정지상권 키워드 → HS005"""
        event = _make_event(
            event_type=EventType.OTHER,
            section=SectionType.GAPGU,
            purpose="기타등기",
            raw_text="법정지상권 성립 가능성 있음",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[event, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is True
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS005" in rule_ids

    def test_canceled_event_not_hard_stop(self, analyzer):
        """말소된 예고등기는 Hard Stop 아님"""
        notice = _make_event(
            event_type=EventType.PRELIMINARY_NOTICE,
            section=SectionType.GAPGU,
            purpose="예고등기",
            raw_text="예고등기",
            canceled=True,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[notice, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is False

    def test_multiple_hard_stops(self, analyzer):
        """복수 Hard Stop 동시 탐지"""
        notice = _make_event(
            event_type=EventType.PRELIMINARY_NOTICE,
            section=SectionType.GAPGU,
            purpose="예고등기",
            raw_text="예고등기",
            accepted_at="2021.01.01",
        )
        trust = _make_event(
            event_type=EventType.TRUST,
            section=SectionType.GAPGU,
            purpose="신탁",
            raw_text="신탁 수탁자",
            accepted_at="2022.01.01",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[notice, trust, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is True
        assert len(result.hard_stop_flags) >= 2
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS001" in rule_ids
        assert "HS002" in rule_ids

    def test_no_hard_stop(self, analyzer):
        """Hard Stop 없는 정상 케이스"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage, auction])
        result = analyzer.analyze(doc)

        assert result.has_hard_stop is False
        assert len(result.hard_stop_flags) == 0


# === TestConfidence ===


class TestConfidence:
    """신뢰도 산출 테스트"""

    def test_high_confidence(self, analyzer):
        """명확한 케이스 → HIGH"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage, auction])
        result = analyzer.analyze(doc)

        assert result.confidence == Confidence.HIGH

    def test_medium_with_uncertain(self, analyzer):
        """uncertain 1건 → MEDIUM"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        ownership = _make_event(
            event_type=EventType.OWNERSHIP_TRANSFER,
            accepted_at="2015.01.01",
            section=SectionType.GAPGU,
            purpose="소유권이전",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[ownership, mortgage, auction])
        result = analyzer.analyze(doc)

        assert result.confidence == Confidence.MEDIUM

    def test_medium_with_warnings(self, analyzer):
        """parse_warnings 존재 → MEDIUM"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(
            events=[mortgage, auction],
            parse_warnings=["금액 파싱 실패"],
        )
        result = analyzer.analyze(doc)

        assert result.confidence == Confidence.MEDIUM

    def test_low_no_base(self, analyzer):
        """경매개시 없음 → LOW"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        doc = _make_doc(events=[mortgage])
        result = analyzer.analyze(doc)

        assert result.confidence == Confidence.LOW

    def test_low_many_uncertain(self, analyzer):
        """uncertain 3건 이상 → LOW"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
            rank_no=1,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        # 소유권 관련 3건 → uncertain 3건
        o1 = _make_event(
            event_type=EventType.OWNERSHIP_TRANSFER,
            accepted_at="2010.01.01",
            section=SectionType.GAPGU,
            purpose="소유권이전",
            rank_no=1,
        )
        o2 = _make_event(
            event_type=EventType.OWNERSHIP_TRANSFER,
            accepted_at="2012.01.01",
            section=SectionType.GAPGU,
            purpose="소유권이전",
            rank_no=2,
        )
        o3 = _make_event(
            event_type=EventType.OWNERSHIP_TRANSFER,
            accepted_at="2015.01.01",
            section=SectionType.GAPGU,
            purpose="소유권이전",
            rank_no=3,
        )
        doc = _make_doc(events=[o1, o2, o3, mortgage, auction])
        result = analyzer.analyze(doc)

        assert result.confidence == Confidence.LOW

    def test_low_parse_confidence(self, analyzer):
        """parse_confidence LOW → LOW"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(
            events=[mortgage, auction],
            parse_confidence=Confidence.LOW,
        )
        result = analyzer.analyze(doc)

        assert result.confidence == Confidence.LOW


# === TestSummary ===


class TestSummary:
    """요약 생성 테스트"""

    def test_summary_contains_base_info(self, analyzer):
        """요약에 말소기준 정보 포함"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
            purpose="근저당권설정",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage, auction])
        result = analyzer.analyze(doc)

        assert "말소기준권리" in result.summary
        assert "2018.01.01" in result.summary

    def test_summary_no_hard_stop(self, analyzer):
        """Hard Stop 없을 때 요약"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2018.01.01",
            section=SectionType.EULGU,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage, auction])
        result = analyzer.analyze(doc)

        assert "Hard Stop: 없음" in result.summary

    def test_summary_with_hard_stop(self, analyzer):
        """Hard Stop 있을 때 요약"""
        notice = _make_event(
            event_type=EventType.PRELIMINARY_NOTICE,
            section=SectionType.GAPGU,
            purpose="예고등기",
            raw_text="예고등기",
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[notice, auction])
        result = analyzer.analyze(doc)

        assert "Hard Stop:" in result.summary
        assert "예고등기" in result.summary


# === TestFullAnalysis ===


class TestFullAnalysis:
    """통합 분석 테스트 (Fixture 기반)"""

    def test_apt_sample(self, parser, analyzer):
        """아파트 샘플 전체 분석"""
        text = _load_fixture("registry_sample_apt.txt")
        doc = parser.parse_text(text)
        result = analyzer.analyze(doc)

        # 말소기준: 을구 1번 근저당 (2018.03.15)
        assert result.cancellation_base_event is not None
        assert result.cancellation_base_event.event_type == EventType.MORTGAGE
        assert result.cancellation_base_event.accepted_at == "2018.03.15"
        assert "담보권" in result.cancellation_base_reason

        # 소멸: 가압류(2022) + 전세(2021) + 근저당(2022) = 3건 (기준 이후)
        assert len(result.extinguished_rights) == 3
        # 인수: 없음 (전세가 기준 이후 설정이므로 소멸)
        assert len(result.surviving_rights) == 0
        # 불확실: 소유권이전(기준과 동일 접수일) = 1건
        assert len(result.uncertain_rights) == 1

        # Hard Stop 없음
        assert result.has_hard_stop is False

    def test_hardstop_sample(self, parser, analyzer):
        """Hard Stop 샘플 분석"""
        text = _load_fixture("registry_sample_hardstop.txt")
        doc = parser.parse_text(text)
        result = analyzer.analyze(doc)

        # Hard Stop: 예고등기 + 신탁
        assert result.has_hard_stop is True
        rule_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS001" in rule_ids  # 예고등기
        assert "HS002" in rule_ids  # 신탁

    def test_complex_sample(self, parser, analyzer):
        """복잡 케이스 분석"""
        text = _load_fixture("registry_sample_complex.txt")
        doc = parser.parse_text(text)
        result = analyzer.analyze(doc)

        # 말소기준: 을구 1번 근저당 (2015.08.20)
        assert result.cancellation_base_event is not None
        assert result.cancellation_base_event.event_type == EventType.MORTGAGE
        assert result.cancellation_base_event.accepted_at == "2015.08.20"

        # Hard Stop 없음
        assert result.has_hard_stop is False

        # 요약 생성됨
        assert result.summary != ""


# === TestEdgeCases ===


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_events(self, analyzer):
        """이벤트 0건"""
        doc = _make_doc(events=[])
        result = analyzer.analyze(doc)

        assert result.cancellation_base_event is None
        assert len(result.extinguished_rights) == 0
        assert len(result.surviving_rights) == 0
        assert len(result.hard_stop_flags) == 0

    def test_same_date_events(self, analyzer):
        """접수일 동일 이벤트"""
        mortgage = _make_event(
            event_type=EventType.MORTGAGE,
            accepted_at="2020.01.01",
            section=SectionType.EULGU,
            rank_no=1,
        )
        lease = _make_event(
            event_type=EventType.LEASE_RIGHT,
            accepted_at="2020.01.01",
            section=SectionType.EULGU,
            purpose="전세권설정",
            rank_no=2,
        )
        auction = _make_event(
            event_type=EventType.AUCTION_START,
            accepted_at="2023.01.01",
            section=SectionType.GAPGU,
            purpose="임의경매개시결정",
        )
        doc = _make_doc(events=[mortgage, lease, auction])
        result = analyzer.analyze(doc)

        # 동일 접수일이라도 분류 가능해야 함
        assert result.cancellation_base_event is mortgage
        all_classified = (
            result.extinguished_rights
            + result.surviving_rights
            + result.uncertain_rights
        )
        assert len(all_classified) >= 1
