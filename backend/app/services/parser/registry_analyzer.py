"""등기부등본 분석 — 말소기준권리 판별 + 인수/소멸 분류 + Hard Stop 탐지

RegistryParser의 출력(RegistryDocument)을 받아서:
1. 말소기준권리(base right)를 판별한다
2. 각 권리의 인수/소멸/불확실을 분류한다
3. Hard Stop 8종을 탐지한다
4. 신뢰도를 산출하고 요약을 생성한다

※ 이 계산은 RuleEngine이 아니라 여기서 수행한다.
  RuleEngine은 이미 계산된 파생 필드를 소비만 한다.

Hard Stop 종류:
  HS001~HS005: 이벤트 타입/키워드 기반 (순서 무관)
  HS006: 소유권이전청구권 가등기 (담보가등기 제외)
  HS007~HS008: 말소기준권리 이전 지상권/지역권
    → analyze()에서 말소기준권리를 먼저 판별한 뒤 _check_hard_stops()에 전달한다.
"""

import logging

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
from app.services.registry_rules import HARD_STOP_RULES

logger = logging.getLogger(__name__)

# 분류에서 제외할 이벤트 타입 (절차적 이벤트)
_SKIP_TYPES = {
    EventType.AUCTION_START,
    EventType.CANCEL,
    EventType.MORTGAGE_CANCEL,
    EventType.CORRECTION,
    EventType.OTHER,
}

# 말소기준권리 후보가 될 수 있는 담보/압류 타입
_CANCELLATION_BASE_TYPES = {
    EventType.MORTGAGE,
    EventType.PROVISIONAL_SEIZURE,
    EventType.SEIZURE,
}

# 소멸하는 권리 타입 (말소기준 이전이라도 소멸)
_EXTINGUISH_TYPES = {
    EventType.MORTGAGE,
    EventType.MORTGAGE_TRANSFER,
    EventType.SEIZURE,
    EventType.PROVISIONAL_SEIZURE,
    EventType.PROVISIONAL_DISPOSITION,
}

# 인수되는 용익권 타입 (말소기준 이전 설정 시 매수인 인수)
_SURVIVING_TYPES = {
    EventType.LEASE_RIGHT,
    EventType.SUPERFICIES,   # 지상권 — HS007 트리거 후보
    EventType.EASEMENT,      # 지역권 — HS008 트리거 후보
}

# 소유권 관련 (UNCERTAIN 처리)
_OWNERSHIP_TYPES = {
    EventType.OWNERSHIP_TRANSFER,
    EventType.OWNERSHIP_PRESERVATION,
}


class RegistryAnalyzer:
    """RegistryDocument → RegistryAnalysisResult 분석"""

    def analyze(self, doc: RegistryDocument) -> RegistryAnalysisResult:
        """전체 분석 수행

        순서:
          1. 말소기준권리 판단 — HS007~HS008 탐지에 필요하므로 Hard Stop 이전에 수행
          2. Hard Stop 체크 (HS001~HS008)
          3. 인수/소멸 분류
          4. 신뢰도 산출
          5. 결과 조립 + 요약 생성
        """
        all_events = doc.all_events

        # 1. 말소기준권리 판단 (HS007~HS008에 base_event 필요)
        base_event, base_reason = self._find_cancellation_base(all_events)

        # 2. Hard Stop 체크 (base_event 전달)
        hard_stop_flags = self._check_hard_stops(all_events, base_event=base_event)

        # 3. 인수/소멸 분류
        extinguished, surviving, uncertain = self._classify_rights(
            all_events, base_event
        )

        # 4. 신뢰도 산출
        confidence = self._calculate_confidence(
            doc, base_event, hard_stop_flags, len(uncertain)
        )

        # 5. 결과 조립
        result = RegistryAnalysisResult(
            document=doc,
            cancellation_base_event=base_event,
            cancellation_base_reason=base_reason,
            extinguished_rights=extinguished,
            surviving_rights=surviving,
            uncertain_rights=uncertain,
            hard_stop_flags=hard_stop_flags,
            has_hard_stop=len(hard_stop_flags) > 0,
            confidence=confidence,
            warnings=list(doc.parse_warnings),
        )

        # 6. 요약 생성
        result.summary = self._generate_summary(result)

        return result

    def _find_cancellation_base(
        self, events: list[RegistryEvent]
    ) -> tuple[RegistryEvent | None, str | None]:
        """말소기준권리 판단 알고리즘"""
        # 유효 이벤트만 (canceled 제외)
        active = [e for e in events if not e.canceled]
        if not active:
            return None, None

        # 경매개시결정 식별
        auction_starts = [
            e for e in active if e.event_type == EventType.AUCTION_START
        ]
        if not auction_starts:
            return None, "경매개시결정을 찾을 수 없습니다"

        # 가장 빠른 경매개시결정
        auction_start = min(
            auction_starts, key=lambda e: e.accepted_at or ""
        )

        # 경매개시 이전 이벤트
        before_auction = [
            e for e in active
            if e.accepted_at and auction_start.accepted_at
            and e.accepted_at < auction_start.accepted_at
            and e.event_type in _CANCELLATION_BASE_TYPES
        ]

        if not before_auction:
            # 경매개시결정 자체가 기준
            return auction_start, "경매개시결정 이전 담보/압류 이벤트가 없어 경매개시결정 자체가 말소기준권리"

        # 우선순위: 근저당(을구) > 가압류(갑구) > 압류(갑구)
        # 각 타입별 최선순위(가장 빠른 접수일)
        mortgages = [
            e for e in before_auction
            if e.event_type == EventType.MORTGAGE
        ]
        if mortgages:
            base = min(mortgages, key=lambda e: e.accepted_at or "")
            return base, "경매개시결정 이전 최선순위 담보권 (을구)"

        seizures_prov = [
            e for e in before_auction
            if e.event_type == EventType.PROVISIONAL_SEIZURE
        ]
        if seizures_prov:
            base = min(seizures_prov, key=lambda e: e.accepted_at or "")
            return base, "경매개시결정 이전 최선순위 가압류 (갑구)"

        seizures = [
            e for e in before_auction
            if e.event_type == EventType.SEIZURE
        ]
        if seizures:
            base = min(seizures, key=lambda e: e.accepted_at or "")
            return base, "경매개시결정 이전 최선순위 압류 (갑구)"

        # fallback (이론상 도달 불가)
        return auction_start, "경매개시결정 자체가 말소기준권리 (fallback)"

    def _classify_rights(
        self,
        events: list[RegistryEvent],
        base_event: RegistryEvent | None,
    ) -> tuple[list[AnalyzedRight], list[AnalyzedRight], list[AnalyzedRight]]:
        """인수/소멸/불확실 분류"""
        extinguished: list[AnalyzedRight] = []
        surviving: list[AnalyzedRight] = []
        uncertain: list[AnalyzedRight] = []

        if not base_event:
            return extinguished, surviving, uncertain

        base_date = base_event.accepted_at or ""

        for event in events:
            # 말소된 이벤트 건너뜀
            if event.canceled:
                continue
            # 절차적 이벤트 건너뜀
            if event.event_type in _SKIP_TYPES:
                continue
            # 말소기준권리 자체 건너뜀
            if event is base_event:
                continue

            event_date = event.accepted_at or ""

            # 말소기준 이후 설정 → 소멸
            if event_date > base_date:
                extinguished.append(AnalyzedRight(
                    event=event,
                    classification=RightClassification.EXTINGUISHED,
                    reason=f"말소기준권리({base_date}) 이후 설정",
                ))
                continue

            # 말소기준 이전 설정
            if event.event_type in _EXTINGUISH_TYPES:
                extinguished.append(AnalyzedRight(
                    event=event,
                    classification=RightClassification.EXTINGUISHED,
                    reason="담보권/압류 → 매각으로 소멸",
                ))
            elif event.event_type in _SURVIVING_TYPES:
                surviving.append(AnalyzedRight(
                    event=event,
                    classification=RightClassification.SURVIVING,
                    reason="말소기준권리 이전 용익권 → 매수인 인수",
                ))
            elif event.event_type in _OWNERSHIP_TYPES:
                uncertain.append(AnalyzedRight(
                    event=event,
                    classification=RightClassification.UNCERTAIN,
                    reason="소유권 관련 등기 → 수동 검토 필요",
                ))
            else:
                uncertain.append(AnalyzedRight(
                    event=event,
                    classification=RightClassification.UNCERTAIN,
                    reason=f"분류 불확실 ({event.event_type.value}) → 수동 검토 필요",
                ))

        return extinguished, surviving, uncertain

    def _check_hard_stops(
        self,
        events: list[RegistryEvent],
        *,
        base_event: RegistryEvent | None = None,
    ) -> list[HardStopFlag]:
        """Hard Stop 8종 탐지

        Args:
            events: 전체 이벤트 목록
            base_event: 말소기준권리 (HS007~HS008 타이밍 판별용)
        """
        flags: list[HardStopFlag] = []
        active_events = [e for e in events if not e.canceled]
        base_date = (
            base_event.accepted_at
            if base_event and base_event.accepted_at
            else None
        )

        for rule in HARD_STOP_RULES:
            # requires_before_base=True인데 base_date 미확인 → 이 룰 스킵
            # (말소기준 판별 불가 = 신뢰도 LOW로 별도 처리됨)
            if rule.get("requires_before_base") and base_date is None:
                continue

            for event in active_events:
                matched = False

                # event_type 매칭
                if rule["event_types"] and event.event_type in rule["event_types"]:
                    matched = True

                # keyword 매칭 (raw_text에서)
                if not matched:
                    for kw in rule.get("keywords", []):
                        if kw in event.raw_text:
                            matched = True
                            break

                if not matched:
                    continue

                # exclude_keywords 체크 (HS006: 담보가등기 제외)
                exclude = rule.get("exclude_keywords", [])
                if exclude:
                    combined = (event.purpose or "") + event.raw_text
                    if any(kw in combined for kw in exclude):
                        matched = False

                if not matched:
                    continue

                # requires_before_base 체크 (HS007~HS008)
                if rule.get("requires_before_base") and base_date:
                    event_date = event.accepted_at or ""
                    if not event_date or event_date >= base_date:
                        # 말소기준 이후 설정 → 소멸 → Hard Stop 아님
                        continue

                flags.append(HardStopFlag(
                    rule_id=rule["id"],
                    name=rule["name"],
                    description=rule["description"],
                    event=event,
                ))
                break  # 같은 룰은 첫 매칭만 (중복 방지)

        return flags

    @staticmethod
    def _calculate_confidence(
        doc: RegistryDocument,
        base_event: RegistryEvent | None,
        hard_stops: list[HardStopFlag],
        uncertain_count: int,
    ) -> Confidence:
        """신뢰도 산출"""
        # LOW 조건
        if doc.parse_confidence == Confidence.LOW:
            return Confidence.LOW
        if base_event is None:
            return Confidence.LOW
        if uncertain_count >= 3:
            return Confidence.LOW

        # MEDIUM 조건
        if doc.parse_warnings:
            return Confidence.MEDIUM
        if uncertain_count >= 1:
            return Confidence.MEDIUM

        # HIGH
        return Confidence.HIGH

    @staticmethod
    def _generate_summary(result: RegistryAnalysisResult) -> str:
        """사람이 읽을 요약 텍스트 생성"""
        lines: list[str] = []

        # 소재지
        if result.document.title and result.document.title.address:
            lines.append(f"소재지: {result.document.title.address}")

        # 말소기준권리
        if result.cancellation_base_event:
            base = result.cancellation_base_event
            lines.append(
                f"말소기준권리: {base.section.value} {base.rank_no}번 "
                f"{base.purpose} ({base.accepted_at})"
            )
            if result.cancellation_base_reason:
                lines.append(f"  └ 사유: {result.cancellation_base_reason}")
        else:
            lines.append("말소기준권리: 판단 불가")

        # 소멸 권리
        if result.extinguished_rights:
            lines.append(f"소멸 권리: {len(result.extinguished_rights)}건")
            for ar in result.extinguished_rights:
                e = ar.event
                amt = f" {e.amount:,}원" if e.amount else ""
                lines.append(
                    f"  - {e.section.value}{e.rank_no} {e.purpose}{amt}"
                )

        # 인수 권리
        if result.surviving_rights:
            lines.append(f"인수 권리: {len(result.surviving_rights)}건")
            for ar in result.surviving_rights:
                e = ar.event
                amt = f" {e.amount:,}원" if e.amount else ""
                lines.append(
                    f"  - {e.section.value}{e.rank_no} {e.purpose}{amt}"
                )

        # 불확실
        if result.uncertain_rights:
            lines.append(f"불확실 (수동 검토): {len(result.uncertain_rights)}건")

        # Hard Stop
        if result.has_hard_stop:
            names = [f.name for f in result.hard_stop_flags]
            lines.append(f"Hard Stop: {', '.join(names)}")
        else:
            lines.append("Hard Stop: 없음")

        lines.append(f"신뢰도: {result.confidence.value}")

        return "\n".join(lines)
