"""공용 DB 테스트 픽스처

SQLite in-memory로 ORM 모델 테스트.
Mac 개발 환경에 PostgreSQL 불필요.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.db.base import Base


@pytest.fixture(scope="function")
def db_session() -> Session:
    """SQLite in-memory DB 세션 (테스트당 새 DB)"""
    engine = create_engine("sqlite://", echo=False)

    # SQLite에서 FK 제약 활성화
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
