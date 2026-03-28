"""registry_analyses_add_columns

registry_analyses: UNIQUE(auction_id) 제거 (1:1→1:N) +
case_number / property_sequence / fetched_by_user_id / fetched_at 컬럼 추가.

Revision ID: g1h2i3j4k5l6
Revises: f8a9b0c1d2e3
Create Date: 2026-03-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # UNIQUE 제거 (한 물건에 여러 번 조회 허용)
    op.drop_constraint(
        "registry_analyses_auction_id_key",
        "registry_analyses",
        type_="unique",
    )

    # 새 컬럼
    op.add_column(
        "registry_analyses",
        sa.Column("case_number", sa.String(50), nullable=True),
    )
    op.add_column(
        "registry_analyses",
        sa.Column(
            "property_sequence",
            sa.Integer(),
            nullable=True,
            server_default="1",
        ),
    )
    op.add_column(
        "registry_analyses",
        sa.Column("fetched_by_user_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "registry_analyses",
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 기존 레코드 backfill (auction_id → auctions.case_number/property_sequence)
    op.execute(
        """
        UPDATE registry_analyses ra
        SET case_number = a.case_number,
            property_sequence = a.property_sequence
        FROM auctions a
        WHERE ra.auction_id = a.id
        """
    )

    # 조회 최적화 인덱스
    op.create_index(
        "idx_registry_analyses_case_seq",
        "registry_analyses",
        ["case_number", "property_sequence"],
    )
    op.create_index(
        "idx_registry_analyses_fetched_at",
        "registry_analyses",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_registry_analyses_fetched_at", table_name="registry_analyses")
    op.drop_index("idx_registry_analyses_case_seq", table_name="registry_analyses")
    op.drop_column("registry_analyses", "fetched_at")
    op.drop_column("registry_analyses", "fetched_by_user_id")
    op.drop_column("registry_analyses", "property_sequence")
    op.drop_column("registry_analyses", "case_number")
    op.create_unique_constraint(
        "registry_analyses_auction_id_key",
        "registry_analyses",
        ["auction_id"],
    )
