"""DB → ML 학습 데이터 추출 파이프라인 (Private)

auctions + scores + occupancy_tenants 조인하여 학습용 DataFrame을 반환한다.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 낙찰 데이터 + 점수 추출 SQL
_MAIN_QUERY = text("""
SELECT
    a.case_number,
    a.winning_bid,
    a.appraised_value,
    a.minimum_bid,
    a.property_type,
    a.court_office_code,
    a.address,
    a.winning_date,
    a.winning_ratio,
    a.bid_count,
    CAST(
        COALESCE(a.detail->>'yuchalCnt', (a.bid_count - 1)::TEXT)
        AS INTEGER
    ) AS fail_count,
    s.legal_score,
    s.price_score,
    s.location_score,
    s.occupancy_score,
    s.total_score
FROM auctions a
LEFT JOIN scores s ON a.id = s.auction_id
WHERE a.winning_bid IS NOT NULL
  AND a.appraised_value > 0
ORDER BY a.winning_date ASC NULLS LAST
""")

# 임차인 집계 SQL
_OCCUPANCY_QUERY = text("""
SELECT
    case_number,
    COUNT(*) AS tenant_count,
    COALESCE(SUM(deposit), 0) AS total_deposit
FROM occupancy_tenants
GROUP BY case_number
""")


class PredictionDataPipeline:
    """DB에서 ML 학습 데이터를 추출하는 파이프라인"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def extract_training_data(self) -> pd.DataFrame:
        """낙찰 데이터 + 점수 + 임차인 정보를 DataFrame으로 추출

        Returns:
            DataFrame (case_number 인덱스용, 피처 아님)
            - target용: winning_bid, appraised_value, winning_ratio
            - 피처용: property_type, fail_count, court_office_code, ...
            - 점수: legal_score, price_score, location_score, occupancy_score, total_score
            - 임차인: tenant_count, total_deposit
        """
        # 1. 낙찰 데이터 + 점수
        main_rows = self._db.execute(_MAIN_QUERY).fetchall()
        if not main_rows:
            logger.warning("낙찰 데이터 없음")
            return pd.DataFrame()

        columns = [
            "case_number", "winning_bid", "appraised_value", "minimum_bid",
            "property_type", "court_office_code", "address", "winning_date",
            "winning_ratio", "bid_count", "fail_count",
            "legal_score", "price_score", "location_score",
            "occupancy_score", "total_score",
        ]
        df = pd.DataFrame(main_rows, columns=columns)

        # 2. 임차인 집계
        occ_rows = self._db.execute(_OCCUPANCY_QUERY).fetchall()
        if occ_rows:
            occ_df = pd.DataFrame(
                occ_rows,
                columns=["case_number", "tenant_count", "total_deposit"],
            )
            df = df.merge(occ_df, on="case_number", how="left")
        else:
            df["tenant_count"] = 0
            df["total_deposit"] = 0

        logger.info("학습 데이터 추출: %d건", len(df))
        return df
