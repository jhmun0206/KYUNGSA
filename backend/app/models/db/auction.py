"""Auction ORM 모델

경매 물건 핵심 엔티티. 정규화 컬럼 + JSONB 하이브리드.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, Float, Index, Integer, String, Text
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

    # 낙찰결과 컬럼 (Phase 6.5)
    winning_bid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    winning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    winning_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    winning_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'court_api'

    # 명도 관련 (Phase 7)
    occupancy_tenant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occupancy_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="분석대기"
    )
    occupancy_risk_level: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )

    # JSONB 컬럼 (중첩 구조)
    coordinates: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    building_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    land_use_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    market_price_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    rent_price_info: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)  # json→jsonb (BUG-03, PostgreSQL에서 JSONB로 저장)
    detail: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    location_data: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)  # BUG-02 수정

    # 정규화 컬럼 (DB-REBUILD: 검색/필터/정렬 최적화)
    property_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    building_type: Mapped[str | None] = mapped_column(String(10), nullable=True)   # '일반'/'집합'
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    station_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    build_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exclusive_area_m2_real: Mapped[float | None] = mapped_column(Float, nullable=True)  # BUG-01 수정
    floor_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_count_real: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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
    occupancy_reports: Mapped[list[OccupancyReport]] = relationship(
        "OccupancyReport", cascade="all, delete-orphan"
    )

    # 관계 (auction_rounds)
    auction_rounds: Mapped[list[AuctionRound]] = relationship(
        "AuctionRound", back_populates="auction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_auctions_court", "court"),
        Index("ix_auctions_court_office_code", "court_office_code"),
        Index("ix_auctions_property_type", "property_type"),
        Index("ix_auctions_auction_date", "auction_date"),
        Index("ix_auctions_status", "status"),
        Index("ix_auctions_court_date", "court_office_code", "auction_date"),
        Index("ix_auctions_status_date", "status", "auction_date"),
        Index("ix_auctions_occupancy_status", "occupancy_status"),
        Index("ix_auctions_property_category", "property_category"),
        Index("ix_auctions_lat_lng", "lat", "lng"),
        Index("ix_auctions_build_year", "build_year"),
        Index("ix_auctions_station_distance", "station_distance_m"),
    )

    def __repr__(self) -> str:
        return f"<Auction {self.case_number}>"


# 순환 참조 해소용 - 모듈 로딩 후 참조
from app.models.db.auction_round import AuctionRound  # noqa: E402
from app.models.db.filter_result import FilterResultORM  # noqa: E402
from app.models.db.occupancy import OccupancyReport  # noqa: E402
from app.models.db.registry import RegistryAnalysisORM, RegistryEventORM  # noqa: E402
from app.models.db.score import Score  # noqa: E402
