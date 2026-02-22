"""Phase 7 명도 데이터 테이블 + auctions 컬럼 추가

occupancy_reports, occupancy_tenants, occupancy_properties 3개 테이블 생성.
auctions 테이블에 occupancy_tenant_count, occupancy_status, occupancy_risk_level 추가.

Revision ID: f7a1b2c3d4e5
Revises: e5a2c947f310
Create Date: 2026-02-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a1b2c3d4e5"
down_revision: Union[str, None] = "e5a2c947f310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- occupancy_reports ---
    op.create_table(
        "occupancy_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "case_number",
            sa.String(50),
            sa.ForeignKey("auctions.case_number"),
            unique=True,
            nullable=False,
        ),
        sa.Column("court_code", sa.String(20), nullable=False, server_default=""),
        sa.Column("investigation_date", sa.String(100), nullable=True),
        sa.Column("etc_note", sa.Text, nullable=True),
        sa.Column("raw_json", sa.JSON, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_occupancy_reports_case_number",
        "occupancy_reports",
        ["case_number"],
    )

    # --- occupancy_tenants ---
    op.create_table(
        "occupancy_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "report_id",
            sa.String(36),
            sa.ForeignKey("occupancy_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_number", sa.String(50), nullable=False),
        sa.Column("property_index", sa.Integer, nullable=False, server_default="1"),
        sa.Column("tenant_name", sa.String(50), nullable=False, server_default=""),
        sa.Column("party_type_code", sa.String(10), nullable=True),
        sa.Column("party_type", sa.String(20), nullable=False, server_default="미상"),
        sa.Column("occupied_part", sa.String(200), nullable=True),
        sa.Column("usage_code", sa.String(10), nullable=True),
        sa.Column("usage", sa.String(50), nullable=False, server_default="미상"),
        sa.Column("deposit", sa.BigInteger, nullable=True),
        sa.Column("deposit_raw", sa.String(100), nullable=True),
        sa.Column("monthly_rent", sa.BigInteger, nullable=True),
        sa.Column("monthly_rent_raw", sa.String(100), nullable=True),
        sa.Column("move_in_date", sa.Date, nullable=True),
        sa.Column("move_in_date_raw", sa.String(50), nullable=True),
        sa.Column("fixed_date", sa.Date, nullable=True),
        sa.Column("fixed_date_raw", sa.String(50), nullable=True),
        sa.Column("is_unknown", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("raw_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_occupancy_tenants_report_id", "occupancy_tenants", ["report_id"]
    )
    op.create_index(
        "ix_occupancy_tenants_case_number", "occupancy_tenants", ["case_number"]
    )

    # --- occupancy_properties ---
    op.create_table(
        "occupancy_properties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "report_id",
            sa.String(36),
            sa.ForeignKey("occupancy_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_number", sa.String(50), nullable=False),
        sa.Column("property_index", sa.Integer, nullable=False, server_default="1"),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("tenant_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("possession_code", sa.String(10), nullable=True),
        sa.Column("possession_desc", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_occupancy_properties_report_id", "occupancy_properties", ["report_id"]
    )
    op.create_index(
        "ix_occupancy_properties_case_number",
        "occupancy_properties",
        ["case_number"],
    )

    # --- auctions 테이블에 명도 컬럼 추가 ---
    op.add_column(
        "auctions", sa.Column("occupancy_tenant_count", sa.Integer, nullable=True)
    )
    op.add_column(
        "auctions",
        sa.Column(
            "occupancy_status",
            sa.String(20),
            nullable=False,
            server_default="분석대기",
        ),
    )
    op.add_column(
        "auctions", sa.Column("occupancy_risk_level", sa.String(10), nullable=True)
    )
    op.create_index(
        "ix_auctions_occupancy_status", "auctions", ["occupancy_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_auctions_occupancy_status", table_name="auctions")
    op.drop_column("auctions", "occupancy_risk_level")
    op.drop_column("auctions", "occupancy_status")
    op.drop_column("auctions", "occupancy_tenant_count")

    op.drop_index(
        "ix_occupancy_properties_case_number", table_name="occupancy_properties"
    )
    op.drop_index(
        "ix_occupancy_properties_report_id", table_name="occupancy_properties"
    )
    op.drop_table("occupancy_properties")

    op.drop_index(
        "ix_occupancy_tenants_case_number", table_name="occupancy_tenants"
    )
    op.drop_index(
        "ix_occupancy_tenants_report_id", table_name="occupancy_tenants"
    )
    op.drop_table("occupancy_tenants")

    op.drop_index(
        "ix_occupancy_reports_case_number", table_name="occupancy_reports"
    )
    op.drop_table("occupancy_reports")
