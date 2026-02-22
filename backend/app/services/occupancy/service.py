"""현황조사서 수집 → 파싱 → DB 저장 서비스

CourtAuctionClient.fetch_occupancy_report() → OccupancyParser → ORM 저장.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.occupancy import OccupancyProperty, OccupancyReport, OccupancyTenant
from app.models.occupancy_dto import OccupancyReportDTO
from app.services.crawler.court_auction import CourtAuctionClient
from app.services.occupancy.parser import OccupancyParser

logger = logging.getLogger(__name__)


class OccupancyService:
    """현황조사서 수집/파싱/저장 오케스트레이터"""

    def __init__(self, db: Session, crawler: CourtAuctionClient) -> None:
        self._db = db
        self._crawler = crawler
        self._parser = OccupancyParser()

    def collect_and_save(
        self,
        internal_case_number: str,
        court_office_code: str,
        property_sequence: str,
        formatted_case_number: str,
    ) -> OccupancyReport | None:
        """현황조사서 1건 수집 → 파싱 → DB 저장

        Args:
            internal_case_number: 내부 사건번호 (예: "20220130112176")
            court_office_code: 법원코드 (예: "B000210")
            property_sequence: 물건순서 (예: "1")
            formatted_case_number: 포맷된 사건번호 (예: "2022타경112169")

        Returns:
            저장된 OccupancyReport ORM 또는 현황조사서 없으면 None
        """
        # 1. API 호출
        raw = self._crawler.fetch_occupancy_report(
            internal_case_number, court_office_code, property_sequence
        )

        # 2. 빈 응답 체크 (현황조사서 없는 물건)
        if not raw:
            logger.info("현황조사서 응답 없음: %s", formatted_case_number)
            return None

        tenant_list = raw.get("dlt_curstExmndcDtl", [])
        if not tenant_list:
            logger.info("현황조사서 임차인 없음: %s", formatted_case_number)
            # 임차인 없어도 점유관계 데이터는 있을 수 있으므로 계속 진행

        # 3. 파싱
        dto = self._parser.parse(raw, formatted_case_number, court_office_code)

        # 4. DB 저장
        report = self._save_report(dto)

        logger.info(
            "현황조사서 저장 완료 [%s]: 임차인 %d명, 물건 %d건",
            formatted_case_number,
            len(dto.tenants),
            len(dto.properties),
        )
        return report

    def _save_report(self, dto: OccupancyReportDTO) -> OccupancyReport:
        """DTO → ORM 저장 (upsert: 기존 삭제 → 신규 생성)"""
        # 기존 삭제 (cascade: tenants + properties 자동 삭제)
        existing = (
            self._db.query(OccupancyReport)
            .filter_by(case_number=dto.case_number)
            .first()
        )
        if existing:
            self._db.delete(existing)
            self._db.flush()

        # Report 생성
        report = OccupancyReport(
            case_number=dto.case_number,
            court_code=dto.court_code,
            investigation_date=dto.investigation_date,
            etc_note=dto.etc_note,
            raw_json=dto.raw_json,
            fetched_at=datetime.now(timezone.utc),
        )
        self._db.add(report)
        self._db.flush()  # id 획득

        # Tenants 생성
        for t in dto.tenants:
            self._db.add(
                OccupancyTenant(
                    report_id=report.id,
                    case_number=dto.case_number,
                    property_index=t.property_index,
                    tenant_name=t.tenant_name,
                    party_type_code=t.party_type_code,
                    party_type=t.party_type,
                    occupied_part=t.occupied_part,
                    usage_code=t.usage_code,
                    usage=t.usage,
                    deposit=t.deposit,
                    deposit_raw=t.deposit_raw,
                    monthly_rent=t.monthly_rent,
                    monthly_rent_raw=t.monthly_rent_raw,
                    move_in_date=t.move_in_date,
                    move_in_date_raw=t.move_in_date_raw,
                    fixed_date=t.fixed_date,
                    fixed_date_raw=t.fixed_date_raw,
                    is_unknown=t.is_unknown,
                    raw_json=t.raw_json,
                )
            )

        # Properties 생성
        for p in dto.properties:
            self._db.add(
                OccupancyProperty(
                    report_id=report.id,
                    case_number=dto.case_number,
                    property_index=p.property_index,
                    address=p.address,
                    tenant_count=p.tenant_count,
                    possession_code=p.possession_code,
                    possession_desc=p.possession_desc,
                )
            )

        # Auction 상태 업데이트
        auction = (
            self._db.query(Auction)
            .filter_by(case_number=dto.case_number)
            .first()
        )
        if auction:
            auction.occupancy_tenant_count = len(dto.tenants)
            auction.occupancy_status = "분석완료"

        self._db.commit()
        self._db.refresh(report)
        return report
