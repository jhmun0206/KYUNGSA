"""add_property_sequence

property_sequence 컬럼 추가 + 복합 UNIQUE (case_number, property_sequence)

Revision ID: f8a9b0c1d2e3
Revises: e3f4a5b6c7d8
Create Date: 2026-03-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. occupancy_reports.case_number FK 제거
    #    (auctions.case_number 단독 UNIQUE 삭제 전에 먼저 제거해야 함)
    op.drop_constraint(
        "occupancy_reports_case_number_fkey", "occupancy_reports", type_="foreignkey"
    )

    # 1. 컬럼 추가 (DEFAULT 1)
    op.add_column(
        "auctions",
        sa.Column("property_sequence", sa.Integer(), nullable=False, server_default="1"),
    )

    # 2. maemulSer 있으면 반영, 없으면 1 유지
    op.execute(
        """
        UPDATE auctions
        SET property_sequence = (detail->>'maemulSer')::int
        WHERE detail->>'maemulSer' IS NOT NULL
          AND detail->>'maemulSer' ~ '^[0-9]+$'
          AND (detail->>'maemulSer')::int >= 1
        """
    )

    # 3. 기존 UNIQUE 제거
    op.drop_constraint("auctions_case_number_key", "auctions", type_="unique")

    # 4. 복합 UNIQUE 추가
    op.create_unique_constraint(
        "auctions_case_number_seq_key",
        "auctions",
        ["case_number", "property_sequence"],
    )


def downgrade() -> None:
    op.drop_constraint("auctions_case_number_seq_key", "auctions", type_="unique")
    op.create_unique_constraint(
        "auctions_case_number_key", "auctions", ["case_number"]
    )
    op.drop_column("auctions", "property_sequence")
    # FK 복원 (downgrade 시 auctions.case_number 단독 UNIQUE 복원됨)
    op.create_foreign_key(
        "occupancy_reports_case_number_fkey",
        "occupancy_reports",
        "auctions",
        ["case_number"],
        ["case_number"],
    )
