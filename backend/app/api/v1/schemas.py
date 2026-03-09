"""Phase 8 대시보드용 응답 스키마 (v1)

DB에서 조회한 데이터를 프론트엔드에 전달하는 Pydantic 스키마.
auctions + scores 테이블 조인 결과를 직렬화한다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel


class AuctionListItem(BaseModel):
    """물건 목록 카드 (1건)"""

    case_number: str
    address: str
    property_type: str
    court: str
    court_office_code: str
    appraised_value: int | None
    minimum_bid: int | None
    auction_date: date | None
    bid_count: int           # 유찰횟수 + 1
    status: str

    # 점수 (Score 없으면 None)
    grade: str | None
    total_score: float | None
    score_coverage: float | None
    grade_provisional: bool
    predicted_winning_ratio: float | None

    # pillar 점수 (리스트 카드에서 리스크 요약 표시용)
    price_score: float | None
    location_score: float | None
    occupancy_score: float | None

    # 기일 지남 여부 (auction_date < today AND status IN 진행/예정 → 결과 대기중)
    is_past_due: bool = False

    # 좌표 (coordinates JSONB → float 변환)
    lat: float | None
    lng: float | None


class AuctionListResponse(BaseModel):
    """물건 목록 응답"""

    total: int
    page: int
    size: int
    items: list[AuctionListItem]


class ScoreDetail(BaseModel):
    """점수 상세 (상세 페이지용)"""

    total_score: float | None
    grade: str | None
    score_coverage: float | None
    grade_provisional: bool
    property_category: str | None

    # pillar 점수
    legal_score: float | None
    price_score: float | None
    location_score: float | None
    occupancy_score: float | None

    # 예측
    predicted_winning_ratio: float | None
    prediction_method: str | None

    # 세부
    sub_scores: dict[str, Any] | None
    missing_pillars: list[str]
    warnings: list[str]
    needs_expert_review: bool


class RoundItem(BaseModel):
    """기일 내역 1건"""

    round_number: int
    round_date: date | None
    minimum_bid: int
    result: str


class AuctionDetailResponse(BaseModel):
    """물건 상세 응답"""

    # 기본 정보
    case_number: str
    address: str
    property_type: str
    court: str
    court_office_code: str
    appraised_value: int | None
    minimum_bid: int | None
    auction_date: date | None
    bid_count: int
    status: str

    # 낙찰 결과 (있으면)
    winning_bid: int | None
    winning_ratio: float | None
    winning_date: date | None

    # 좌표
    lat: float | None
    lng: float | None

    # 점수
    score: ScoreDetail | None

    # 기일 내역 (detail JSONB 파싱)
    rounds: list[RoundItem]

    # ML 예측 (모델 있으면 ml_v1, 없으면 rule_v1 fallback)
    ml_prediction: MLPrediction | None

    # 추가 데이터
    specification_remarks: str        # gdsSpcfcRmk
    building_info: dict[str, Any] | None
    market_price_info: dict[str, Any] | None
    rent_price_info: dict[str, Any] | None
    location_data: dict[str, Any] | None

    # 투자 분석 시뮬레이터 기본값 (서버 설정값 전달)
    default_loan_rate: float = 0.045


class MLPredictionFactor(BaseModel):
    """ML 예측 영향 요인 1건"""

    feature: str            # "할인율 64%", "유찰 2회" 등 (사람 읽기용)
    importance: float       # 중요도 (%)


class MLPrediction(BaseModel):
    """ML 낙찰가율 예측 결과 (Private → 상세 페이지용)"""

    predicted_ratio: float          # 예측 낙찰가율 (0~1.5)
    predicted_price: int            # 예측 낙찰가 (원)
    confidence: str                 # "high" | "medium" | "low"
    model_version: str              # "ml_v1" | "rule_v1"
    top_factors: list[MLPredictionFactor]  # 상위 영향 피처 (최대 3개)
    fallback_reason: str | None     # fallback 사유 (ML 사용 시 None)


class MapItem(BaseModel):
    """지도용 마커 1건"""

    case_number: str
    lat: float
    lng: float
    grade: str | None
    address: str
    appraised_value: int | None
    auction_date: date | None
    property_type: str


class MapResponse(BaseModel):
    """지도 응답"""

    items: list[MapItem]
