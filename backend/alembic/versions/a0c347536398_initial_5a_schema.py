"""initial_5a_schema

5A: 경매 큐레이션 핵심 5개 테이블 생성.
auctions, filter_results, registry_events, registry_analyses, pipeline_runs.

Revision ID: a0c347536398
Revises:
Create Date: 2026-02-15 22:00:59.167788
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a0c347536398"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """5A 스키마 생성"""

    # --- auctions ---
    op.create_table(
        "auctions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_number", sa.String(50), unique=True, nullable=False),
        sa.Column("court", sa.String(100), nullable=False),
        sa.Column("court_office_code", sa.String(20), nullable=False, server_default=""),
        sa.Column("address", sa.Text, nullable=False, server_default=""),
        sa.Column("property_type", sa.String(50), nullable=False, server_default=""),
        sa.Column("appraised_value", sa.BigInteger, nullable=True),
        sa.Column("minimum_bid", sa.BigInteger, nullable=True),
        sa.Column("auction_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=""),
        sa.Column("bid_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("coordinates", postgresql.JSONB, nullable=True),
        sa.Column("building_info", postgresql.JSONB, nullable=True),
        sa.Column("land_use_info", postgresql.JSONB, nullable=True),
        sa.Column("market_price_info", postgresql.JSONB, nullable=True),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auctions_court", "auctions", ["court"])
    op.create_index("ix_auctions_court_office_code", "auctions", ["court_office_code"])
    op.create_index("ix_auctions_property_type", "auctions", ["property_type"])
    op.create_index("ix_auctions_auction_date", "auctions", ["auction_date"])
    op.create_index("ix_auctions_status", "auctions", ["status"])
    op.create_index("ix_auctions_court_date", "auctions", ["court_office_code", "auction_date"])
    op.create_index("ix_auctions_status_date", "auctions", ["status", "auction_date"])

    # --- filter_results ---
    op.create_table(
        "filter_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("color", sa.String(10), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("matched_rules", postgresql.JSONB, nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_filter_results_color", "filter_results", ["color"])
    op.create_index("ix_filter_results_evaluated_at", "filter_results", ["evaluated_at"])

    # --- registry_events ---
    op.create_table(
        "registry_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(10), nullable=False),
        sa.Column("rank_no", sa.Integer, nullable=True),
        sa.Column("purpose", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False, server_default="기타"),
        sa.Column("accepted_at", sa.String(20), nullable=True),
        sa.Column("receipt_no", sa.String(50), nullable=True),
        sa.Column("cause", sa.Text, nullable=True),
        sa.Column("holder", sa.String(200), nullable=True),
        sa.Column("amount", sa.BigInteger, nullable=True),
        sa.Column("canceled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("raw_text", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_registry_events_event_type", "registry_events", ["event_type"])
    op.create_index("ix_registry_events_accepted_at", "registry_events", ["accepted_at"])
    op.create_index("ix_registry_events_auction_section_rank", "registry_events", ["auction_id", "section", "rank_no"])

    # --- registry_analyses ---
    op.create_table(
        "registry_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("registry_unique_no", sa.String(100), nullable=True),
        sa.Column("registry_match_confidence", sa.Float, nullable=True),
        sa.Column("cancellation_base_event_id", sa.String(36), sa.ForeignKey("registry_events.id"), nullable=True),
        sa.Column("has_hard_stop", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("hard_stop_flags", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="HIGH"),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("extinguished_rights", postgresql.JSONB, nullable=True),
        sa.Column("surviving_rights", postgresql.JSONB, nullable=True),
        sa.Column("uncertain_rights", postgresql.JSONB, nullable=True),
        sa.Column("warnings", postgresql.JSONB, nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_registry_analyses_has_hard_stop", "registry_analyses", ["has_hard_stop"])

    # --- pipeline_runs ---
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(100), unique=True, nullable=False),
        sa.Column("court_code", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_searched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_enriched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_filtered", sa.Integer, nullable=False, server_default="0"),
        sa.Column("red_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("yellow_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("green_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pipeline_runs_court_code", "pipeline_runs", ["court_code"])
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])


def downgrade() -> None:
    """5A 스키마 제거"""
    op.drop_table("registry_analyses")
    op.drop_table("registry_events")
    op.drop_table("filter_results")
    op.drop_table("pipeline_runs")
    op.drop_table("auctions")
