"""Phase H-2: rent_price_info 컬럼 추가

Revision ID: a8f3c2d1e9b7
Revises: f7a1b2c3d4e5
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "a8f3c2d1e9b7"
down_revision = "f7a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auctions",
        sa.Column("rent_price_info", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("auctions", "rent_price_info")
