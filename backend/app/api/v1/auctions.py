"""Phase 8 대시보드용 경매 API v1

DB(auctions + scores)에서 조회한 데이터를 반환한다.
기존 /api/* 엔드포인트(크롤러 직접 실행)와 완전히 분리된 DB 읽기 전용 라우터.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case as sa_case, func
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.v1.schemas import (
    AuctionDetailResponse,
    AuctionListItem,
    AuctionListResponse,
    MapItem,
    MapResponse,
    RoundItem,
    ScoreDetail,
)
from app.models.db.auction import Auction
from app.models.db.score import Score

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1-auctions"])

# ── 내부 헬퍼 ────────────────────────────────────────────────────


def _parse_coords(coords: dict | None) -> tuple[float | None, float | None]:
    """coordinates JSONB → (lat, lng) float 변환.

    카카오 좌표계: x=경도(lng), y=위도(lat), 모두 문자열.
    """
    if not coords:
        return None, None
    try:
        lat = float(coords["y"])
        lng = float(coords["x"])
        return lat, lng
    except (KeyError, ValueError, TypeError):
        return None, None


def _grade_order():
    """등급 정렬 (A→B→C→D→없음 순)"""
    return sa_case(
        (Score.grade == "A", 1),
        (Score.grade == "B", 2),
        (Score.grade == "C", 3),
        (Score.grade == "D", 4),
        else_=5,
    )


def _parse_rounds(detail: dict | None) -> list[RoundItem]:
    """detail JSONB의 auction_rounds 배열 → RoundItem 목록"""
    if not detail:
        return []
    rounds_raw = detail.get("auction_rounds", [])
    result = []
    for r in rounds_raw:
        if not isinstance(r, dict):
            continue
        # round_date: "2025-12-10" 형식
        round_date = None
        if rd := r.get("round_date"):
            try:
                from datetime import date
                round_date = date.fromisoformat(str(rd))
            except (ValueError, TypeError):
                pass
        result.append(
            RoundItem(
                round_number=int(r.get("round_number", 0)),
                round_date=round_date,
                minimum_bid=int(r.get("minimum_bid", 0)),
                result=str(r.get("result", "")),
            )
        )
    return result


def _build_score_detail(score: Score | None) -> ScoreDetail | None:
    """Score ORM → ScoreDetail 스키마"""
    if score is None:
        return None
    return ScoreDetail(
        total_score=score.total_score,
        grade=score.grade,
        score_coverage=score.score_coverage,
        grade_provisional=score.grade_provisional,
        property_category=score.property_category,
        legal_score=score.legal_score,
        price_score=score.price_score,
        location_score=score.location_score,
        occupancy_score=score.occupancy_score,
        predicted_winning_ratio=score.predicted_winning_ratio,
        prediction_method=score.prediction_method,
        sub_scores=score.sub_scores,
        missing_pillars=list(score.missing_pillars or []),
        warnings=list(score.warnings or []),
        needs_expert_review=score.needs_expert_review,
    )


def _auction_to_list_item(auction: Auction, score: Score | None) -> AuctionListItem:
    """Auction + Score → AuctionListItem"""
    lat, lng = _parse_coords(auction.coordinates)
    return AuctionListItem(
        case_number=auction.case_number,
        address=auction.address,
        property_type=auction.property_type,
        court=auction.court,
        court_office_code=auction.court_office_code,
        appraised_value=auction.appraised_value,
        minimum_bid=auction.minimum_bid,
        auction_date=auction.auction_date,
        bid_count=auction.bid_count,
        status=auction.status,
        grade=score.grade if score else None,
        total_score=score.total_score if score else None,
        score_coverage=score.score_coverage if score else None,
        grade_provisional=score.grade_provisional if score else False,
        predicted_winning_ratio=score.predicted_winning_ratio if score else None,
        lat=lat,
        lng=lng,
    )


# ── 엔드포인트 ────────────────────────────────────────────────────


@router.get("/auctions/map", response_model=MapResponse)
def get_map_items(
    court_office_code: str | None = Query(None, description="법원 코드 필터"),
    grade: str | None = Query(None, description="등급 필터 (콤마 구분: A,B,C)"),
    property_type: str | None = Query(None, description="물건 유형"),
    db: Session = Depends(get_db),
) -> MapResponse:
    """지도용 좌표 목록 (좌표 있는 물건만)

    /auctions/{case_number} 보다 먼저 등록해야 한다.
    """
    query = (
        db.query(Auction, Score)
        .outerjoin(Score, Auction.id == Score.auction_id)
        .filter(Auction.status.notin_(["취하", "변경"]))
        .filter(Auction.coordinates.is_not(None))
    )

    if court_office_code:
        query = query.filter(Auction.court_office_code == court_office_code)

    if grade:
        grades = [g.strip().upper() for g in grade.split(",") if g.strip()]
        if grades:
            query = query.filter(Score.grade.in_(grades))

    if property_type:
        query = query.filter(Auction.property_type.contains(property_type))

    rows = query.limit(2000).all()  # 지도용 최대 2000건

    items: list[MapItem] = []
    for auction, score in rows:
        lat, lng = _parse_coords(auction.coordinates)
        if lat is None or lng is None:
            continue
        items.append(
            MapItem(
                case_number=auction.case_number,
                lat=lat,
                lng=lng,
                grade=score.grade if score else None,
                address=auction.address,
                appraised_value=auction.appraised_value,
                auction_date=auction.auction_date,
                property_type=auction.property_type,
            )
        )

    return MapResponse(items=items)


@router.get("/auctions", response_model=AuctionListResponse)
def get_auctions(
    court_office_code: str | None = Query(None, description="법원 코드"),
    grade: str | None = Query(None, description="등급 필터 (콤마 구분: A,B,C)"),
    property_type: str | None = Query(None, description="물건 유형"),
    sort: str = Query("grade", description="정렬 기준: grade|appraised_value|auction_date|predicted_winning_ratio"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AuctionListResponse:
    """물건 목록 조회 (DB 기반, 필터/정렬/페이지네이션)"""
    query = (
        db.query(Auction, Score)
        .outerjoin(Score, Auction.id == Score.auction_id)
        .filter(Auction.status.notin_(["취하", "변경"]))
    )

    # 필터
    if court_office_code:
        query = query.filter(Auction.court_office_code == court_office_code)

    if grade:
        grades = [g.strip().upper() for g in grade.split(",") if g.strip()]
        if grades:
            query = query.filter(Score.grade.in_(grades))

    if property_type:
        query = query.filter(Auction.property_type.contains(property_type))

    # 전체 건수 (페이지네이션 전)
    total = query.count()

    # 정렬
    if sort == "appraised_value":
        query = query.order_by(Auction.appraised_value.desc().nullslast())
    elif sort == "auction_date":
        query = query.order_by(Auction.auction_date.asc().nullslast())
    elif sort == "predicted_winning_ratio":
        query = query.order_by(Score.predicted_winning_ratio.asc().nullslast())
    else:
        # 기본: 등급순 (A→B→C→D→없음)
        query = query.order_by(_grade_order(), Score.total_score.desc().nullslast())

    # 페이지네이션
    rows = query.offset((page - 1) * size).limit(size).all()

    items = [_auction_to_list_item(a, s) for a, s in rows]
    return AuctionListResponse(total=total, page=page, size=size, items=items)


@router.get("/auctions/{case_number}", response_model=AuctionDetailResponse)
def get_auction_detail(
    case_number: str,
    db: Session = Depends(get_db),
) -> AuctionDetailResponse:
    """물건 상세 조회"""
    row = (
        db.query(Auction, Score)
        .outerjoin(Score, Auction.id == Score.auction_id)
        .filter(Auction.case_number == case_number)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"물건을 찾을 수 없습니다: {case_number}")

    auction, score = row
    lat, lng = _parse_coords(auction.coordinates)

    # detail JSONB에서 specification_remarks 추출
    spec_remarks = ""
    location_data_raw: dict[str, Any] | None = None
    if auction.detail and isinstance(auction.detail, dict):
        spec_remarks = auction.detail.get("specification_remarks", "") or ""
        location_data_raw = auction.detail.get("location_data")

    return AuctionDetailResponse(
        case_number=auction.case_number,
        address=auction.address,
        property_type=auction.property_type,
        court=auction.court,
        court_office_code=auction.court_office_code,
        appraised_value=auction.appraised_value,
        minimum_bid=auction.minimum_bid,
        auction_date=auction.auction_date,
        bid_count=auction.bid_count,
        status=auction.status,
        winning_bid=auction.winning_bid,
        winning_ratio=auction.winning_ratio,
        winning_date=auction.winning_date,
        lat=lat,
        lng=lng,
        score=_build_score_detail(score),
        rounds=_parse_rounds(auction.detail),
        specification_remarks=spec_remarks,
        market_price_info=auction.market_price_info,
        location_data=location_data_raw,
    )
