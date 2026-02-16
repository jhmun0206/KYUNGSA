"""FilterResult ORM 모델

1단 필터링 결과. Auction과 1:1 관계.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, JSONBOrJSON, PrimaryKeyMixin


class FilterResultORM(PrimaryKeyMixin, Base):
    """1단 필터링 결과"""

    __tablename__ = "filter_results"

    auction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("auctions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    color: Mapped[str] = mapped_column(String(10), nullable=False)  # RED/YELLOW/GREEN
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    matched_rules: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 관계
    auction: Mapped[Auction] = relationship("Auction", back_populates="filter_result")

    __table_args__ = (
        Index("ix_filter_results_color", "color"),
        Index("ix_filter_results_evaluated_at", "evaluated_at"),
    )

    def __repr__(self) -> str:
        return f"<FilterResultORM {self.color} auction={self.auction_id}>"


from app.models.db.auction import Auction  # noqa: E402
