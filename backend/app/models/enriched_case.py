"""1단+2단 파이프라인 데이터 모델

크롤링 결과(AuctionCaseDetail)에 공공 API 데이터를 결합한 EnrichedCase 모델.
1단 필터 엔진 평가 결과(FilterResult)와 2단 등기부 분석 결과를 포함한다.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.auction import AuctionCaseDetail
from app.models.registry import RegistryAnalysisResult
from app.models.scores import (
    LegalScoreResult,
    LocationScoreResult,
    OccupancyScoreResult,
    PriceScoreResult,
    TotalScoreResult,
)


class FilterColor(str, Enum):
    """필터링 결과 색상 분류"""

    RED = "RED"  # 즉시 제외
    YELLOW = "YELLOW"  # 주의 필요
    GREEN = "GREEN"  # 통과


class RuleMatch(BaseModel):
    """매칭된 개별 룰 정보"""

    rule_id: str  # 룰 ID (예: "R001", "Y002")
    rule_name: str  # 룰 이름 (예: "개발제한구역")
    description: str = ""  # 상세 사유


class FilterResult(BaseModel):
    """필터 엔진 평가 결과"""

    color: FilterColor  # RED / YELLOW / GREEN
    passed: bool  # CostGate 통과 여부 (RED=False)
    matched_rules: list[RuleMatch] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=datetime.now)


class BuildingInfo(BaseModel):
    """건축물대장 정보 (data.go.kr)"""

    main_purpose: str = ""  # 주용도 ("업무시설", "공동주택" 등)
    structure: str = ""  # 구조 ("철근콘크리트구조")
    total_area: float | None = None  # 연면적 (㎡)
    exclusive_area_m2: float | None = None  # deprecated: platArea(대지면적) 기반, BUG-01 대상
    exclusive_area_m2_real: float | None = None  # BUG-01 수정: totArea(연면적) 기반 올바른 값
    building_type: str | None = None  # '일반'/'집합' (regstrGbCd 기반)
    ground_floors: int | None = None  # 지상 층수 (grndFlrCnt)
    underground_floors: int | None = None  # 지하 층수 (ugrndFlrCnt)
    units_count: int | None = None  # 세대/호수 (hhldCnt or hoCnt)
    build_year: int | None = None  # 건축년도 (사용승인일 기준)
    use_approve_date: str = ""  # 사용승인일
    violation: bool = False  # 위반건축물 여부
    raw_items: list[dict] = Field(default_factory=list)
    # 전유부 호실별 면적 (getBrExposPubuseAreaInfo, 없으면 빈 리스트)
    units: list[dict] = Field(default_factory=list)  # [{ho, floor, area_m2}]


class LandUseInfo(BaseModel):
    """용도지역 정보 (Vworld)"""

    zones: list[str] = Field(default_factory=list)  # 용도지역명 목록
    is_greenbelt: bool = False  # 개발제한구역 여부
    raw_items: list[dict] = Field(default_factory=list)


class LocationData(BaseModel):
    """입지 데이터 (카카오 카테고리 검색 결과 — raw)"""

    nearest_station_m: int | None = None     # 가장 가까운 지하철역 거리 (m), None=역 없음
    nearest_station_name: str | None = None  # 가장 가까운 지하철역 이름 (예: "강남역")
    nearest_station_line: str | None = None  # 호선 정보 (예: "수도권 2호선")
    station_count_1km: int = 0              # 1km 내 지하철역 수
    nearest_school_m: int | None = None     # 가장 가까운 학교 거리 (m), None=1500m 내 없음
    school_count_1km: int = 0              # 1km 내 학교 수
    amenity_count_500m: int = 0             # 500m 내 편의시설 합산 수 (마트+편의점+병원)
    categories_fetched: list[str] = Field(default_factory=list)  # 성공한 카테고리 코드 목록


class MarketPriceInfo(BaseModel):
    """시세 정보 (실거래가 API)"""

    avg_price_per_m2: float | None = None  # 평균 단가 (원/㎡)
    recent_trades: list[dict] = Field(default_factory=list)
    trade_count: int = 0
    reference_period: str = ""  # 조회 기간 (예: "202601")
    lawd_cd: str = ""  # 조회한 법정동코드


class RentAreaRange(BaseModel):
    """면적 구간별 월세 통계 (1개 구간)"""

    range: str           # "20~40㎡"
    min_m2: float        # 구간 하한 (이상)
    max_m2: float        # 구간 상한 (미만, 마지막 구간은 9999)
    avg_rent: float      # 평균 월세 (만원)
    avg_deposit: float   # 평균 보증금 (만원, 없으면 0)
    count: int           # 샘플 수


class RentPriceInfo(BaseModel):
    """월세 실거래가 정보 (국토부 API) — 면적 구간별 분류"""

    by_area_range: list[RentAreaRange] = Field(default_factory=list)  # 구간별 통계
    overall_avg_rent: float | None = None      # 전체 평균 월세 (만원, fallback)
    overall_avg_deposit: float | None = None   # 전체 평균 보증금 (만원, fallback)
    sample_count: int = 0                      # 전체 샘플 수
    source: str = ""                           # 데이터 출처 (연립다세대, 오피스텔 등)
    lawd_cd: str = ""                          # 조회한 법정동코드
    queried_months: list[str] = Field(default_factory=list)


class EnrichedCase(BaseModel):
    """공공 API 데이터가 결합된 경매 물건"""

    case: AuctionCaseDetail
    coordinates: dict | None = None  # {"x": "127.0365", "y": "37.4994"}
    building: BuildingInfo | None = None
    land_use: LandUseInfo | None = None
    market_price: MarketPriceInfo | None = None
    rent_price: RentPriceInfo | None = None
    filter_result: FilterResult | None = None

    # 2단 등기부 분석 결과 (Optional — 1단 통과 건만 채워짐)
    registry_analysis: RegistryAnalysisResult | None = None
    registry_unique_no: str | None = None             # CODEF 고유번호
    registry_match_confidence: float | None = None    # matcher 매칭 신뢰도
    registry_error: str | None = None                 # 2단 실패 사유

    # 입지 데이터 (Phase 6 — 카카오 카테고리 검색 결과 raw)
    location_data: LocationData | None = None

    # 법률 리스크 점수 (5C — 등기부 분석 완료 건만)
    legal_score: LegalScoreResult | None = None

    # 가격 매력도 점수 (5D — 1단 데이터만으로 산출)
    price_score: PriceScoreResult | None = None

    # 입지 점수 (Phase 6 — 1단 데이터만으로 산출)
    location_score: LocationScoreResult | None = None

    # 명도 점수 (Phase 7 — 현황조사서 임차인 기반)
    occupancy_score: OccupancyScoreResult | None = None

    # 통합 점수 (5E — 가용 pillar 가중 합산)
    total_score: TotalScoreResult | None = None


class PipelineResult(BaseModel):
    """파이프라인 실행 결과"""

    total_searched: int = 0
    total_enriched: int = 0
    total_filtered: int = 0
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    cases: list[EnrichedCase] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
