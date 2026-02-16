"""ORM 공통 베이스

DeclarativeBase + 공용 Mixin 정의.
SQLite 테스트 호환을 위해 JSONB → JSON 자동 전환 포함.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class JSONBOrJSON(TypeDecorator):
    """PostgreSQL에서는 JSONB, SQLite에서는 JSON으로 동작하는 타입"""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스 클래스"""

    type_annotation_map = {
        dict: JSONBOrJSON,
        list: JSONBOrJSON,
    }


class TimestampMixin:
    """created_at / updated_at 자동 관리 Mixin"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PrimaryKeyMixin:
    """UUID PK Mixin"""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
