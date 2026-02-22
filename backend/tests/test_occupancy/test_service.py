"""OccupancyService 테스트"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.occupancy import OccupancyProperty, OccupancyReport, OccupancyTenant
from app.services.occupancy.service import OccupancyService

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture() -> dict:
    with open(FIXTURE_DIR / "occupancy_response.json", encoding="utf-8") as f:
        return json.load(f)


def _make_auction(db_session: Session, case_number: str = "2022타경112169") -> Auction:
    """FK 만족을 위해 부모 Auction 생성"""
    existing = db_session.query(Auction).filter_by(case_number=case_number).first()
    if existing:
        return existing
    auction = Auction(
        case_number=case_number,
        court="서울중앙지방법원",
        court_office_code="B000210",
        address="서울특별시 중구 마장로1길 22",
        property_type="상가",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
        status="진행",
    )
    db_session.add(auction)
    db_session.flush()
    return auction


def _make_service(db_session: Session, raw_response: dict | None = None) -> OccupancyService:
    """mock crawler로 OccupancyService 생성"""
    crawler = MagicMock()
    crawler.fetch_occupancy_report.return_value = raw_response
    return OccupancyService(db=db_session, crawler=crawler)


class TestCollectAndSave:
    """collect_and_save 정상 동작"""

    def test_normal(self, db_session: Session):
        """정상 수집 + DB 저장"""
        _make_auction(db_session)
        fixture = _load_fixture()
        svc = _make_service(db_session, fixture)

        report = svc.collect_and_save(
            internal_case_number="20220130112176",
            court_office_code="B000210",
            property_sequence="1",
            formatted_case_number="2022타경112169",
        )

        assert report is not None
        assert report.case_number == "2022타경112169"

        # 임차인 3명 저장 확인
        tenants = db_session.query(OccupancyTenant).all()
        assert len(tenants) == 3
        assert tenants[0].tenant_name == "김OO"

        # 물건 1건 저장 확인
        props = db_session.query(OccupancyProperty).all()
        assert len(props) == 1

    def test_empty_response_returns_none(self, db_session: Session):
        """빈 응답이면 None 반환"""
        _make_auction(db_session)
        svc = _make_service(db_session, None)

        result = svc.collect_and_save(
            internal_case_number="20220130112176",
            court_office_code="B000210",
            property_sequence="1",
            formatted_case_number="2022타경112169",
        )

        assert result is None
        assert db_session.query(OccupancyReport).count() == 0

    def test_auction_status_updated(self, db_session: Session):
        """auction.occupancy_status 업데이트 확인"""
        auction = _make_auction(db_session)
        assert auction.occupancy_status == "분석대기"

        fixture = _load_fixture()
        svc = _make_service(db_session, fixture)
        svc.collect_and_save(
            internal_case_number="20220130112176",
            court_office_code="B000210",
            property_sequence="1",
            formatted_case_number="2022타경112169",
        )

        db_session.refresh(auction)
        assert auction.occupancy_status == "분석완료"
        assert auction.occupancy_tenant_count == 3


class TestUpsert:
    """재수집 시 upsert 동작"""

    def test_upsert_deletes_old(self, db_session: Session):
        """재수집 시 기존 삭제 → 신규 저장"""
        _make_auction(db_session)
        fixture = _load_fixture()

        # 1차 수집
        svc1 = _make_service(db_session, fixture)
        svc1.collect_and_save(
            internal_case_number="20220130112176",
            court_office_code="B000210",
            property_sequence="1",
            formatted_case_number="2022타경112169",
        )
        assert db_session.query(OccupancyReport).count() == 1
        assert db_session.query(OccupancyTenant).count() == 3

        # 2차 수집 (동일 사건번호)
        svc2 = _make_service(db_session, fixture)
        svc2.collect_and_save(
            internal_case_number="20220130112176",
            court_office_code="B000210",
            property_sequence="1",
            formatted_case_number="2022타경112169",
        )

        # Report 1건, Tenant 3명 유지 (중복 없음)
        assert db_session.query(OccupancyReport).count() == 1
        assert db_session.query(OccupancyTenant).count() == 3


class TestRelationships:
    """ORM 관계 확인"""

    def test_cascade_loaded(self, db_session: Session):
        """report.tenants / report.properties 관계 로딩"""
        _make_auction(db_session)
        fixture = _load_fixture()
        svc = _make_service(db_session, fixture)

        report = svc.collect_and_save(
            internal_case_number="20220130112176",
            court_office_code="B000210",
            property_sequence="1",
            formatted_case_number="2022타경112169",
        )

        loaded = db_session.query(OccupancyReport).first()
        assert len(loaded.tenants) == 3
        assert len(loaded.properties) == 1
        assert loaded.tenants[0].tenant_name == "김OO"
