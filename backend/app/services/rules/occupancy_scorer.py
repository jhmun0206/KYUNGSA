"""명도 리스크 점수 산출기 (Phase 7-3)

현황조사서 임차인 데이터를 기반으로 명도 용이성을 0~100으로 산출한다.
3개 서브스코어(임차인 복잡도, 보증금 부담도, 대항력 위험도) → 유형별 가중합 → 신뢰도 감쇠.

=== 설계 원칙 ===
- 임차인 0명 → 높은 점수 (명도 불필요), 단 신뢰도 MEDIUM
  (조사 시점 이후 변동 가능)
- 선형 보간 (LocationScorer와 동일 패턴)
- 미상 임차인은 추가 감점 (실태 불명)
"""

from __future__ import annotations

import logging

from app.models.auction import AuctionCaseDetail
from app.models.occupancy_dto import OccupancyTenantDTO
from app.models.scores import OccupancyScoreResult, OccupancySubScores

logger = logging.getLogger(__name__)

# 유형별 내부 가중치 (합=1.0)
OCCUPANCY_WEIGHTS: dict[str, dict[str, float]] = {
    "아파트":   {"tenant_complexity": 0.25, "deposit_burden": 0.35, "opposing_power": 0.40},
    "꼬마빌딩": {"tenant_complexity": 0.35, "deposit_burden": 0.30, "opposing_power": 0.35},
    "토지":     {"tenant_complexity": 0.60, "deposit_burden": 0.20, "opposing_power": 0.20},
}

DEFAULT_CATEGORY = "꼬마빌딩"

# 임차인 수 → 복잡도 점수 곡선
TENANT_COUNT_CURVE: list[tuple[int, float]] = [
    (0, 100), (1, 80), (2, 60), (3, 40), (4, 20),
]
UNKNOWN_PENALTY = 15.0  # 미상 임차인 1명당 감점

# 보증금/감정가 비율 → 부담도 점수 곡선
DEPOSIT_RATIO_CURVE: list[tuple[float, float]] = [
    (0.0, 100), (0.1, 85), (0.3, 65), (0.5, 45), (0.7, 25), (1.0, 10),
]
DEPOSIT_UNKNOWN_SCORE = 50.0  # 보증금 정보 없을 때 불확실 점수

# 대항력 비율 (전입+확정 보유 비율) → 위험도 점수 곡선
OPPOSING_POWER_CURVE: list[tuple[float, float]] = [
    (0.0, 100), (0.25, 80), (0.5, 55), (0.75, 35), (1.0, 15),
]

# 물건 유형 분류
_APARTMENT_TYPES = frozenset({"아파트", "오피스텔", "주상복합", "연립", "빌라"})
_LAND_TYPES = frozenset({"토지", "임야", "전", "답", "대지"})

SCORER_VERSION = "v1.0"


def _interpolate(curve: list[tuple[int | float, float]], value: float) -> float:
    """선형 보간 — 범위 외 경계값 클램프"""
    if value <= curve[0][0]:
        return curve[0][1]
    if value >= curve[-1][0]:
        return curve[-1][1]
    for i in range(1, len(curve)):
        x0, y0 = curve[i - 1]
        x1, y1 = curve[i]
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return curve[-1][1]


def _calc_tenant_complexity(tenant_count: int, unknown_count: int) -> float:
    """임차인 복잡도 점수 산출

    임차인 수가 많을수록 명도 협상이 복잡해진다.
    미상 임차인은 추가 감점 (실태 불명).
    """
    base = _interpolate(TENANT_COUNT_CURVE, float(tenant_count))
    penalty = unknown_count * UNKNOWN_PENALTY
    return max(0.0, base - penalty)


def _calc_deposit_burden(
    total_deposit: int,
    appraised_value: int | None,
    minimum_bid: int | None,
) -> float:
    """보증금 부담도 점수 산출

    총 보증금 / 감정가 비율이 높을수록 명도 시 보증금 반환 부담 큼.
    """
    # 보증금 없으면 불확실
    if total_deposit == 0:
        return DEPOSIT_UNKNOWN_SCORE

    # 기준가 결정 (감정가 > 최저가 > 0 방지)
    base_value = appraised_value or minimum_bid or 0
    if base_value <= 0:
        return DEPOSIT_UNKNOWN_SCORE

    ratio = total_deposit / base_value
    return _interpolate(DEPOSIT_RATIO_CURVE, ratio)


def _calc_opposing_power(
    tenants: list[OccupancyTenantDTO],
) -> float:
    """대항력 위험도 점수 산출

    전입일 + 확정일 모두 있는 임차인 비율이 높을수록 대항력 가능성 높다.
    """
    if not tenants:
        return 100.0  # 임차인 없으면 대항력 위험 없음

    # 미상 임차인 제외하고 계산
    known_tenants = [t for t in tenants if not t.is_unknown]
    if not known_tenants:
        return 50.0  # 전원 미상이면 불확실

    fixed_count = sum(
        1 for t in known_tenants
        if t.move_in_date is not None and t.fixed_date is not None
    )
    fixed_ratio = fixed_count / len(known_tenants)
    return _interpolate(OPPOSING_POWER_CURVE, fixed_ratio)


class OccupancyScorer:
    """명도 리스크 점수 산출기 (Phase 7-3)

    현황조사서 임차인 데이터(OccupancyTenantDTO)와 경매 물건 상세(AuctionCaseDetail)를
    바탕으로 임차인 복잡도/보증금 부담도/대항력 위험도 서브스코어를 산출하고
    물건 유형별 가중 합산으로 최종 명도 리스크 점수를 반환한다.
    """

    def score(
        self,
        case: AuctionCaseDetail,
        tenants: list[OccupancyTenantDTO],
    ) -> OccupancyScoreResult:
        """명도 리스크 점수 산출

        Args:
            case: 경매 물건 상세 (property_type, appraised_value 참조)
            tenants: 현황조사서 임차인 목록. 빈 리스트 = 임차인 없음.

        Returns:
            OccupancyScoreResult
        """
        warnings: list[str] = []
        category = self._classify_property(case.property_type)

        tenant_count = len(tenants)
        unknown_count = sum(1 for t in tenants if t.is_unknown)
        total_deposit = sum(t.deposit or 0 for t in tenants)

        # 서브스코어 산출
        tenant_complexity = _calc_tenant_complexity(tenant_count, unknown_count)
        deposit_burden = _calc_deposit_burden(
            total_deposit, case.appraised_value, case.minimum_bid,
        )
        opposing_power = _calc_opposing_power(tenants)

        sub_scores = OccupancySubScores(
            tenant_complexity_score=round(tenant_complexity, 1),
            deposit_burden_score=round(deposit_burden, 1),
            opposing_power_score=round(opposing_power, 1),
        )

        # 유형별 가중 합산
        weights = OCCUPANCY_WEIGHTS.get(category, OCCUPANCY_WEIGHTS[DEFAULT_CATEGORY])
        base_score = (
            tenant_complexity * weights["tenant_complexity"]
            + deposit_burden * weights["deposit_burden"]
            + opposing_power * weights["opposing_power"]
        )
        base_score = round(base_score, 1)

        # 신뢰도 결정
        confidence, conf_multiplier = self._determine_confidence(
            tenants, total_deposit,
        )

        final_score = round(base_score * conf_multiplier, 1)
        final_score = max(0.0, min(100.0, final_score))

        if unknown_count > 0:
            warnings.append(f"미상 임차인 {unknown_count}명 — 실태 확인 필요")

        return OccupancyScoreResult(
            score=final_score,
            base_score=base_score,
            sub_scores=sub_scores,
            confidence=confidence,
            confidence_multiplier=conf_multiplier,
            property_category=category,
            tenant_count=tenant_count,
            unknown_count=unknown_count,
            total_deposit=total_deposit,
            warnings=warnings,
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
        return DEFAULT_CATEGORY

    @staticmethod
    def _determine_confidence(
        tenants: list[OccupancyTenantDTO],
        total_deposit: int,
    ) -> tuple[str, float]:
        """데이터 완비도 기반 신뢰도 결정

        - tenant > 0 AND 보증금 있음 AND 날짜 있음 → HIGH (1.0)
        - tenant > 0 AND (보증금 없음 OR 날짜 없음) → MEDIUM (0.85)
        - tenant == 0 (임차인 없음) → MEDIUM (0.85)
        """
        if not tenants:
            # 임차인 없음: 안전하지만 조사 시점 이후 변동 가능
            return "MEDIUM", 0.85

        has_deposit = total_deposit > 0
        has_date = any(
            t.move_in_date is not None or t.fixed_date is not None
            for t in tenants if not t.is_unknown
        )

        if has_deposit and has_date:
            return "HIGH", 1.0

        return "MEDIUM", 0.85
