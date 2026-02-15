"""1단 필터 엔진

EnrichedCase를 평가하여 RED / YELLOW / GREEN으로 분류한다.
- RED: 하나라도 매칭 → passed=False
- YELLOW: RED 없이 YELLOW만 매칭 → passed=True
- GREEN: 아무것도 매칭 안 됨 → passed=True
- RED+YELLOW 동시 → RED 우선 (YELLOW 사유도 기록)
"""

import logging

from app.models.enriched_case import (
    EnrichedCase,
    FilterColor,
    FilterResult,
    RuleMatch,
)
from app.services.filter_rules import RED_RULES, YELLOW_RULES

logger = logging.getLogger(__name__)


class FilterEngine:
    """1단 필터 엔진"""

    def evaluate(self, ec: EnrichedCase) -> FilterResult:
        """EnrichedCase를 평가하여 FilterResult 반환"""
        matched: list[RuleMatch] = []
        red_matched = False
        yellow_matched = False

        # RED 룰 평가
        for rule_id, rule_name, rule_fn in RED_RULES:
            reason = rule_fn(ec)
            if reason is not None:
                matched.append(RuleMatch(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    description=reason,
                ))
                red_matched = True

        # YELLOW 룰 평가 (RED 여부와 무관하게 전부 평가)
        for rule_id, rule_name, rule_fn in YELLOW_RULES:
            reason = rule_fn(ec)
            if reason is not None:
                matched.append(RuleMatch(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    description=reason,
                ))
                yellow_matched = True

        # 색상 결정: RED > YELLOW > GREEN
        if red_matched:
            color = FilterColor.RED
        elif yellow_matched:
            color = FilterColor.YELLOW
        else:
            color = FilterColor.GREEN

        # CostGate: RED → passed=False
        passed = color != FilterColor.RED

        return FilterResult(
            color=color,
            passed=passed,
            matched_rules=matched,
        )

    def evaluate_batch(self, cases: list[EnrichedCase]) -> list[EnrichedCase]:
        """배치 평가: 각 EnrichedCase에 filter_result 설정"""
        for ec in cases:
            ec.filter_result = self.evaluate(ec)
        return cases
