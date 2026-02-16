"""5e_scores_table

5E: 통합 점수 테이블 생성.
scores: Auction 1:1, pillar 점수 + 통합 + 등급 + 캘리브레이션 컬럼.

Revision ID: b1d458637499
Revises: a0c347536398
Create Date: 2026-02-16 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1d458637499"
down_revision: Union[str, Sequence[str], None] = "a0c347536398"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """scores 테이블 생성"""

    op.create_table(
        "scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "auction_id", sa.String(36),
            sa.ForeignKey("auctions.id", ondelete="CASCADE"),
            unique=True, nullable=False,
        ),
        sa.Column("property_category", sa.String(20), nullable=False, server_default="꼬마빌딩"),
        # pillar 점수
        sa.Column("legal_score", sa.Float, nullable=True),
        sa.Column("price_score", sa.Float, nullable=True),
        sa.Column("location_score", sa.Float, nullable=True),
        sa.Column("occupancy_score", sa.Float, nullable=True),
        # 통합 결과
        sa.Column("total_score", sa.Float, nullable=False),
        sa.Column("score_coverage", sa.Float, nullable=False),
        sa.Column("missing_pillars", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("grade", sa.String(1), nullable=True),
        sa.Column("sub_scores", postgresql.JSONB, nullable=True),
        sa.Column("warnings", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("needs_expert_review", sa.Boolean, nullable=False, server_default="false"),
        # 캘리브레이션
        sa.Column("actual_winning_bid", sa.BigInteger, nullable=True),
        sa.Column("actual_winning_ratio", sa.Float, nullable=True),
        sa.Column("prediction_error", sa.Float, nullable=True),
        # 메타
        sa.Column("scorer_version", sa.String(20), nullable=False, server_default="v1.0"),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column("pipeline_run_id", sa.String(36), nullable=True),
    )

    op.create_index("ix_scores_total", "scores", ["total_score"])
    op.create_index("ix_scores_grade", "scores", ["grade"])
    op.create_index("ix_scores_coverage", "scores", ["score_coverage"])
    op.create_index("ix_scores_category", "scores", ["property_category"])
    op.create_index("ix_scores_scored_at", "scores", ["scored_at"])


def downgrade() -> None:
    """scores 테이블 제거"""
    op.drop_index("ix_scores_scored_at", "scores")
    op.drop_index("ix_scores_category", "scores")
    op.drop_index("ix_scores_coverage", "scores")
    op.drop_index("ix_scores_grade", "scores")
    op.drop_index("ix_scores_total", "scores")
    op.drop_table("scores")
