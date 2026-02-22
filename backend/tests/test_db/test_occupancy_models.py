"""명도 ORM 모델 테스트"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.occupancy import OccupancyProperty, OccupancyReport, OccupancyTenant


def _make_auction(**overrides) -> Auction:
    defaults = {
        "case_number": "2022타경112169",
        "court": "서울중앙지방법원",
        "court_office_code": "B000210",
        "address": "서울특별시 중구 마장로1길 22",
        "property_type": "상가",
        "appraised_value": 500_000_000,
        "minimum_bid": 400_000_000,
        "status": "진행",
    }
    defaults.update(overrides)
    return Auction(**defaults)


def _ensure_auction(db_session: Session, case_number: str = "2022타경112169") -> Auction:
    """FK 만족을 위해 부모 Auction 생성 (이미 존재하면 반환)"""
    existing = db_session.query(Auction).filter_by(case_number=case_number).first()
    if existing:
        return existing
    auction = _make_auction(case_number=case_number)
    db_session.add(auction)
    db_session.flush()
    return auction


def _make_report(
    db_session: Session, case_number: str = "2022타경112169", **overrides
) -> OccupancyReport:
    _ensure_auction(db_session, case_number)
    defaults = {
        "case_number": case_number,
        "court_code": "B000210",
        "investigation_date": "2022년12월09일16시10분",
        "etc_note": "상가건물임대차 현황서에 등재된자를 일응 임차인으로 보고함.",
        "raw_json": {"data": "test"},
        "fetched_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return OccupancyReport(**defaults)


class TestOccupancyReportCRUD:
    """OccupancyReport 기본 CRUD"""

    def test_create_report(self, db_session: Session):
        report = _make_report(db_session)
        db_session.add(report)
        db_session.commit()

        result = db_session.query(OccupancyReport).first()
        assert result is not None
        assert result.case_number == "2022타경112169"
        assert result.court_code == "B000210"
        assert result.raw_json == {"data": "test"}

    def test_unique_case_number(self, db_session: Session):
        """사건번호 중복 방지"""
        db_session.add(_make_report(db_session))
        db_session.commit()

        with pytest.raises(Exception):
            db_session.add(_make_report(db_session))
            db_session.commit()


class TestOccupancyTenantCRUD:
    """OccupancyTenant 기본 CRUD"""

    def test_create_tenant(self, db_session: Session):
        report = _make_report(db_session)
        db_session.add(report)
        db_session.flush()

        tenant = OccupancyTenant(
            report_id=report.id,
            case_number="2022타경112169",
            property_index=1,
            tenant_name="김OO",
            party_type_code="01",
            party_type="임차인",
            occupied_part="1층 159호",
            usage_code="02",
            usage="점포",
            deposit=20_000_000,
            deposit_raw="2천만원",
            monthly_rent=1_650_000,
            monthly_rent_raw="165만원",
            move_in_date=date(2011, 8, 23),
            move_in_date_raw="2011.08.23",
            is_unknown=False,
        )
        db_session.add(tenant)
        db_session.commit()

        result = db_session.query(OccupancyTenant).first()
        assert result is not None
        assert result.tenant_name == "김OO"
        assert result.deposit == 20_000_000
        assert result.monthly_rent == 1_650_000
        assert result.move_in_date == date(2011, 8, 23)
        assert result.usage == "점포"


class TestOccupancyPropertyCRUD:
    """OccupancyProperty 기본 CRUD"""

    def test_create_property(self, db_session: Session):
        report = _make_report(db_session)
        db_session.add(report)
        db_session.flush()

        prop = OccupancyProperty(
            report_id=report.id,
            case_number="2022타경112169",
            property_index=1,
            address="서울특별시 중구 마장로1길 22, 1층159호",
            tenant_count=1,
            possession_code="05",
            possession_desc="채무자(소유자)점유, 임차인(별지)점유",
        )
        db_session.add(prop)
        db_session.commit()

        result = db_session.query(OccupancyProperty).first()
        assert result is not None
        assert result.tenant_count == 1
        assert result.possession_code == "05"


class TestRelationships:
    """관계 테스트"""

    def test_report_has_tenants(self, db_session: Session):
        report = _make_report(db_session)
        db_session.add(report)
        db_session.flush()

        tenant = OccupancyTenant(
            report_id=report.id,
            case_number="2022타경112169",
            tenant_name="김OO",
            party_type="임차인",
        )
        db_session.add(tenant)
        db_session.commit()

        loaded = db_session.query(OccupancyReport).first()
        assert len(loaded.tenants) == 1
        assert loaded.tenants[0].tenant_name == "김OO"

    def test_report_has_properties(self, db_session: Session):
        report = _make_report(db_session)
        db_session.add(report)
        db_session.flush()

        prop = OccupancyProperty(
            report_id=report.id,
            case_number="2022타경112169",
            property_index=1,
            tenant_count=0,
        )
        db_session.add(prop)
        db_session.commit()

        loaded = db_session.query(OccupancyReport).first()
        assert len(loaded.properties) == 1

    def test_cascade_delete(self, db_session: Session):
        """Report 삭제 시 Tenant/Property CASCADE"""
        report = _make_report(db_session)
        db_session.add(report)
        db_session.flush()

        db_session.add(OccupancyTenant(
            report_id=report.id,
            case_number="2022타경112169",
            tenant_name="김OO",
            party_type="임차인",
        ))
        db_session.add(OccupancyProperty(
            report_id=report.id,
            case_number="2022타경112169",
            property_index=1,
            tenant_count=0,
        ))
        db_session.commit()

        db_session.delete(report)
        db_session.commit()

        assert db_session.query(OccupancyReport).count() == 0
        assert db_session.query(OccupancyTenant).count() == 0
        assert db_session.query(OccupancyProperty).count() == 0


class TestAuctionOccupancyColumns:
    """Auction 테이블 명도 컬럼 테스트"""

    def test_default_values(self, db_session: Session):
        auction = _make_auction()
        db_session.add(auction)
        db_session.commit()

        loaded = db_session.query(Auction).first()
        assert loaded.occupancy_status == "분석대기"
        assert loaded.occupancy_tenant_count is None
        assert loaded.occupancy_risk_level is None

    def test_set_occupancy_fields(self, db_session: Session):
        auction = _make_auction()
        auction.occupancy_tenant_count = 2
        auction.occupancy_status = "분석완료"
        auction.occupancy_risk_level = "medium"
        db_session.add(auction)
        db_session.commit()

        loaded = db_session.query(Auction).first()
        assert loaded.occupancy_tenant_count == 2
        assert loaded.occupancy_status == "분석완료"
        assert loaded.occupancy_risk_level == "medium"
