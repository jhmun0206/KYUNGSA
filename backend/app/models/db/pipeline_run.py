"""PipelineRun ORM 모델

배치 실행 이력 추적. 5B에서 본격 사용.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.db.base import Base, JSONBOrJSON, PrimaryKeyMixin, TimestampMixin


class PipelineRun(PrimaryKeyMixin, TimestampMixin, Base):
    """배치 파이프라인 실행 이력"""

    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    court_code: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_searched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_enriched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_filtered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yellow_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    green_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")

    __table_args__ = (
        Index("ix_pipeline_runs_court_code", "court_code"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<PipelineRun {self.run_id} {self.status}>"
