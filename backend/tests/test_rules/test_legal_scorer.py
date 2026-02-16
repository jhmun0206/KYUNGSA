"""LegalScorer 단위 테스트

법률 리스크 점수 엔진의 각 세부 점수 계산과 통합 산출을 검증한다.
"""

import pytest

from app.models.auction import AuctionCaseDetail
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
from app.services.rules.legal_scorer import LegalScorer


# ──────────────────────────────────────
# 테스트 헬퍼
# ──────────────────────────────────────


def _make_event(
    event_type: EventType = EventType.MORTGAGE,
    amount: int | None = None,
    canceled: bool = False,
    purpose: str = "",
    raw_text: str = "",
) -> RegistryEvent:
    """테스트용 등기 이벤트 생성"""
    return RegistryEvent(
        section=SectionType.EULGU if event_type == EventType.MORTGAGE else SectionType.GAPGU,
        rank_no=1,
        purpose=purpose or event_type.value,
        event_type=event_type,
        accepted_at="2024.01.01",
        amount=amount,
        canceled=canceled,
        raw_text=raw_text or purpose or event_type.value,
    )


def _make_analysis(
    events: list[RegistryEvent] | None = None,
    hard_stop: bool = False,
    hard_stop_flags: list[HardStopFlag] | None = None,
    surviving_rights: list[AnalyzedRight] | None = None,
    uncertain_rights: list[AnalyzedRight] | None = None,
    confidence: Confidence = Confidence.HIGH,
) -> RegistryAnalysisResult:
    """테스트용 등기부 분석 결과 생성"""
    all_events = events or []
    doc = RegistryDocument(
        all_events=all_events,
        gapgu_events=[e for e in all_events if e.section == SectionType.GAPGU],
        eulgu_events=[e for e in all_events if e.section == SectionType.EULGU],
    )
    return RegistryAnalysisResult(
        document=doc,
        hard_stop_flags=hard_stop_flags or [],
        has_hard_stop=hard_stop,
        surviving_rights=surviving_rights or [],
        uncertain_rights=uncertain_rights or [],
        confidence=confidence,
    )


def _make_case(
    appraised_value: int = 500_000_000,
    property_type: str = "아파트",
    **kwargs,
) -> AuctionCaseDetail:
    """테스트용 경매 물건 생성"""
    defaults = {
        "case_number": "2024타경12345",
        "court": "서울중앙지방법원",
        "address": "서울특별시 강남구 역삼동 123-4",
        "minimum_bid": appraised_value * 8 // 10,
    }
    defaults.update(kwargs)
    return AuctionCaseDetail(
        appraised_value=appraised_value,
        property_type=property_type,
        **defaults,
    )


def _make_surviving_right(
    amount: int | None = None,
    event_type: EventType = EventType.LEASE_RIGHT,
) -> AnalyzedRight:
    """테스트용 인수 권리 생성"""
    return AnalyzedRight(
        event=_make_event(event_type=event_type, amount=amount),
        classification=RightClassification.SURVIVING,
        reason="테스트",
    )


def _make_uncertain_right(
    event_type: EventType = EventType.OTHER,
) -> AnalyzedRight:
    """테스트용 불확실 권리 생성"""
    return AnalyzedRight(
        event=_make_event(event_type=event_type),
        classification=RightClassification.UNCERTAIN,
        reason="불확실 테스트",
    )


# ──────────────────────────────────────
# 근저당 비율 점수 테스트
# ──────────────────────────────────────

scorer = LegalScorer()


class TestMortgageRatioScore:
    """근저당/감정가 비율 점수 테스트"""

    def test_no_mortgage(self):
        """근저당 없으면 100점"""
        score, detail = scorer._calc_mortgage_ratio_score(0, 500_000_000, True)
        assert score == 100.0

    def test_apt_ratio_50pct(self):
        """아파트 ratio=0.5 → 안전 구간 (~87)"""
        # ratio 0.5는 0~0.6 구간: 100→80, 선형 보간
        # _lerp(0.5, 0.0, 0.6, 100, 80) = 100 + (0.5/0.6) * (80-100) = 100 - 16.67 ≈ 83.3
        score, _ = scorer._calc_mortgage_ratio_score(
            250_000_000, 500_000_000, True
        )
        assert 80.0 < score < 90.0

    def test_apt_ratio_60pct(self):
        """아파트 ratio=0.6 → 경계점 = 80"""
        score, _ = scorer._calc_mortgage_ratio_score(
            300_000_000, 500_000_000, True
        )
        assert score == 80.0

    def test_apt_ratio_80pct(self):
        """아파트 ratio=0.8 → 경계점 = 50"""
        score, _ = scorer._calc_mortgage_ratio_score(
            400_000_000, 500_000_000, True
        )
        assert score == 50.0

    def test_building_ratio_50pct(self):
        """꼬마빌딩 ratio=0.5 → 경계점 = 80"""
        score, _ = scorer._calc_mortgage_ratio_score(
            250_000_000, 500_000_000, False
        )
        assert score == 80.0

    def test_building_ratio_70pct(self):
        """꼬마빌딩 ratio=0.7 → 경계점 = 50"""
        score, _ = scorer._calc_mortgage_ratio_score(
            350_000_000, 500_000_000, False
        )
        assert score == 50.0

    def test_building_ratio_100pct(self):
        """꼬마빌딩 ratio=1.0 → 경계점 = 20"""
        score, _ = scorer._calc_mortgage_ratio_score(
            500_000_000, 500_000_000, False
        )
        assert score == 20.0

    def test_zero_appraised(self):
        """감정가 0이면 점수 0 + 방어"""
        score, detail = scorer._calc_mortgage_ratio_score(100_000_000, 0, True)
        assert score == 0.0
        assert detail["reason"] == "감정가 0 이하"


# ──────────────────────────────────────
# 가압류/가처분 점수 테스트
# ──────────────────────────────────────


class TestSeizureScore:
    """가압류/가처분 점수 테스트"""

    def test_no_seizures(self):
        """가압류 없으면 100점"""
        score, _, _ = scorer._calc_seizure_score(0, 0, 0, 500_000_000)
        assert score == 100.0

    def test_one_small(self):
        """가압류 1건 소액 → 건수감점 20 + 소액감점"""
        # 1건, 금액 1000만원, 감정가 5억 → ratio = 0.02 → 금액감점 5
        score, detail, _ = scorer._calc_seizure_score(
            1, 10_000_000, 0, 500_000_000
        )
        assert detail["count_penalty"] == 20.0
        # 총 감점 25: 100 - 25 = 75
        assert score == 75.0

    def test_three_large(self):
        """가압류 3건 고액 → 건수감점 50 + 금액감점 → 총 감점 캡 70 → 30점"""
        # 3건, 금액 3억, 감정가 5억 → ratio=0.6
        # 건수감점=50, 금액감점=~44 → 합계 94, 캡 70 → score=30
        score, _, _ = scorer._calc_seizure_score(
            3, 300_000_000, 0, 500_000_000
        )
        assert score == 30.0

    def test_no_amount(self):
        """금액 0인 가압류 → 건수 감점만 적용"""
        score, _, _ = scorer._calc_seizure_score(2, 0, 0, 500_000_000)
        assert score == 65.0  # 100 - 35

    def test_disposition_hard_penalty(self):
        """소유권 가처분 1건 → -60 강력 감점 + 경고"""
        score, detail, warnings = scorer._calc_seizure_score(
            0, 0, 1, 500_000_000
        )
        assert score <= 40.0  # 100 - 60
        assert detail["disposition_penalty"] == 60.0
        assert any("가처분" in w for w in warnings)


# ──────────────────────────────────────
# 인수 권리 부담 점수 테스트
# ──────────────────────────────────────


class TestSurvivingScore:
    """인수 권리 부담 점수 테스트"""

    def test_no_surviving(self):
        """인수 권리 없으면 100점"""
        score, _, needs = scorer._calc_surviving_score(0, 0, 500_000_000)
        assert score == 100.0
        assert needs is False

    def test_ratio_20pct(self):
        """인수 ratio=0.2 → 중간 감점"""
        # ratio 0.2는 0.1~0.3 구간: 감점 10→40, lerp(0.2, 0.1, 0.3, 10, 40) = 25
        score, _, _ = scorer._calc_surviving_score(
            100_000_000, 0, 500_000_000
        )
        assert 70.0 <= score <= 80.0  # 100 - 25 = 75

    def test_ratio_50pct_flag(self):
        """인수 ratio=0.5 → 감점 70 + needs_expert_review"""
        score, _, needs = scorer._calc_surviving_score(
            250_000_000, 0, 500_000_000
        )
        assert score <= 30.0  # 100 - 70 = 30
        assert needs is True

    def test_uncertain_rights(self):
        """불확실 권리 2건 → 추가 감점 20"""
        score, detail, _ = scorer._calc_surviving_score(0, 2, 500_000_000)
        assert detail["uncertain_penalty"] == 20.0
        assert score == 80.0  # 100 - 0 - 20


# ──────────────────────────────────────
# 신뢰도 계수 테스트
# ──────────────────────────────────────


class TestConfidenceMultiplier:
    """신뢰도 계수 테스트"""

    def test_high(self):
        """HIGH → 1.0"""
        assert scorer._get_confidence_multiplier(Confidence.HIGH) == 1.0

    def test_medium(self):
        """MEDIUM → 0.8"""
        assert scorer._get_confidence_multiplier(Confidence.MEDIUM) == 0.8

    def test_low(self):
        """LOW → 0.6"""
        assert scorer._get_confidence_multiplier(Confidence.LOW) == 0.6


# ──────────────────────────────────────
# Hard Stop 테스트
# ──────────────────────────────────────


class TestHardStop:
    """Hard Stop 시 점수 0 테스트"""

    def test_hard_stop_zero(self):
        """Hard Stop → 최종 점수 0"""
        case = _make_case()
        analysis = _make_analysis(hard_stop=True)
        result = scorer.score(case, analysis)
        assert result.score == 0.0
        assert result.has_hard_stop is True

    def test_sub_scores_still_computed(self):
        """Hard Stop이어도 세부 점수는 계산됨 (투명성)"""
        events = [
            _make_event(EventType.MORTGAGE, amount=200_000_000),
        ]
        case = _make_case()
        analysis = _make_analysis(events=events, hard_stop=True)
        result = scorer.score(case, analysis)
        assert result.score == 0.0
        # 세부 점수는 0이 아님
        assert result.sub_scores.mortgage_ratio_score > 0
        assert result.base_score > 0


# ──────────────────────────────────────
# 통합 테스트
# ──────────────────────────────────────


class TestIntegration:
    """LegalScorer 통합 테스트"""

    def test_clean_apartment(self):
        """깨끗한 아파트 → 85점 이상"""
        events = [
            _make_event(EventType.MORTGAGE, amount=200_000_000),  # ratio=0.4
            _make_event(EventType.AUCTION_START),
        ]
        case = _make_case(property_type="아파트", appraised_value=500_000_000)
        analysis = _make_analysis(events=events, confidence=Confidence.HIGH)

        result = scorer.score(case, analysis)
        assert result.score >= 85.0
        assert result.has_hard_stop is False
        assert result.needs_expert_review is False
        assert result.confidence == "HIGH"
        assert result.confidence_multiplier == 1.0

    def test_risky_building(self):
        """위험한 꼬마빌딩 → 10점 이하"""
        events = [
            _make_event(EventType.MORTGAGE, amount=450_000_000),  # ratio=0.9
            _make_event(EventType.PROVISIONAL_SEIZURE, amount=200_000_000),
            _make_event(EventType.PROVISIONAL_SEIZURE, amount=100_000_000),
            _make_event(EventType.PROVISIONAL_SEIZURE, amount=50_000_000),
            _make_event(
                EventType.PROVISIONAL_DISPOSITION,
                purpose="처분금지가처분",
                raw_text="처분금지가처분",
            ),
            _make_event(EventType.AUCTION_START),
        ]
        surviving = [
            _make_surviving_right(amount=200_000_000),
        ]
        case = _make_case(property_type="상가", appraised_value=500_000_000)
        analysis = _make_analysis(
            events=events,
            surviving_rights=surviving,
            confidence=Confidence.MEDIUM,
        )

        result = scorer.score(case, analysis)
        # mortgage 30*0.4 + seizure 0*0.3 + surviving 45*0.3 = 25.5 * 0.8 = 20.4
        assert result.score <= 25.0
        assert result.needs_expert_review is True
        assert result.confidence_multiplier == 0.8
        assert len(result.warnings) > 0
