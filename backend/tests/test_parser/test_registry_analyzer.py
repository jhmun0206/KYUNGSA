"""말소기준권리 판별 + Hard Stop 탐지 (HS006~HS008) 테스트"""

import pytest

from app.models.registry import (
    EventType,
    RegistryDocument,
    RegistryEvent,
    SectionType,
    TitleSection,
)
from app.services.parser.registry_analyzer import RegistryAnalyzer


# ──────────────────────────────────────
# 테스트 헬퍼
# ──────────────────────────────────────

analyzer = RegistryAnalyzer()


def _evt(
    event_type: EventType,
    section: SectionType = SectionType.GAPGU,
    accepted_at: str = "2024.01.01",
    purpose: str = "",
    raw_text: str = "",
    canceled: bool = False,
) -> RegistryEvent:
    """테스트용 RegistryEvent 빌더"""
    return RegistryEvent(
        section=section,
        rank_no=1,
        purpose=purpose or event_type.value,
        event_type=event_type,
        accepted_at=accepted_at,
        canceled=canceled,
        raw_text=raw_text or purpose or event_type.value,
    )


def _doc(*events: RegistryEvent) -> RegistryDocument:
    """이벤트 목록으로 RegistryDocument 생성 (section 기준 분리)"""
    all_events = list(events)
    gapgu = [e for e in all_events if e.section == SectionType.GAPGU]
    eulgu = [e for e in all_events if e.section == SectionType.EULGU]
    return RegistryDocument(
        all_events=all_events,
        gapgu_events=gapgu,
        eulgu_events=eulgu,
    )


# ──────────────────────────────────────
# HS006: 소유권이전청구권 가등기
# ──────────────────────────────────────

class TestHS006ProvisionalRegistration:
    """HS006: 소유권이전청구권 가등기 Hard Stop"""

    def test_hs006_triggers(self):
        """소유권이전청구권 가등기 → Hard Stop"""
        auction = _evt(EventType.AUCTION_START, accepted_at="2025.01.01")
        mortgage = _evt(EventType.MORTGAGE, SectionType.EULGU, accepted_at="2023.01.01")
        reg = _evt(
            EventType.PROVISIONAL_REGISTRATION,
            SectionType.GAPGU,
            accepted_at="2022.01.01",
            purpose="소유권이전청구권가등기",
            raw_text="소유권이전청구권가등기",
        )
        result = analyzer.analyze(_doc(mortgage, reg, auction))
        assert result.has_hard_stop is True
        hs_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS006" in hs_ids

    def test_hs006_collateral_registration_excluded(self):
        """담보가등기는 말소 대상 → HS006 제외"""
        auction = _evt(EventType.AUCTION_START, accepted_at="2025.01.01")
        mortgage = _evt(EventType.MORTGAGE, SectionType.EULGU, accepted_at="2023.01.01")
        reg = _evt(
            EventType.PROVISIONAL_REGISTRATION,
            SectionType.GAPGU,
            accepted_at="2022.01.01",
            purpose="담보가등기",
            raw_text="담보가등기 채권자 홍길동",
        )
        result = analyzer.analyze(_doc(mortgage, reg, auction))
        hs_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS006" not in hs_ids


# ──────────────────────────────────────
# HS007: 인수되는 지상권
# ──────────────────────────────────────

class TestHS007Superficies:
    """HS007: 말소기준권리 이전 지상권 Hard Stop"""

    def test_hs007_surviving_superficies_triggers(self):
        """말소기준권리 이전 지상권 → Hard Stop"""
        superficies = _evt(
            EventType.SUPERFICIES, SectionType.EULGU,
            accepted_at="2020.01.01",
            raw_text="지상권설정 목적 건물소유",
        )
        mortgage = _evt(EventType.MORTGAGE, SectionType.EULGU, accepted_at="2022.01.01")
        auction = _evt(EventType.AUCTION_START, accepted_at="2024.01.01")
        result = analyzer.analyze(_doc(superficies, mortgage, auction))
        assert result.has_hard_stop is True
        hs_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS007" in hs_ids

    def test_hs007_extinguished_superficies_no_hard_stop(self):
        """말소기준권리 이후 지상권 → 소멸 → Hard Stop 아님"""
        mortgage = _evt(EventType.MORTGAGE, SectionType.EULGU, accepted_at="2020.01.01")
        superficies = _evt(
            EventType.SUPERFICIES, SectionType.EULGU,
            accepted_at="2022.01.01",  # 말소기준(근저당 2020) 이후
            raw_text="지상권설정",
        )
        auction = _evt(EventType.AUCTION_START, accepted_at="2024.01.01")
        result = analyzer.analyze(_doc(mortgage, superficies, auction))
        hs_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS007" not in hs_ids


# ──────────────────────────────────────
# HS008: 인수되는 지역권
# ──────────────────────────────────────

class TestHS008Easement:
    """HS008: 말소기준권리 이전 지역권 Hard Stop"""

    def test_hs008_surviving_easement_triggers(self):
        """말소기준권리 이전 지역권 → Hard Stop"""
        easement = _evt(
            EventType.EASEMENT, SectionType.EULGU,
            accepted_at="2019.01.01",
            raw_text="지역권설정 통행지역권",
        )
        mortgage = _evt(EventType.MORTGAGE, SectionType.EULGU, accepted_at="2021.01.01")
        auction = _evt(EventType.AUCTION_START, accepted_at="2024.01.01")
        result = analyzer.analyze(_doc(easement, mortgage, auction))
        assert result.has_hard_stop is True
        hs_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS008" in hs_ids

    def test_hs008_extinguished_easement_no_hard_stop(self):
        """말소기준권리 이후 지역권 → 소멸 → Hard Stop 아님"""
        mortgage = _evt(EventType.MORTGAGE, SectionType.EULGU, accepted_at="2019.01.01")
        easement = _evt(
            EventType.EASEMENT, SectionType.EULGU,
            accepted_at="2022.01.01",  # 말소기준(근저당 2019) 이후
            raw_text="지역권설정",
        )
        auction = _evt(EventType.AUCTION_START, accepted_at="2024.01.01")
        result = analyzer.analyze(_doc(mortgage, easement, auction))
        hs_ids = [f.rule_id for f in result.hard_stop_flags]
        assert "HS008" not in hs_ids
