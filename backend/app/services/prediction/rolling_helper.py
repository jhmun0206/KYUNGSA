"""Rolling 통계 DB 조회 헬퍼 (Private)

추론 시점에 동일 유형×시도의 최근 낙찰가율 평균/건수를 DB에서 조회한다.
학습 시 FeatureEngineer가 생성하는 rolling_avg_3m/rolling_count_3m과 동일한 의미.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class RollingStats:
    """Rolling 통계"""

    avg: float | None       # 평균 낙찰가율 (건수 0이면 None)
    count: int              # 건수


# 동일 유형×시도 최근 낙찰 건의 평균/건수
_ROLLING_QUERY = text("""
SELECT
    AVG(a.winning_ratio) AS avg_ratio,
    COUNT(*) AS cnt
FROM auctions a
WHERE a.winning_bid IS NOT NULL
  AND a.appraised_value > 0
  AND a.property_type = :property_type
  AND a.address LIKE :sido_prefix
""")


def get_rolling_stats(
    db: Session,
    *,
    property_type: str,
    address: str,
) -> RollingStats:
    """DB에서 동일 유형×시도의 낙찰가율 통계 조회

    Args:
        db: SQLAlchemy Session
        property_type: 원본 물건유형 (병합 전)
        address: 전체 주소 (sido 추출용)

    Returns:
        RollingStats(avg, count)
    """
    # 주소에서 시도 추출
    addr_parts = (address or "").strip().split()
    sido = addr_parts[0] if addr_parts else ""

    if not sido or not property_type:
        return RollingStats(avg=None, count=0)

    try:
        row = db.execute(
            _ROLLING_QUERY,
            {"property_type": property_type, "sido_prefix": f"{sido}%"},
        ).fetchone()

        if row and row[1] > 0:
            return RollingStats(
                avg=round(float(row[0]), 4) if row[0] is not None else None,
                count=int(row[1]),
            )
    except Exception:
        logger.exception("rolling stats 조회 실패")

    return RollingStats(avg=None, count=0)
