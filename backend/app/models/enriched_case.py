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
from app.models.scores import LegalScoreResult, PriceScoreResult, TotalScoreResult


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
    use_approve_date: str = ""  # 사용승인일
    violation: bool = False  # 위반건축물 여부
    raw_items: list[dict] = Field(default_factory=list)


class LandUseInfo(BaseModel):
    """용도지역 정보 (Vworld)"""

    zones: list[str] = Field(default_factory=list)  # 용도지역명 목록
    is_greenbelt: bool = False  # 개발제한구역 여부
    raw_items: list[dict] = Field(default_factory=list)


class MarketPriceInfo(BaseModel):
    """시세 정보 (실거래가 API)"""

    avg_price_per_m2: float | None = None  # 평균 단가 (원/㎡)
    recent_trades: list[dict] = Field(default_factory=list)
    trade_count: int = 0
    reference_period: str = ""  # 조회 기간 (예: "202601")
    lawd_cd: str = ""  # 조회한 법정동코드


class EnrichedCase(BaseModel):
    """공공 API 데이터가 결합된 경매 물건"""

    case: AuctionCaseDetail
    coordinates: dict | None = None  # {"x": "127.0365", "y": "37.4994"}
    building: BuildingInfo | None = None
    land_use: LandUseInfo | None = None
    market_price: MarketPriceInfo | None = None
    filter_result: FilterResult | None = None

    # 2단 등기부 분석 결과 (Optional — 1단 통과 건만 채워짐)
    registry_analysis: RegistryAnalysisResult | None = None
    registry_unique_no: str | None = None             # CODEF 고유번호
    registry_match_confidence: float | None = None    # matcher 매칭 신뢰도
    registry_error: str | None = None                 # 2단 실패 사유

    # 법률 리스크 점수 (5C — 등기부 분석 완료 건만)
    legal_score: LegalScoreResult | None = None

    # 가격 매력도 점수 (5D — 1단 데이터만으로 산출)
    price_score: PriceScoreResult | None = None

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
