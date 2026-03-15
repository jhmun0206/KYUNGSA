"""AuctionRound ORM 모델

경매 기일 이력. Auction과 1:N 관계.
DB-REBUILD: detail JSONB에 묻혀있던 기일 이력을 정규화 테이블로 분리.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base


class AuctionRound(Base):
    """경매 기일 1건"""

    __tablename__ = "auction_rounds"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    auction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    round_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    minimum_bid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)  # '진행중'/'유찰'/'매각'/'취하'/'변경'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 관계
    auction: Mapped[Auction] = relationship("Auction", back_populates="auction_rounds")

    __table_args__ = (
        UniqueConstraint("auction_id", "round_number", name="uq_auction_round"),
        Index("ix_auction_rounds_auction_id", "auction_id"),
        Index("ix_auction_rounds_date", "round_date"),
    )

    def __repr__(self) -> str:
        return f"<AuctionRound auction={self.auction_id} round={self.round_number} result={self.result}>"


from app.models.db.auction import Auction  # noqa: E402
