"""현황조사서 JSON 응답 파서

courtauction.go.kr selectCurstExmndc.on 응답을 OccupancyReportDTO로 변환.
stateless — I/O 없이 dict → DTO 변환만 수행.
"""

from __future__ import annotations

import logging

from app.models.occupancy_dto import (
    OccupancyPropertyDTO,
    OccupancyReportDTO,
    OccupancyTenantDTO,
)
from app.utils.date_parser import parse_korean_date
from app.utils.money_parser import parse_korean_money
from app.utils.privacy import mask_name
from app.utils.text_utils import strip_html

logger = logging.getLogger(__name__)

# 관계인 유형 코드 → 텍스트 매핑
PARTY_TYPE_MAP: dict[str, str] = {
    "01": "임차인",
    "02": "채무자",
    "03": "소유자",
    "04": "점유자",
    "05": "전차인",
    "06": "대항력있는 임차인",
}

# 용도 코드 → 텍스트 매핑
USAGE_MAP: dict[str, str] = {
    "01": "주거",
    "02": "점포",
    "03": "사무실",
    "04": "공장",
    "05": "창고",
    "06": "기타",
}


class OccupancyParser:
    """현황조사서 JSON 응답 파서"""

    def parse(
        self, data: dict, case_number: str, court_code: str
    ) -> OccupancyReportDTO:
        """raw API 응답 → OccupancyReportDTO

        Args:
            data: selectCurstExmndc.on 응답 dict
            case_number: 포맷된 사건번호 (DB 저장용, 예: "2022타경112169")
            court_code: 법원코드 (예: "B000210")

        Returns:
            OccupancyReportDTO
        """
        # 조사일, 기타사항 추출
        investigation_date = (
            data.get("dma_curstExmndcInfo", {}).get("curstExmndcDt", "")
            or ""
        ).strip() or None

        etc_note_raw = (
            data.get("dma_curstExmndcInfo", {}).get("lesDts", "") or ""
        )
        etc_note = strip_html(etc_note_raw) or None

        # 임차인 목록 파싱
        tenant_list = data.get("dlt_curstExmndcDtl", [])
        tenants: list[OccupancyTenantDTO] = []
        for idx, item in enumerate(tenant_list):
            try:
                tenant = self._parse_tenant(item, idx + 1)
                tenants.append(tenant)
            except Exception:
                logger.warning(
                    "임차인 파싱 실패 [%s] idx=%d: %s",
                    case_number,
                    idx,
                    item,
                    exc_info=True,
                )
                continue

        # 물건별 점유관계 파싱
        prop_list = data.get("dlt_gdsPossCtt", [])
        properties: list[OccupancyPropertyDTO] = []
        for idx, item in enumerate(prop_list):
            try:
                prop = self._parse_property(item, idx + 1)
                properties.append(prop)
            except Exception:
                logger.warning(
                    "점유관계 파싱 실패 [%s] idx=%d", case_number, idx, exc_info=True
                )
                continue

        return OccupancyReportDTO(
            case_number=case_number,
            court_code=court_code,
            investigation_date=investigation_date,
            etc_note=etc_note,
            tenants=tenants,
            properties=properties,
            raw_json=data,
        )

    def _parse_tenant(self, item: dict, default_index: int) -> OccupancyTenantDTO:
        """단일 임차인 파싱"""
        # 물건 순서
        prop_idx_raw = item.get("dspslGdsSeq", "")
        property_index = int(prop_idx_raw) if prop_idx_raw else default_index

        # 이름 마스킹
        raw_name = item.get("relPrtsNm", "") or ""
        tenant_name = mask_name(raw_name.strip())

        # 관계인 유형
        party_type_code = item.get("relPrtsCd", "") or None
        party_type = PARTY_TYPE_MAP.get(party_type_code or "", "미상")

        # 점유 부분
        occupied_part = (item.get("occptnPrtDts", "") or "").strip() or None

        # 용도
        usage_code = item.get("usgCd", "") or None
        usage = USAGE_MAP.get(usage_code or "", item.get("usgNm", "미상") or "미상")

        # 보증금
        deposit_raw = (item.get("dpstAmt", "") or "").strip() or None
        deposit = parse_korean_money(deposit_raw)

        # 월세
        rent_raw = (item.get("mnthlyRntAmt", "") or "").strip() or None
        monthly_rent = parse_korean_money(rent_raw)

        # 전입일
        move_in_raw = (item.get("mvnDt", "") or "").strip() or None
        move_in_date = parse_korean_date(move_in_raw)

        # 확정일자
        fixed_raw = (item.get("fxdDt", "") or "").strip() or None
        fixed_date = parse_korean_date(fixed_raw)

        # 미상 판별: 이름이 비어있거나 "미상"이면
        is_unknown = not raw_name.strip() or raw_name.strip() == "미상"

        return OccupancyTenantDTO(
            property_index=property_index,
            tenant_name=tenant_name,
            party_type_code=party_type_code,
            party_type=party_type,
            occupied_part=occupied_part,
            usage_code=usage_code,
            usage=usage,
            deposit=deposit,
            deposit_raw=deposit_raw,
            monthly_rent=monthly_rent,
            monthly_rent_raw=rent_raw,
            move_in_date=move_in_date,
            move_in_date_raw=move_in_raw,
            fixed_date=fixed_date,
            fixed_date_raw=fixed_raw,
            is_unknown=is_unknown,
            raw_json=item,
        )

    def _parse_property(self, item: dict, default_index: int) -> OccupancyPropertyDTO:
        """단일 물건 점유관계 파싱"""
        prop_idx_raw = item.get("dspslGdsSeq", "")
        property_index = int(prop_idx_raw) if prop_idx_raw else default_index

        address = (item.get("printSt", "") or "").strip() or None

        tenant_count_raw = item.get("relPrtsCnt", "0")
        try:
            tenant_count = int(tenant_count_raw)
        except (ValueError, TypeError):
            tenant_count = 0

        possession_code = item.get("gdsPossCd", "") or None
        possession_desc_raw = item.get("gdsPossCtt", "") or ""
        possession_desc = strip_html(possession_desc_raw) or None

        return OccupancyPropertyDTO(
            property_index=property_index,
            address=address,
            tenant_count=tenant_count,
            possession_code=possession_code,
            possession_desc=possession_desc,
        )
