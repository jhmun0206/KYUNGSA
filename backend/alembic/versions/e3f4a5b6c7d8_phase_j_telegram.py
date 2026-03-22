"""phase_j_telegram

Phase J: 텔레그램 개인 알림 시스템
- users 테이블에 telegram_chat_id, telegram_verified_at 컬럼 추가
- telegram_verifications 테이블 신규 생성

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-03-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users 테이블에 텔레그램 컬럼 추가
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("telegram_verified_at", sa.DateTime(timezone=True), nullable=True))

    # 텔레그램 연동 인증 코드 테이블
    op.create_table(
        "telegram_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_tg_verif_code", "telegram_verifications", ["code"])
    op.create_index("idx_tg_verif_user", "telegram_verifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_tg_verif_user", table_name="telegram_verifications")
    op.drop_index("idx_tg_verif_code", table_name="telegram_verifications")
    op.drop_table("telegram_verifications")
    op.drop_column("users", "telegram_verified_at")
    op.drop_column("users", "telegram_chat_id")
