"""ORM 모델 CRUD + 제약조건 테스트

SQLite in-memory로 실행. PostgreSQL 불필요.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.db.auction import Auction
from app.models.db.filter_result import FilterResultORM
from app.models.db.pipeline_run import PipelineRun
from app.models.db.registry import RegistryAnalysisORM, RegistryEventORM


def _make_auction(**overrides) -> Auction:
    defaults = {
        "case_number": "2026타경12345",
        "court": "서울중앙지방법원",
        "court_office_code": "B000210",
        "address": "서울 강남구 역삼동 123-4",
        "property_type": "아파트",
        "appraised_value": 500_000_000,
        "minimum_bid": 350_000_000,
        "auction_date": date(2026, 3, 15),
        "status": "진행",
        "bid_count": 2,
    }
    defaults.update(overrides)
    return Auction(**defaults)


class TestAuctionCRUD:
    """Auction 테이블 CRUD"""

    def test_create_and_read(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.commit()

        result = db_session.query(Auction).filter_by(case_number="2026타경12345").first()
        assert result is not None
        assert result.court == "서울중앙지방법원"
        assert result.appraised_value == 500_000_000
        assert result.bid_count == 2

    def test_unique_case_number(self, db_session):
        db_session.add(_make_auction())
        db_session.commit()
        db_session.add(_make_auction())
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_update(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.commit()

        auction.minimum_bid = 300_000_000
        auction.status = "유찰"
        db_session.commit()

        result = db_session.query(Auction).first()
        assert result.minimum_bid == 300_000_000
        assert result.status == "유찰"

    def test_delete(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.commit()

        db_session.delete(auction)
        db_session.commit()
        assert db_session.query(Auction).count() == 0

    def test_jsonb_columns(self, db_session):
        auction = _make_auction(
            coordinates={"x": "127.0", "y": "37.5"},
            building_info={"main_purpose": "업무시설", "violation": False},
            detail={"case_number": "2026타경12345", "court": "서울중앙지방법원"},
        )
        db_session.add(auction)
        db_session.commit()

        result = db_session.query(Auction).first()
        assert result.coordinates["x"] == "127.0"
        assert result.building_info["main_purpose"] == "업무시설"
        assert result.detail["case_number"] == "2026타경12345"

    def test_timestamps_auto_set(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.commit()

        result = db_session.query(Auction).first()
        assert result.created_at is not None
        assert result.updated_at is not None


class TestFilterResultCRUD:
    """FilterResult 테이블 CRUD"""

    def test_create_with_auction(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()

        fr = FilterResultORM(
            auction_id=auction.id,
            color="RED",
            passed=False,
            matched_rules=[{"rule_id": "R001", "rule_name": "그린벨트", "description": "개발제한구역"}],
            evaluated_at=datetime.now(timezone.utc),
        )
        db_session.add(fr)
        db_session.commit()

        result = db_session.query(FilterResultORM).first()
        assert result.color == "RED"
        assert result.passed is False
        assert len(result.matched_rules) == 1

    def test_cascade_delete(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()
        db_session.add(FilterResultORM(auction_id=auction.id, color="GREEN", passed=True))
        db_session.commit()

        db_session.delete(auction)
        db_session.commit()
        assert db_session.query(FilterResultORM).count() == 0

    def test_unique_auction_id(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()
        db_session.add(FilterResultORM(auction_id=auction.id, color="RED", passed=False))
        db_session.commit()
        db_session.add(FilterResultORM(auction_id=auction.id, color="GREEN", passed=True))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestRegistryEventCRUD:
    """RegistryEvent 테이블 CRUD"""

    def test_create_event(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()

        event = RegistryEventORM(
            auction_id=auction.id,
            section="GAPGU",
            rank_no=1,
            purpose="근저당권설정",
            event_type="근저당권설정",
            accepted_at="2024.01.15",
            holder="국민은행",
            amount=200_000_000,
            raw_text="1  근저당권설정  2024.01.15 ...",
        )
        db_session.add(event)
        db_session.commit()

        result = db_session.query(RegistryEventORM).first()
        assert result.section == "GAPGU"
        assert result.amount == 200_000_000

    def test_multiple_events(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()

        for i in range(3):
            db_session.add(RegistryEventORM(
                auction_id=auction.id,
                section="EULGU",
                rank_no=i + 1,
                purpose=f"근저당권설정{i}",
                raw_text=f"raw_{i}",
            ))
        db_session.commit()
        assert db_session.query(RegistryEventORM).count() == 3

    def test_cascade_delete(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()
        db_session.add(RegistryEventORM(
            auction_id=auction.id, section="GAPGU", purpose="압류", raw_text="raw"
        ))
        db_session.commit()

        db_session.delete(auction)
        db_session.commit()
        assert db_session.query(RegistryEventORM).count() == 0


class TestRegistryAnalysisCRUD:
    """RegistryAnalysis 테이블 CRUD"""

    def test_create_analysis(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()

        analysis = RegistryAnalysisORM(
            auction_id=auction.id,
            registry_unique_no="1234-5678-90",
            registry_match_confidence=0.9,
            has_hard_stop=True,
            hard_stop_flags=[{"rule_id": "HS001", "name": "예고등기", "description": "desc", "event": {}}],
            confidence="HIGH",
            summary="위험 물건",
        )
        db_session.add(analysis)
        db_session.commit()

        result = db_session.query(RegistryAnalysisORM).first()
        assert result.has_hard_stop is True
        assert result.registry_match_confidence == 0.9

    def test_unique_auction_id(self, db_session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.flush()
        db_session.add(RegistryAnalysisORM(auction_id=auction.id, has_hard_stop=False))
        db_session.commit()
        db_session.add(RegistryAnalysisORM(auction_id=auction.id, has_hard_stop=True))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPipelineRunCRUD:
    """PipelineRun 테이블 CRUD"""

    def test_create_run(self, db_session):
        run = PipelineRun(
            run_id="20260215_B000210",
            court_code="B000210",
            started_at=datetime.now(timezone.utc),
            total_searched=100,
            total_enriched=80,
            total_filtered=80,
            red_count=20,
            yellow_count=30,
            green_count=30,
            status="COMPLETED",
        )
        db_session.add(run)
        db_session.commit()

        result = db_session.query(PipelineRun).first()
        assert result.run_id == "20260215_B000210"
        assert result.total_searched == 100
        assert result.status == "COMPLETED"

    def test_unique_run_id(self, db_session):
        db_session.add(PipelineRun(run_id="run1", court_code="B000210"))
        db_session.commit()
        db_session.add(PipelineRun(run_id="run1", court_code="B000211"))
        with pytest.raises(IntegrityError):
            db_session.commit()
