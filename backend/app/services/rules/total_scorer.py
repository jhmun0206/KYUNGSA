"""통합 점수 합산기 (5E)

개별 pillar 점수를 가중 합산하여 최종 점수와 등급을 산출한다.
I/O 없음 — 순수 계산 로직만 포함.

핵심:
  - 가용 pillar만으로 가중합 + 가중치 재정규화 (Partial Score)
  - 유형별 가중치 (아파트/꼬마빌딩/토지)
  - 등급: A(80+) / B(60~80) / C(40~60) / D(<40)
  - score_coverage: 원래 가중치 중 가용 pillar가 차지하는 비율 (0~1.0)

=== 신뢰도 설계 원칙 (Phase 5.5 명문화) ===
1. 신뢰도 감쇠(confidence_multiplier)는 각 pillar 내부에서만 적용한다.
   - LegalScorer:  HIGH=1.0, MEDIUM=0.8,  LOW=0.6
   - PriceScorer:  HIGH=1.0, MEDIUM=0.85, LOW=0.7
   - LocationScorer (Phase 6), OccupancyScorer (Phase 7): 별도 결정

2. TotalScorer는 신뢰도 감쇠를 하지 않는다. 재정규화만 수행한다.
   이유: pillar 내부에서 이미 감쇠된 점수를 TotalScorer가 또 감쇠하면
         이중 페널티가 발생한다.

3. 대신 TotalScorer는 score_coverage와 경고로만 신뢰도를 표현한다.
   - coverage < 0.70 → "점수 커버리지 낮음" 경고
   - 이 원칙은 Phase 6/7 pillar 추가 후에도 유지한다.
==="""

from __future__ import annotations

import logging

from app.models.scores import TotalScoreResult

logger = logging.getLogger(__name__)

# 유형별 4-pillar 가중치 (합=1.0)
PILLAR_WEIGHTS: dict[str, dict[str, float]] = {
    "아파트": {"legal": 0.20, "price": 0.25, "location": 0.30, "occupancy": 0.25},
    "꼬마빌딩": {"legal": 0.35, "price": 0.20, "location": 0.15, "occupancy": 0.30},
    "토지": {"legal": 0.25, "price": 0.15, "location": 0.50, "occupancy": 0.10},
}

DEFAULT_CATEGORY = "꼬마빌딩"

SCORER_VERSION = "v1.0"
PREDICTION_METHOD = "rule_v1"

# property_type → category 매핑
_APARTMENT_TYPES = frozenset({"아파트", "오피스텔", "주상복합", "연립", "빌라"})
_LAND_TYPES = frozenset({"토지", "임야", "전", "답", "대지"})

# rule_v1: 유찰 횟수별 예측 낙찰가율 (통계 평균 midpoint)
# 출처: Phase 5F 백테스트 실데이터 7,134건 기반 (2026-02-18 캘리브레이션).
# 0유찰 값만 교체 (서울 5개 법원 낙찰완료 실측 기반):
#   아파트 0유찰: 1,473건 중앙값 0.80 (기존 0.975 → -17.5% 오차)
#   꼬마빌딩 0유찰: 5,127건 중앙값 0.63 (기존 0.90 → -27.0% 오차)
#   토지 0유찰: 481건 중앙값 0.54 (기존 0.85 → -31.4% 오차)
# 1유찰+ 값은 추후 충분한 샘플 확보 후 캘리브레이션 예정.
_PREDICTED_RATIO_TABLE: dict[str, list[float]] = {
    #            0유찰  1유찰  2유찰  3유찰  4유찰+
    "아파트":   [0.80,  0.90,  0.80,  0.70,  0.60],
    "꼬마빌딩": [0.63,  0.80,  0.70,  0.60,  0.50],
    "토지":     [0.54,  0.75,  0.65,  0.55,  0.45],
}


class TotalScorer:
    """통합 점수 합산기"""

    def score(
        self,
        property_type: str,
        *,
        legal_score: float | None = None,
        price_score: float | None = None,
        location_score: float | None = None,
        occupancy_score: float | None = None,
        needs_expert_review: bool = False,
        fail_count: int = 0,
    ) -> TotalScoreResult:
        """통합 점수 산출

        Args:
            property_type: 물건 유형 (예: "아파트", "상가", "토지")
            legal_score: 법률 리스크 점수 (0~100)
            price_score: 가격 매력도 점수 (0~100)
            location_score: 입지 점수 (0~100) — Phase 6
            occupancy_score: 명도 리스크 점수 (0~100) — Phase 7
            needs_expert_review: 전문가 검토 필요 여부 (pillar에서 전달)
            fail_count: 유찰 횟수 (bid_count - 1). predicted_winning_ratio 산출에 사용.

        Returns:
            TotalScoreResult
        """
        warnings: list[str] = []

        # 1. 유형 분류
        category = self._classify_property(property_type)

        # 2. 가용 pillar 수집
        available: dict[str, float] = {}
        pillar_scores: dict[str, float] = {}

        if legal_score is not None:
            available["legal"] = PILLAR_WEIGHTS[category]["legal"]
            pillar_scores["legal"] = legal_score
        if price_score is not None:
            available["price"] = PILLAR_WEIGHTS[category]["price"]
            pillar_scores["price"] = price_score
        if location_score is not None:
            available["location"] = PILLAR_WEIGHTS[category]["location"]
            pillar_scores["location"] = location_score
        if occupancy_score is not None:
            available["occupancy"] = PILLAR_WEIGHTS[category]["occupancy"]
            pillar_scores["occupancy"] = occupancy_score

        # missing pillars
        all_pillars = {"legal", "price", "location", "occupancy"}
        missing = sorted(all_pillars - set(available.keys()))

        # 3. coverage 계산 (원래 가중치 합 대비 가용 가중치 합)
        score_coverage = sum(available.values())

        if score_coverage < 0.70:
            warnings.append(f"점수 커버리지 낮음 ({score_coverage:.0%}) — 해석 주의")

        # 4. 가중치 재정규화
        normalized = self._normalize_weights(available)

        # 5. 가중 합산
        if not pillar_scores:
            total_score = 0.0
            warnings.append("가용 pillar 없음 — 점수 산출 불가")
        else:
            total_score = sum(
                pillar_scores[name] * normalized[name]
                for name in pillar_scores
            )
            total_score = round(total_score, 1)

        # 6. 등급 부여 + 잠정 여부 (coverage < 0.70)
        grade = self._assign_grade(total_score)
        grade_provisional = score_coverage < 0.70

        # 7. 예측 낙찰가율 (rule_v1: 유찰 횟수 기반 통계값)
        predicted_ratio = self._calc_predicted_ratio(category, fail_count)

        return TotalScoreResult(
            total_score=total_score,
            score_coverage=round(score_coverage, 4),
            missing_pillars=missing,
            grade=grade,
            grade_provisional=grade_provisional,
            property_category=category,
            weights_used={k: round(v, 4) for k, v in normalized.items()},
            legal_score=legal_score,
            price_score=price_score,
            location_score=location_score,
            occupancy_score=occupancy_score,
            warnings=warnings,
            needs_expert_review=needs_expert_review,
            scorer_version=SCORER_VERSION,
            predicted_winning_ratio=predicted_ratio,
            prediction_method=PREDICTION_METHOD,
        )

    @staticmethod
    def _classify_property(property_type: str) -> str:
        """물건 유형 → 카테고리 (아파트/꼬마빌딩/토지)"""
        if not property_type:
            return DEFAULT_CATEGORY

        for keyword in _APARTMENT_TYPES:
            if keyword in property_type:
                return "아파트"
        for keyword in _LAND_TYPES:
            if keyword in property_type:
                return "토지"

        # 그 외 (상가, 근린, 다가구 등) → 꼬마빌딩 (보수적)
        return "꼬마빌딩"

    @staticmethod
    def _normalize_weights(available: dict[str, float]) -> dict[str, float]:
        """가용 pillar 가중치 재정규화 (합=1.0)"""
        total = sum(available.values())
        if total == 0:
            return {}
        return {name: weight / total for name, weight in available.items()}

    @staticmethod
    def _assign_grade(total_score: float) -> str:
        """총점 → 등급"""
        if total_score >= 80:
            return "A"
        if total_score >= 60:
            return "B"
        if total_score >= 40:
            return "C"
        return "D"

    @staticmethod
    def _calc_predicted_ratio(category: str, fail_count: int) -> float:
        """예측 낙찰가율 산출 (rule_v1 — 유찰 횟수 기반 통계값)

        Phase 5F 백테스트에서 실데이터 기반으로 교체될 초기값.
        4회 이상 유찰은 마지막 값(인덱스 4)으로 클램프.
        """
        table = _PREDICTED_RATIO_TABLE.get(category, _PREDICTED_RATIO_TABLE[DEFAULT_CATEGORY])
        idx = min(fail_count, len(table) - 1)
        return table[idx]
