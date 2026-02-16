"""법률 리스크 점수 엔진 (5C)

등기부등본 분석 결과(RegistryAnalysisResult)와 경매 물건 정보(AuctionCaseDetail)를
입력받아 법률 리스크 점수(0~100, 높을수록 안전)를 산출한다.

구조: 3축 가중 합산 × 신뢰도 계수
  base_score = mortgage*0.40 + seizure*0.30 + surviving*0.30
  final_score = base_score × confidence_multiplier
  Hard Stop → final_score = 0

근거:
  - 채권최고액 = 실대출의 110~120%. 아파트/꼬마빌딩 곡선 분리.
  - 가압류와 가처분은 질적으로 다르므로 별도 처리.
  - 신뢰도 LOW이면 전체 점수가 의미 없으므로 계수형 적용.
"""

from __future__ import annotations

import logging

from app.models.auction import AuctionCaseDetail
from app.models.registry import (
    Confidence,
    EventType,
    RegistryAnalysisResult,
    RegistryEvent,
)
from app.models.scores import LegalScoreResult, LegalSubScores

logger = logging.getLogger(__name__)

# 소유권 관련 가처분 키워드
_DISPOSITION_KEYWORDS = frozenset(
    ["처분금지", "철거", "토지인도", "건물철거", "인도청구"]
)


class LegalScorer:
    """법률 리스크 점수 산출기"""

    # 3축 가중치
    W_MORTGAGE = 0.40
    W_SEIZURE = 0.30
    W_SURVIVING = 0.30

    # 신뢰도 계수
    CONFIDENCE_MULTIPLIER: dict[str, float] = {
        "HIGH": 1.0,
        "MEDIUM": 0.8,
        "LOW": 0.6,
    }

    # 주거용 property_type 키워드
    RESIDENTIAL_TYPES = frozenset(
        {"아파트", "오피스텔", "주상복합", "연립", "빌라", "주택"}
    )

    def score(
        self,
        case: AuctionCaseDetail,
        registry_analysis: RegistryAnalysisResult,
    ) -> LegalScoreResult:
        """법률 리스크 점수 산출

        Args:
            case: 경매 물건 상세 정보
            registry_analysis: 등기부등본 분석 결과

        Returns:
            LegalScoreResult (0~100, 높을수록 안전)
        """
        warnings: list[str] = []
        details: dict = {}

        appraised = case.appraised_value
        is_residential = self._is_residential(case.property_type)
        all_events = registry_analysis.document.all_events

        # --- 데이터 추출 ---
        active_mortgages = self._extract_active_mortgages(all_events)
        active_seizures = self._extract_active_seizures(all_events)
        dispositions = self._extract_dispositions(all_events)

        total_mortgage = self._sum_amounts(active_mortgages)
        seizure_count = len(active_seizures)
        seizure_total = self._sum_amounts(active_seizures)
        disposition_count = len(dispositions)

        surviving_amount = self._sum_amounts_from_rights(
            registry_analysis.surviving_rights
        )
        uncertain_count = len(registry_analysis.uncertain_rights)

        # amount=None 경고
        mortgage_none_count = sum(
            1 for e in active_mortgages if e.amount is None
        )
        seizure_none_count = sum(
            1 for e in active_seizures if e.amount is None
        )
        if mortgage_none_count:
            warnings.append(
                f"금액 미상 근저당 {mortgage_none_count}건 — 실제 부담이 더 클 수 있음"
            )
        if seizure_none_count:
            warnings.append(
                f"금액 미상 가압류 {seizure_none_count}건 — 실제 부담이 더 클 수 있음"
            )

        # --- 세부 점수 계산 ---
        # (1) 근저당 비율
        mortgage_score, mortgage_detail = self._calc_mortgage_ratio_score(
            total_mortgage, appraised, is_residential
        )
        details["mortgage"] = mortgage_detail

        # (2) 가압류/가처분
        seizure_score, seizure_detail, seizure_warnings = (
            self._calc_seizure_score(
                seizure_count, seizure_total, disposition_count, appraised
            )
        )
        details["seizure"] = seizure_detail
        warnings.extend(seizure_warnings)

        # (3) 인수 권리
        surviving_score, surviving_detail, needs_review = (
            self._calc_surviving_score(
                surviving_amount, uncertain_count, appraised
            )
        )
        details["surviving"] = surviving_detail
        if uncertain_count > 0:
            warnings.append("불확실 권리 존재 — 전문가 검토 권장")

        # --- 합산 ---
        base_score = (
            mortgage_score * self.W_MORTGAGE
            + seizure_score * self.W_SEIZURE
            + surviving_score * self.W_SURVIVING
        )
        base_score = round(base_score, 1)

        # 신뢰도 계수
        confidence = registry_analysis.confidence
        multiplier = self._get_confidence_multiplier(confidence)

        final_score = round(base_score * multiplier, 1)
        final_score = max(0.0, min(100.0, final_score))

        # Hard Stop 오버라이드
        has_hard_stop = registry_analysis.has_hard_stop
        if has_hard_stop:
            final_score = 0.0

        # needs_expert_review 판단
        needs_expert = needs_review or disposition_count > 0
        if needs_expert:
            warnings.append("전문가 검토 필요")

        # appraised_value == 0 경고
        if appraised <= 0:
            warnings.append("감정가 미확인 — 비율 기반 점수 산출 불가")

        details["property_type"] = case.property_type
        details["is_residential"] = is_residential
        details["appraised_value"] = appraised
        details["confidence"] = confidence.value

        return LegalScoreResult(
            score=final_score,
            base_score=base_score,
            sub_scores=LegalSubScores(
                mortgage_ratio_score=mortgage_score,
                seizure_score=seizure_score,
                surviving_rights_score=surviving_score,
            ),
            confidence_multiplier=multiplier,
            has_hard_stop=has_hard_stop,
            needs_expert_review=needs_expert,
            confidence=confidence.value,
            warnings=warnings,
            details=details,
        )

    # ──────────────────────────────────────
    # 세부 점수 계산
    # ──────────────────────────────────────

    @staticmethod
    def _calc_mortgage_ratio_score(
        total_mortgage: int,
        appraised_value: int,
        is_residential: bool,
    ) -> tuple[float, dict]:
        """근저당/감정가 비율 점수 (0~100)

        아파트: (0, 0.6, 0.8, 1.0) → (100, 80, 50, 25, 0)
        꼬마빌딩: (0, 0.5, 0.7, 1.0) → (100, 80, 50, 20, 0)
        """
        detail = {
            "total_mortgage": total_mortgage,
            "appraised_value": appraised_value,
            "is_residential": is_residential,
        }

        if appraised_value <= 0:
            detail["ratio"] = None
            detail["reason"] = "감정가 0 이하"
            return 0.0, detail

        ratio = total_mortgage / appraised_value
        detail["ratio"] = round(ratio, 4)

        if ratio == 0:
            score = 100.0
        elif is_residential:
            score = _lerp_mortgage_residential(ratio)
        else:
            score = _lerp_mortgage_commercial(ratio)

        score = max(0.0, min(100.0, round(score, 1)))
        detail["score"] = score
        return score, detail

    @staticmethod
    def _calc_seizure_score(
        seizure_count: int,
        seizure_total: int,
        disposition_count: int,
        appraised_value: int,
    ) -> tuple[float, dict, list[str]]:
        """가압류/가처분 점수 (0~100)"""
        detail: dict = {
            "seizure_count": seizure_count,
            "seizure_total": seizure_total,
            "disposition_count": disposition_count,
        }
        warnings: list[str] = []

        # 건수 감점
        if seizure_count == 0:
            count_penalty = 0.0
        elif seizure_count == 1:
            count_penalty = 20.0
        elif seizure_count == 2:
            count_penalty = 35.0
        else:
            count_penalty = 50.0

        # 금액 감점
        if appraised_value <= 0:
            amount_penalty = 0.0
            detail["seizure_ratio"] = None
        else:
            s_ratio = seizure_total / appraised_value
            detail["seizure_ratio"] = round(s_ratio, 4)
            amount_penalty = _calc_seizure_amount_penalty(s_ratio)

        # 총 감점 캡 = 70
        total_penalty = min(70.0, count_penalty + amount_penalty)

        # 가처분 별도 감점
        disposition_penalty = 0.0
        if disposition_count > 0:
            disposition_penalty = 60.0
            warnings.append(
                f"소유권 관련 가처분 {disposition_count}건 감지 "
                "— Hard Stop에 준하는 리스크"
            )

        score = max(0.0, 100.0 - total_penalty - disposition_penalty)
        score = round(score, 1)

        detail["count_penalty"] = count_penalty
        detail["amount_penalty"] = round(amount_penalty, 1)
        detail["disposition_penalty"] = disposition_penalty
        detail["score"] = score

        return score, detail, warnings

    @staticmethod
    def _calc_surviving_score(
        surviving_amount: int,
        uncertain_count: int,
        appraised_value: int,
    ) -> tuple[float, dict, bool]:
        """인수 권리 부담 점수 (0~100)

        Returns:
            (score, detail, needs_expert_review)
        """
        detail: dict = {
            "surviving_amount": surviving_amount,
            "uncertain_count": uncertain_count,
        }
        needs_review = False

        # 비율 감점
        if appraised_value <= 0:
            ratio_penalty = 0.0
            detail["surviving_ratio"] = None
        else:
            s_ratio = surviving_amount / appraised_value
            detail["surviving_ratio"] = round(s_ratio, 4)
            ratio_penalty = _calc_surviving_ratio_penalty(s_ratio)

            if s_ratio >= 0.5:
                needs_review = True

        # 불확실 감점
        uncertain_penalty = min(30.0, uncertain_count * 10.0)

        score = max(0.0, 100.0 - ratio_penalty - uncertain_penalty)
        score = round(score, 1)

        detail["ratio_penalty"] = round(ratio_penalty, 1)
        detail["uncertain_penalty"] = uncertain_penalty
        detail["score"] = score
        detail["needs_review"] = needs_review

        return score, detail, needs_review

    @classmethod
    def _get_confidence_multiplier(cls, confidence: Confidence) -> float:
        """신뢰도 계수 반환"""
        return cls.CONFIDENCE_MULTIPLIER.get(confidence.value, 0.6)

    # ──────────────────────────────────────
    # 데이터 추출 헬퍼
    # ──────────────────────────────────────

    @classmethod
    def _is_residential(cls, property_type: str) -> bool:
        """주거용 물건 여부 판별

        판별 불가 시 False (보수적으로 꼬마빌딩 곡선 적용).
        """
        if not property_type:
            return False
        for rtype in cls.RESIDENTIAL_TYPES:
            if rtype in property_type:
                return True
        return False

    @staticmethod
    def _extract_active_mortgages(
        events: list[RegistryEvent],
    ) -> list[RegistryEvent]:
        """활성 근저당 이벤트 추출"""
        return [
            e
            for e in events
            if e.event_type == EventType.MORTGAGE and not e.canceled
        ]

    @staticmethod
    def _extract_active_seizures(
        events: list[RegistryEvent],
    ) -> list[RegistryEvent]:
        """활성 가압류/압류 이벤트 추출"""
        return [
            e
            for e in events
            if e.event_type
            in (EventType.PROVISIONAL_SEIZURE, EventType.SEIZURE)
            and not e.canceled
        ]

    @staticmethod
    def _extract_dispositions(
        events: list[RegistryEvent],
    ) -> list[RegistryEvent]:
        """소유권 관련 가처분 이벤트 추출

        EventType.PROVISIONAL_DISPOSITION + purpose 키워드 매칭.
        """
        result: list[RegistryEvent] = []
        for e in events:
            if e.canceled:
                continue
            if e.event_type == EventType.PROVISIONAL_DISPOSITION:
                # 소유권/물권 관련 키워드 확인
                purpose = e.purpose or ""
                raw = e.raw_text or ""
                text = purpose + raw
                if any(kw in text for kw in _DISPOSITION_KEYWORDS):
                    result.append(e)
                else:
                    # 키워드 없어도 가처분 자체가 위험
                    result.append(e)
        return result

    @staticmethod
    def _sum_amounts(events: list[RegistryEvent]) -> int:
        """이벤트 목록의 금액 합산 (amount=None은 0으로 처리)"""
        return sum(e.amount for e in events if e.amount is not None)

    @staticmethod
    def _sum_amounts_from_rights(rights: list) -> int:
        """AnalyzedRight 목록의 금액 합산"""
        total = 0
        for ar in rights:
            if ar.event.amount is not None:
                total += ar.event.amount
        return total


# ──────────────────────────────────────
# 선형 보간 헬퍼 (모듈 내부)
# ──────────────────────────────────────


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """선형 보간: x가 [x0, x1] 구간에서 y를 [y0, y1] 사이로 보간"""
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def _lerp_mortgage_residential(ratio: float) -> float:
    """아파트 근저당 비율 곡선

    ratio ≤ 0.6 → 100→80
    0.6 < ratio ≤ 0.8 → 80→50
    0.8 < ratio ≤ 1.0 → 50→25
    ratio > 1.0 → 25→0
    """
    if ratio <= 0.6:
        return _lerp(ratio, 0.0, 0.6, 100.0, 80.0)
    if ratio <= 0.8:
        return _lerp(ratio, 0.6, 0.8, 80.0, 50.0)
    if ratio <= 1.0:
        return _lerp(ratio, 0.8, 1.0, 50.0, 25.0)
    # ratio > 1.0: 25→0 (ratio 2.0에서 0)
    return max(0.0, _lerp(ratio, 1.0, 2.0, 25.0, 0.0))


def _lerp_mortgage_commercial(ratio: float) -> float:
    """꼬마빌딩 근저당 비율 곡선

    ratio ≤ 0.5 → 100→80
    0.5 < ratio ≤ 0.7 → 80→50
    0.7 < ratio ≤ 1.0 → 50→20
    ratio > 1.0 → 20→0
    """
    if ratio <= 0.5:
        return _lerp(ratio, 0.0, 0.5, 100.0, 80.0)
    if ratio <= 0.7:
        return _lerp(ratio, 0.5, 0.7, 80.0, 50.0)
    if ratio <= 1.0:
        return _lerp(ratio, 0.7, 1.0, 50.0, 20.0)
    # ratio > 1.0: 20→0 (ratio 2.0에서 0)
    return max(0.0, _lerp(ratio, 1.0, 2.0, 20.0, 0.0))


def _calc_seizure_amount_penalty(ratio: float) -> float:
    """가압류 금액 감점 (계단형 선형 보간)

    ≤ 0.05 → 5
    0.05~0.2 → 10~25
    0.2~0.5 → 25~40
    > 0.5 → 40~50 (캡)
    """
    if ratio <= 0:
        return 0.0
    if ratio <= 0.05:
        return 5.0
    if ratio <= 0.2:
        return _lerp(ratio, 0.05, 0.2, 10.0, 25.0)
    if ratio <= 0.5:
        return _lerp(ratio, 0.2, 0.5, 25.0, 40.0)
    # > 0.5: 40→50 캡
    return min(50.0, _lerp(ratio, 0.5, 1.0, 40.0, 50.0))


def _calc_surviving_ratio_penalty(ratio: float) -> float:
    """인수 권리 비율 감점

    ≤ 0.1 → 0~10
    0.1~0.3 → 10~40
    0.3~0.5 → 40~70
    > 0.5 → 70~100
    """
    if ratio <= 0:
        return 0.0
    if ratio <= 0.1:
        return _lerp(ratio, 0.0, 0.1, 0.0, 10.0)
    if ratio <= 0.3:
        return _lerp(ratio, 0.1, 0.3, 10.0, 40.0)
    if ratio <= 0.5:
        return _lerp(ratio, 0.3, 0.5, 40.0, 70.0)
    # > 0.5: 70→100
    return min(100.0, _lerp(ratio, 0.5, 1.0, 70.0, 100.0))
