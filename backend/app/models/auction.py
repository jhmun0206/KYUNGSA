"""경매 물건 데이터 모델

크롤링 결과를 정규화하여 저장하는 Pydantic 모델.
DB 모델(SQLAlchemy)은 별도로 정의한다. 여기는 DTO/값 객체만.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class AuctionCaseListItem(BaseModel):
    """경매 물건 목록 항목 (검색 결과 1행)"""

    case_number: str  # 사건번호 (예: "2022타경112176")
    court: str  # 관할법원 (예: "서울중앙지방법원")
    property_type: str  # 물건 용도 (예: "건물", "아파트")
    address: str  # 소재지
    appraised_value: int  # 감정가 (원)
    minimum_bid: int  # 최저매각가격 (원)
    auction_date: date | None = None  # 매각기일
    status: str = ""  # 진행상태 (예: "진행", "유찰")
    bid_count: int = 1  # 유찰횟수 + 1
    court_office_code: str = ""  # 법원코드 (boCd, 예: "B000210")
    internal_case_number: str = ""  # 내부 사건번호 (saNo, 예: "20260130012345")
    property_sequence: str = ""  # 물건순서 (maemulSer, 예: "1")


class AuctionPropertyObject(BaseModel):
    """개별 매각 물건 (일괄매각 시 복수 존재)"""

    sequence: int  # 매각 객체 순번 (dspslObjctSeq)
    real_estate_type: str = ""  # 부동산 구분 ("전유", "토지" 등)
    building_info: str = ""  # 건물 구조/면적 ("철골철근콘크리트조 36.714㎡")
    building_detail: str = ""  # 건물 상세 ("지1층비109호")
    building_name: str = ""  # 건물명
    appraised_value: int = 0  # 개별 감정가
    address: str = ""  # 소재지 (userPrintSt)
    lot_number: str = ""  # 지번 (rprsLtnoAddr)
    area_m2: float | None = None  # 면적 (㎡, building_info에서 추출)
    x_coord: str | int = ""  # X 좌표 (API가 int로 주기도 함)
    y_coord: str | int = ""  # Y 좌표 (API가 int로 주기도 함)


class AppraisalNote(BaseModel):
    """감정평가 요점"""

    sequence: int  # 순번
    category_code: str = ""  # 항목코드 (00083001 등)
    content: str = ""  # 내용


class AuctionRound(BaseModel):
    """경매 회차 정보"""

    round_number: int  # 회차
    round_date: date | None = None  # 기일
    minimum_bid: int  # 최저매각가격
    result: str = ""  # 결과 (매각, 유찰, 진행예정 등) — 미래 기일은 None으로 올 수 있음
    result_code: str = ""  # 결과코드 원본 (001, 002, 003 등)
    winning_bid: int | None = None  # 낙찰가
    sale_time: str = ""  # 기일 시각 ("1000")
    sale_place: str = ""  # 기일 장소


class AuctionCaseDetail(AuctionCaseListItem):
    """경매 물건 상세 정보"""

    # 사건 기본정보 (csBaseInfo)
    internal_case_number: str = ""  # 내부 사건번호 (20220130112176)
    case_name: str = ""  # 사건명 ("부동산강제경매")
    case_receipt_date: date | None = None  # 접수일
    case_start_date: date | None = None  # 개시결정일
    claim_amount: int = 0  # 청구금액
    court_department: str = ""  # 담당 계 ("경매21계")
    court_phone: str = ""  # 전화번호

    # 매각 정보 (dspslGdsDxdyInfo)
    sale_decision_date: date | None = None  # 매각결정기일
    sale_place: str = ""  # 매각장소
    deposit_rate: int = 10  # 입찰보증금 비율 (%)
    failed_count: int = 0  # 유찰횟수
    specification_remarks: str = ""  # 물건명세서 비고 (리스크 판단용)
    top_priority_mortgage: str = ""  # 최선순위 근저당 설정 상세
    superficies_info: str = ""  # 지상권 존재 상세
    sale_remarks: str = ""  # 매각물건 비고

    # 배당요구종기 (dstrtDemnInfo)
    distribution_demand_deadline: date | None = None

    # 문건 존재 여부 (상세 응답에서 추론)
    has_specification: bool = False  # 매각물건명세서
    has_appraisal: bool = False  # 감정평가서
    specification_date: date | None = None  # 물건명세서 작성일

    # 하위 데이터
    property_objects: list[AuctionPropertyObject] = Field(default_factory=list)
    appraisal_notes: list[AppraisalNote] = Field(default_factory=list)
    auction_rounds: list[AuctionRound] = Field(default_factory=list)
    photo_urls: list[str] = Field(default_factory=list)

    # API 후속 호출용
    court_office_code: str = ""  # 법원코드 (예: "B000210")
    property_sequence: str = ""  # 물건순서

    # Level 1 호환 필드
    lot_number: str = ""  # 지번
    area_m2: float | None = None  # 면적 (m2)
    floor: str = ""  # 층수 정보
    land_use: str = ""  # 용도지역
    parties: list[dict] = Field(default_factory=list)  # 당사자 정보
    reference_prices: dict = Field(default_factory=dict)
    detail_url: str = ""


class AuctionCaseHistory(BaseModel):
    """경매 사건 내역 (회차별 진행 이력)"""

    case_number: str
    case_start_date: date | None = None  # 개시결정일
    distribution_demand_deadline: date | None = None  # 배당요구종기
    rounds: list[AuctionRound] = Field(default_factory=list)


class AuctionDocument(BaseModel):
    """경매 문건 정보"""

    doc_type: str  # 문건 유형 (매각물건명세서, 감정평가서 등)
    title: str  # 제목
    doc_date: date | None = None  # 등록일
    url: str = ""
    exists: bool = True  # 존재 여부


class AuctionDocuments(BaseModel):
    """경매 문건 목록"""

    case_number: str
    has_specification: bool = False  # 매각물건명세서
    has_appraisal: bool = False  # 감정평가서
    has_status_report: bool = False  # 현황조사서
    specification_date: date | None = None
    documents: list[AuctionDocument] = Field(default_factory=list)
