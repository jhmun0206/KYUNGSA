"""phase65_winning_columns

Phase 6.5: auctions 테이블에 낙찰결과 컬럼 4개 추가.
기수집 물건 상태 추적으로 winning_bid/date/ratio/source 저장.

Revision ID: e5a2c947f310
Revises: d4f721839b6c
Create Date: 2026-02-17 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a2c947f310"
down_revision: Union[str, Sequence[str], None] = "d4f721839b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 낙찰결과 컬럼 추가 (기존 행은 NULL)
    op.add_column("auctions", sa.Column("winning_bid", sa.BigInteger(), nullable=True))
    op.add_column("auctions", sa.Column("winning_date", sa.Date(), nullable=True))
    op.add_column("auctions", sa.Column("winning_ratio", sa.Float(), nullable=True))
    op.add_column("auctions", sa.Column("winning_source", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("auctions", "winning_source")
    op.drop_column("auctions", "winning_ratio")
    op.drop_column("auctions", "winning_date")
    op.drop_column("auctions", "winning_bid")
