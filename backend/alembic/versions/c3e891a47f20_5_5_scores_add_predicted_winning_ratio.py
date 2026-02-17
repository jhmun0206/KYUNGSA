"""5_5_scores_add_predicted_winning_ratio

5.5: scores 테이블에 낙찰가율 예측 컬럼 추가.
predicted_winning_ratio: 예측 낙찰가율 (0~1.0)
prediction_method: 예측 방법 ('rule_v1' | 'model_v1')

Revision ID: c3e891a47f20
Revises: b1d458637499
Create Date: 2026-02-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e891a47f20"
down_revision: Union[str, Sequence[str], None] = "b1d458637499"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """scores 테이블에 낙찰가율 예측 컬럼 추가"""
    op.add_column(
        "scores",
        sa.Column("predicted_winning_ratio", sa.Float, nullable=True),
    )
    op.add_column(
        "scores",
        sa.Column(
            "prediction_method",
            sa.String(30),
            nullable=False,
            server_default="rule_v1",
        ),
    )


def downgrade() -> None:
    """컬럼 제거"""
    op.drop_column("scores", "prediction_method")
    op.drop_column("scores", "predicted_winning_ratio")
