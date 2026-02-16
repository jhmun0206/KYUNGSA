"""Auction ORM 모델

경매 물건 핵심 엔티티. 정규화 컬럼 + JSONB 하이브리드.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, JSONBOrJSON, PrimaryKeyMixin, TimestampMixin


class Auction(PrimaryKeyMixin, TimestampMixin, Base):
    """경매 물건"""

    __tablename__ = "auctions"

    # 정규화 컬럼 (WHERE / ORDER BY 대상)
    case_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    court: Mapped[str] = mapped_column(String(100), nullable=False)
    court_office_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    property_type: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    appraised_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    minimum_bid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    auction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    bid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # JSONB 컬럼 (중첩 구조)
    coordinates: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    building_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    land_use_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    market_price_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)

    # 관계
    filter_result: Mapped[FilterResultORM | None] = relationship(
        "FilterResultORM", back_populates="auction", uselist=False, cascade="all, delete-orphan"
    )
    registry_events: Mapped[list[RegistryEventORM]] = relationship(
        "RegistryEventORM", back_populates="auction", cascade="all, delete-orphan"
    )
    registry_analysis: Mapped[RegistryAnalysisORM | None] = relationship(
        "RegistryAnalysisORM", back_populates="auction", uselist=False, cascade="all, delete-orphan"
    )
    score: Mapped[Score | None] = relationship(
        "Score", back_populates="auction", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_auctions_court", "court"),
        Index("ix_auctions_court_office_code", "court_office_code"),
        Index("ix_auctions_property_type", "property_type"),
        Index("ix_auctions_auction_date", "auction_date"),
        Index("ix_auctions_status", "status"),
        Index("ix_auctions_court_date", "court_office_code", "auction_date"),
        Index("ix_auctions_status_date", "status", "auction_date"),
    )

    def __repr__(self) -> str:
        return f"<Auction {self.case_number}>"


# 순환 참조 해소용 - 모듈 로딩 후 참조
from app.models.db.filter_result import FilterResultORM  # noqa: E402
from app.models.db.registry import RegistryAnalysisORM, RegistryEventORM  # noqa: E402
from app.models.db.score import Score  # noqa: E402
