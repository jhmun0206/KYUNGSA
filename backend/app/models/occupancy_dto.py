"""현황조사서 API 응답 DTO

courtauction.go.kr selectCurstExmndc.on 응답을 파싱한 중간 모델.
raw dict → OccupancyReportDTO → ORM 변환에 사용.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class OccupancyTenantDTO(BaseModel):
    """임차인 1명 파싱 결과"""

    property_index: int = 1
    tenant_name: str = ""  # mask_name() 적용 후
    party_type_code: str | None = None  # 관계인 코드
    party_type: str = "미상"  # "임차인" | "채무자" | "소유자" | "미상"
    occupied_part: str | None = None  # 점유부분
    usage_code: str | None = None  # 용도 코드
    usage: str = "미상"  # "주거" | "점포" | "사무실" | "미상"
    deposit: int | None = None  # parse_korean_money() 결과
    deposit_raw: str | None = None  # 원본 텍스트
    monthly_rent: int | None = None
    monthly_rent_raw: str | None = None
    move_in_date: date | None = None  # parse_korean_date() 결과
    move_in_date_raw: str | None = None
    fixed_date: date | None = None  # 확정일자
    fixed_date_raw: str | None = None
    is_unknown: bool = False  # 미상 임차인 여부
    raw_json: dict | None = None  # 원본 dict


class OccupancyPropertyDTO(BaseModel):
    """물건별 점유관계 파싱 결과"""

    property_index: int = 1
    address: str | None = None
    tenant_count: int = 0
    possession_code: str | None = None  # 점유관계 코드
    possession_desc: str | None = None  # HTML 제거 후 텍스트


class OccupancyReportDTO(BaseModel):
    """현황조사서 1건 파싱 결과 (임차인 + 점유관계 포함)"""

    case_number: str  # 포맷된 사건번호 (srnSaNo)
    court_code: str  # 법원코드
    investigation_date: str | None = None  # 원본 텍스트 그대로
    etc_note: str | None = None  # 기타사항 (HTML 제거 후)
    tenants: list[OccupancyTenantDTO] = Field(default_factory=list)
    properties: list[OccupancyPropertyDTO] = Field(default_factory=list)
    raw_json: dict = Field(default_factory=dict)  # 전체 API 응답 원본
