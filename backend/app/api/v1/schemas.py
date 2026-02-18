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

    # 추가 데이터
    specification_remarks: str        # gdsSpcfcRmk
    market_price_info: dict[str, Any] | None
    location_data: dict[str, Any] | None


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
