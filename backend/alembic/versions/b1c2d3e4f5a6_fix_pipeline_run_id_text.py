"""scores.pipeline_run_id 타입 VARCHAR(36) → Text 변경

Revision ID: b1c2d3e4f5a6
Revises: a8f3c2d1e9b7
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a8f3c2d1e9b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "scores",
        "pipeline_run_id",
        existing_type=sa.VARCHAR(length=36),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "scores",
        "pipeline_run_id",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=36),
        existing_nullable=True,
    )
