"""통합 점수 합산기 (5E)

개별 pillar 점수를 가중 합산하여 최종 점수와 등급을 산출한다.
I/O 없음 — 순수 계산 로직만 포함.

핵심:
  - 가용 pillar만으로 가중합 + 가중치 재정규화 (Partial Score)
  - 유형별 가중치 (아파트/꼬마빌딩/토지)
  - 등급: A(80+) / B(60~80) / C(40~60) / D(<40)
  - score_coverage: 원래 가중치 중 가용 pillar가 차지하는 비율 (0~1.0)
"""

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

# property_type → category 매핑
_APARTMENT_TYPES = frozenset({"아파트", "오피스텔", "주상복합", "연립", "빌라"})
_LAND_TYPES = frozenset({"토지", "임야", "전", "답", "대지"})


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
    ) -> TotalScoreResult:
        """통합 점수 산출

        Args:
            property_type: 물건 유형 (예: "아파트", "상가", "토지")
            legal_score: 법률 리스크 점수 (0~100)
            price_score: 가격 매력도 점수 (0~100)
            location_score: 입지 점수 (0~100) — Phase 6
            occupancy_score: 명도 리스크 점수 (0~100) — Phase 7
            needs_expert_review: 전문가 검토 필요 여부 (pillar에서 전달)

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

        # 6. 등급 부여
        grade = self._assign_grade(total_score)

        return TotalScoreResult(
            total_score=total_score,
            score_coverage=round(score_coverage, 4),
            missing_pillars=missing,
            grade=grade,
            property_category=category,
            weights_used={k: round(v, 4) for k, v in normalized.items()},
            legal_score=legal_score,
            price_score=price_score,
            location_score=location_score,
            occupancy_score=occupancy_score,
            warnings=warnings,
            needs_expert_review=needs_expert_review,
            scorer_version=SCORER_VERSION,
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
