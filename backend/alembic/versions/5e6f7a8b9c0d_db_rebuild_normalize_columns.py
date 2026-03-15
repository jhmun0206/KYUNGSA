"""DB-REBUILD: 정규화 컬럼 추가 + auction_rounds 테이블 + rent_price_info JSONB 변환

Revision ID: 5e6f7a8b9c0d
Revises: 4d0e491c6f8f
Create Date: 2026-03-14

변경 내용:
  auctions 신규 컬럼:
    - location_data     JSONB   (BUG-02: 카카오 입지 데이터 저장 누락)
    - property_category VARCHAR(30)
    - building_type     VARCHAR(10)
    - lat / lng         FLOAT
    - station_distance_m INTEGER
    - build_year        INTEGER
    - exclusive_area_m2_real FLOAT
    - floor_count       INTEGER
    - units_count_real  INTEGER
    - current_round     INTEGER DEFAULT 1

  auctions 타입 변경:
    - rent_price_info   JSON → JSONB  (BUG-03)

  신규 테이블:
    - auction_rounds (auction_id, round_number, round_date, minimum_bid, result)

  신규 인덱스:
    - ix_auctions_property_category
    - ix_auctions_build_year
    - ix_auctions_station_distance
    - ix_auctions_lat_lng (composite)
    - ix_auction_rounds_auction_id
    - ix_auction_rounds_date
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers
revision: str = "5e6f7a8b9c0d"
down_revision: str = "4d0e491c6f8f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ──────────────────────────────────────────
    # 1. auctions 신규 컬럼 추가 (ADD COLUMN은 lock 없음)
    # ──────────────────────────────────────────
    op.add_column("auctions", sa.Column("location_data", JSONB(), nullable=True))
    op.add_column("auctions", sa.Column("property_category", sa.String(30), nullable=True))
    op.add_column("auctions", sa.Column("building_type", sa.String(10), nullable=True))
    op.add_column("auctions", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("auctions", sa.Column("lng", sa.Float(), nullable=True))
    op.add_column("auctions", sa.Column("station_distance_m", sa.Integer(), nullable=True))
    op.add_column("auctions", sa.Column("build_year", sa.Integer(), nullable=True))
    op.add_column("auctions", sa.Column("exclusive_area_m2_real", sa.Float(), nullable=True))
    op.add_column("auctions", sa.Column("floor_count", sa.Integer(), nullable=True))
    op.add_column("auctions", sa.Column("units_count_real", sa.Integer(), nullable=True))
    op.add_column(
        "auctions",
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="1"),
    )

    # ──────────────────────────────────────────
    # 2. rent_price_info: json → jsonb (BUG-03)
    #    사전 확인: SELECT COUNT(*) FROM auctions WHERE json_typeof(rent_price_info) != 'null'
    #    null 리터럴 → SQL NULL 정리 후 타입 변경
    # ──────────────────────────────────────────
    op.execute(
        "UPDATE auctions SET rent_price_info = NULL WHERE json_typeof(rent_price_info) = 'null'"
    )
    op.execute(
        "ALTER TABLE auctions ALTER COLUMN rent_price_info TYPE jsonb "
        "USING rent_price_info::text::jsonb"
    )

    # ──────────────────────────────────────────
    # 3. auction_rounds 테이블 생성
    # ──────────────────────────────────────────
    op.create_table(
        "auction_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "auction_id",
            sa.String(36),
            sa.ForeignKey("auctions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("round_date", sa.Date(), nullable=True),
        sa.Column("minimum_bid", sa.BigInteger(), nullable=True),
        sa.Column("result", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("auction_id", "round_number", name="uq_auction_round"),
    )

    # ──────────────────────────────────────────
    # 4. 신규 인덱스
    # ──────────────────────────────────────────
    op.create_index("ix_auctions_property_category", "auctions", ["property_category"])
    op.create_index("ix_auctions_build_year", "auctions", ["build_year"])
    op.create_index("ix_auctions_station_distance", "auctions", ["station_distance_m"])
    op.create_index("ix_auctions_lat_lng", "auctions", ["lat", "lng"])
    op.create_index("ix_auction_rounds_auction_id", "auction_rounds", ["auction_id"])
    op.create_index("ix_auction_rounds_date", "auction_rounds", ["round_date"])


def downgrade() -> None:
    op.drop_index("ix_auction_rounds_date", table_name="auction_rounds")
    op.drop_index("ix_auction_rounds_auction_id", table_name="auction_rounds")
    op.drop_index("ix_auctions_lat_lng", table_name="auctions")
    op.drop_index("ix_auctions_station_distance", table_name="auctions")
    op.drop_index("ix_auctions_build_year", table_name="auctions")
    op.drop_index("ix_auctions_property_category", table_name="auctions")

    op.drop_table("auction_rounds")

    # rent_price_info: jsonb → json (역변환)
    op.execute(
        "ALTER TABLE auctions ALTER COLUMN rent_price_info TYPE json "
        "USING rent_price_info::text::json"
    )

    op.drop_column("auctions", "current_round")
    op.drop_column("auctions", "units_count_real")
    op.drop_column("auctions", "floor_count")
    op.drop_column("auctions", "exclusive_area_m2_real")
    op.drop_column("auctions", "build_year")
    op.drop_column("auctions", "station_distance_m")
    op.drop_column("auctions", "lng")
    op.drop_column("auctions", "lat")
    op.drop_column("auctions", "building_type")
    op.drop_column("auctions", "property_category")
    op.drop_column("auctions", "location_data")
