"""데이터베이스 세션 관리

Sync 전용 (psycopg2). 5A~5F 전 단계에서 sync 통일.
async 전환은 Phase 8+ 대시보드에서 검토.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends용 DB 세션 팩토리"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
