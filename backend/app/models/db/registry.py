"""Registry ORM 모델

RegistryEvent (정규화) + RegistryAnalysis (1:1).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, JSONBOrJSON, PrimaryKeyMixin


class RegistryEventORM(PrimaryKeyMixin, Base):
    """등기 이벤트 (정규화 테이블)"""

    __tablename__ = "registry_events"

    auction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(10), nullable=False)  # GAPGU/EULGU
    rank_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="기타")
    accepted_at: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 자유포맷 "2024.01.15"
    receipt_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    holder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    canceled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 관계
    auction: Mapped[Auction] = relationship("Auction", back_populates="registry_events")

    __table_args__ = (
        Index("ix_registry_events_event_type", "event_type"),
        Index("ix_registry_events_accepted_at", "accepted_at"),
        Index("ix_registry_events_auction_section_rank", "auction_id", "section", "rank_no"),
    )

    def __repr__(self) -> str:
        return f"<RegistryEventORM {self.event_type} rank={self.rank_no}>"


class RegistryAnalysisORM(PrimaryKeyMixin, Base):
    """등기부 분석 결과 (Auction과 1:1)"""

    __tablename__ = "registry_analyses"

    auction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("auctions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    registry_unique_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registry_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    cancellation_base_event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("registry_events.id"), nullable=True
    )
    has_hard_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hard_stop_flags: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, default="HIGH")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extinguished_rights: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    surviving_rights: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    uncertain_rights: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 관계
    auction: Mapped[Auction] = relationship("Auction", back_populates="registry_analysis")
    cancellation_base_event: Mapped[RegistryEventORM | None] = relationship(
        "RegistryEventORM", foreign_keys=[cancellation_base_event_id]
    )

    __table_args__ = (
        Index("ix_registry_analyses_has_hard_stop", "has_hard_stop"),
    )

    def __repr__(self) -> str:
        return f"<RegistryAnalysisORM auction={self.auction_id} hard_stop={self.has_hard_stop}>"


from app.models.db.auction import Auction  # noqa: E402
