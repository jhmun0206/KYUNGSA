"""명도 데이터 ORM 모델

현황조사서 API 응답을 저장하는 3개 테이블.
occupancy_reports (1:N) → occupancy_tenants, occupancy_properties
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, JSONBOrJSON, PrimaryKeyMixin, TimestampMixin


class OccupancyReport(PrimaryKeyMixin, TimestampMixin, Base):
    """현황조사서 리포트 (사건당 1건)"""

    __tablename__ = "occupancy_reports"

    case_number: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("auctions.case_number"),
        unique=True,
        nullable=False,
    )
    court_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    investigation_date: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # 원본 텍스트 그대로
    etc_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # lesDts
    raw_json: Mapped[dict] = mapped_column(JSONBOrJSON, nullable=False)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 관계
    auction: Mapped[Auction] = relationship(
        "Auction", back_populates="occupancy_reports"
    )
    tenants: Mapped[list[OccupancyTenant]] = relationship(
        "OccupancyTenant",
        back_populates="report",
        cascade="all, delete-orphan",
    )
    properties: Mapped[list[OccupancyProperty]] = relationship(
        "OccupancyProperty",
        back_populates="report",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_occupancy_reports_case_number", "case_number"),
    )

    def __repr__(self) -> str:
        return f"<OccupancyReport {self.case_number}>"


class OccupancyTenant(PrimaryKeyMixin, TimestampMixin, Base):
    """임차인 정보"""

    __tablename__ = "occupancy_tenants"

    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("occupancy_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_number: Mapped[str] = mapped_column(String(50), nullable=False)
    property_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tenant_name: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )  # 마스킹
    party_type_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    party_type: Mapped[str] = mapped_column(String(20), nullable=False, default="미상")
    occupied_part: Mapped[str | None] = mapped_column(String(200), nullable=True)
    usage_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    usage: Mapped[str] = mapped_column(String(50), nullable=False, default="미상")
    deposit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deposit_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monthly_rent: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    monthly_rent_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    move_in_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    move_in_date_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fixed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fixed_date_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_json: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)

    # 관계
    report: Mapped[OccupancyReport] = relationship(
        "OccupancyReport", back_populates="tenants"
    )

    __table_args__ = (
        Index("ix_occupancy_tenants_report_id", "report_id"),
        Index("ix_occupancy_tenants_case_number", "case_number"),
    )

    def __repr__(self) -> str:
        return f"<OccupancyTenant {self.tenant_name} case={self.case_number}>"


class OccupancyProperty(PrimaryKeyMixin, TimestampMixin, Base):
    """물건별 점유관계"""

    __tablename__ = "occupancy_properties"

    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("occupancy_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_number: Mapped[str] = mapped_column(String(50), nullable=False)
    property_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    possession_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    possession_desc: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # HTML 제거

    # 관계
    report: Mapped[OccupancyReport] = relationship(
        "OccupancyReport", back_populates="properties"
    )

    __table_args__ = (
        Index("ix_occupancy_properties_report_id", "report_id"),
        Index("ix_occupancy_properties_case_number", "case_number"),
    )

    def __repr__(self) -> str:
        return f"<OccupancyProperty idx={self.property_index} case={self.case_number}>"


# 순환 참조 해소
from app.models.db.auction import Auction  # noqa: E402
