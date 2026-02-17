"""phase6_scores_add_grade_provisional

Phase 6: scores 테이블에 grade_provisional 컬럼 추가.
grade_provisional: score_coverage < 0.70 시 True (잠정 등급 표시)

Revision ID: d4f721839b6c
Revises: c3e891a47f20
Create Date: 2026-02-17 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f721839b6c"
down_revision: Union[str, Sequence[str], None] = "c3e891a47f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # grade_provisional 컬럼 추가 (기존 행은 False로 초기화)
    op.add_column(
        "scores",
        sa.Column(
            "grade_provisional",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.create_index(
        "ix_scores_grade_provisional",
        "scores",
        ["grade_provisional"],
    )


def downgrade() -> None:
    op.drop_index("ix_scores_grade_provisional", table_name="scores")
    op.drop_column("scores", "grade_provisional")
