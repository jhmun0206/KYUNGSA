"""Phase 8 대시보드용 경매 API v1

DB(auctions + scores)에서 조회한 데이터를 반환한다.
기존 /api/* 엔드포인트(크롤러 직접 실행)와 완전히 분리된 DB 읽기 전용 라우터.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Float, case as sa_case, func, or_, and_
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import settings
from app.api.v1.schemas import (
    AuctionDetailResponse,
    AuctionListItem,
    AuctionListResponse,
    MapItem,
    MapResponse,
    MLPrediction,
    MLPredictionFactor,
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


def _build_ml_prediction(auction: Auction, db: Session) -> MLPrediction | None:
    """Auction → ML 예측 결과 (감정가 없으면 None)"""
    if not auction.appraised_value or auction.appraised_value <= 0:
        return None
    if not auction.minimum_bid or auction.minimum_bid <= 0:
        return None

    try:
        from app.services.prediction.predictor import WinningBidPredictor
        from app.services.prediction.rolling_helper import get_rolling_stats

        # fail_count 추출
        fail_count = max(auction.bid_count - 1, 0)
        if auction.detail and isinstance(auction.detail, dict):
            yuchal = auction.detail.get("yuchalCnt")
            if yuchal is not None:
                try:
                    fail_count = int(yuchal)
                except (ValueError, TypeError):
                    pass

        # rolling 통계 DB 조회
        stats = get_rolling_stats(
            db,
            property_type=auction.property_type,
            address=auction.address,
        )

        predictor = WinningBidPredictor.get_instance()
        result = predictor.predict(
            appraised_value=auction.appraised_value,
            minimum_bid=auction.minimum_bid,
            fail_count=fail_count,
            property_type=auction.property_type,
            court_office_code=auction.court_office_code,
            address=auction.address,
            rolling_avg=stats.avg,
            rolling_count=stats.count,
            tenant_count=auction.occupancy_tenant_count or 0,
            total_deposit=0,  # 개별 보증금 합계는 별도 쿼리 필요 → 0 기본값
        )

        return MLPrediction(
            predicted_ratio=result.predicted_ratio,
            predicted_price=result.predicted_price,
            confidence=result.confidence,
            model_version=result.model_version,
            top_factors=[
                MLPredictionFactor(**f) for f in result.top_factors
            ],
            fallback_reason=result.fallback_reason,
        )
    except Exception:
        logger.exception("ML 예측 실패: %s", auction.case_number)
        return None


def _category_conditions(cat: str) -> list:
    """카테고리명 → SQLAlchemy 조건 목록 (OR 대상)

    프론트에서 정규화된 카테고리명("상가/근린", "다세대/빌라" 등)을 받아
    DB raw property_type 에 대한 ilike 조건으로 변환한다.
    """
    if cat == "아파트":
        return [
            and_(
                Auction.property_type.ilike("%아파트%"),
                ~Auction.property_type.ilike("%오피스텔%"),
            )
        ]
    elif cat == "오피스텔":
        return [Auction.property_type.ilike("%오피스텔%")]
    elif cat in ("다세대/빌라", "다세대빌라"):
        return [
            or_(
                Auction.property_type.ilike("%다세대%"),
                Auction.property_type.ilike("%연립%"),
                Auction.property_type.ilike("%빌라%"),
            )
        ]
    elif cat in ("단독/다가구", "단독다가구"):
        return [
            or_(
                Auction.property_type.ilike("%단독%"),
                Auction.property_type.ilike("%다가구%"),
            )
        ]
    elif cat in ("상가/근린", "상가/근생", "상가근린", "상가근생"):
        # "상가", "근린시설", "근린생활시설", "제1종근린생활시설" 등 포함
        return [
            or_(
                Auction.property_type.ilike("%상가%"),
                Auction.property_type.ilike("%근린%"),
            )
        ]
    elif cat == "토지":
        return [
            or_(
                Auction.property_type.ilike("%전답%"),
                Auction.property_type.ilike("%임야%"),
                Auction.property_type.ilike("%대지%"),
                Auction.property_type.ilike("%토지%"),
            )
        ]
    else:
        # 알 수 없는 카테고리: contains fallback
        return [Auction.property_type.ilike(f"%{cat}%")]


def _apply_property_type_filter(query, property_type_param: str):
    """물건 유형 필터 적용 (콤마 구분 다중 카테고리 지원)

    예) "상가/근린,오피스텔" → 두 카테고리를 OR 조건으로 적용
    """
    categories = [c.strip() for c in property_type_param.split(",") if c.strip()]
    if not categories:
        return query

    all_conditions = []
    for cat in categories:
        all_conditions.extend(_category_conditions(cat))

    if len(all_conditions) == 1:
        return query.filter(all_conditions[0])
    return query.filter(or_(*all_conditions))


def _apply_default_type_exclusions(query):
    """유형 필터 없을 때 비부동산(자동차, 중기, 기타, 빈 값) 기본 제외"""
    return query.filter(
        Auction.property_type.isnot(None),
        Auction.property_type != "",
        Auction.property_type != "기타",
        ~Auction.property_type.ilike("%자동차%"),
        ~Auction.property_type.ilike("%중기%"),
    )


def _auction_to_list_item(auction: Auction, score: Score | None) -> AuctionListItem:
    """Auction + Score → AuctionListItem"""
    # 정규화 lat/lng 우선, 없으면 JSONB coordinates fallback
    lat = auction.lat
    lng = auction.lng
    if lat is None or lng is None:
        lat, lng = _parse_coords(auction.coordinates)
    today = date_type.today()
    is_past_due = bool(
        auction.auction_date is not None
        and auction.auction_date < today
        and auction.status in ("진행", "예정")
    )
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
        is_past_due=is_past_due,
        grade=score.grade if score else None,
        total_score=score.total_score if score else None,
        score_coverage=score.score_coverage if score else None,
        grade_provisional=score.grade_provisional if score else False,
        predicted_winning_ratio=score.predicted_winning_ratio if score else None,
        price_score=score.price_score if score else None,
        location_score=score.location_score if score else None,
        occupancy_score=score.occupancy_score if score else None,
        lat=lat,
        lng=lng,
        # 정규화 컬럼
        property_category=auction.property_category,
        building_type=auction.building_type,
        station_distance_m=auction.station_distance_m,
        build_year=auction.build_year,
        exclusive_area_m2_real=auction.exclusive_area_m2_real,
        current_round=auction.current_round,
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
    property_type: str | None = Query(None, description="물건 유형 카테고리 (상가/근린, 오피스텔, 아파트, 다세대/빌라, 단독/다가구, 토지; 콤마 구분 다중 선택)"),
    district: str | None = Query(None, description="행정구 필터 (콤마 구분 다중 선택, 예: 강남구,서초구)"),
    region: str | None = Query(None, description="시/도 필터 (콤마 구분 다중 선택, 예: 서울,경기)"),
    q: str | None = Query(None, description="주소 키워드 검색"),
    sort: str = Query("grade", description="정렬 기준: grade|appraised_value|auction_date|minimum_bid|bid_count|predicted_winning_ratio"),
    status: str | None = Query(None, description="상태 필터: 없으면 진행+예정만, '전체' 또는 'all' 이면 전체, '매각' 이면 매각만"),
    min_price: int | None = Query(None, ge=0, description="감정가 하한 (원)"),
    max_price: int | None = Query(None, ge=0, description="감정가 상한 (원)"),
    bid_count_min: int | None = Query(None, ge=1, description="최소 유찰횟수 (1=1회 이상, 2=2회 이상 …)"),
    building_type: str | None = Query(None, description="건물 형태: '일반' | '집합'"),
    build_year_min: int | None = Query(None, ge=1900, description="사용승인연도 이상 (예: 2015)"),
    station_radius_m: int | None = Query(None, ge=1, description="역까지 거리 이내(m) (예: 500, 1000)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AuctionListResponse:
    """물건 목록 조회 (DB 기반, 필터/정렬/페이지네이션)"""
    query = (
        db.query(Auction, Score)
        .outerjoin(Score, Auction.id == Score.auction_id)
    )

    # 상태 필터: 기본값은 매각/취하/기각/변경 제외 (진행+예정만)
    if status is None:
        query = query.filter(Auction.status.notin_(["매각", "취하", "기각", "변경"]))
    elif status not in ("전체", "all"):
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            query = query.filter(Auction.status.in_(statuses))

    # 필터
    if court_office_code:
        query = query.filter(Auction.court_office_code == court_office_code)

    if grade:
        grades = [g.strip().upper() for g in grade.split(",") if g.strip()]
        if grades:
            query = query.filter(Score.grade.in_(grades))

    # 물건 유형: 정규화 카테고리명 → ilike 매핑, 없으면 기타 제외
    if property_type:
        query = _apply_property_type_filter(query, property_type)
    else:
        query = _apply_default_type_exclusions(query)

    # 시/도 필터 (콤마 구분 OR 조건, 물건 주소 기준)
    if region:
        regions = [r.strip() for r in region.split(",") if r.strip()]
        if regions:
            region_conds = [Auction.address.ilike(f"%{r}%") for r in regions]
            query = query.filter(or_(*region_conds))

    # 행정구 필터 (콤마 구분 OR 조건, 물건 주소 기준)
    if district:
        districts = [d.strip() for d in district.split(",") if d.strip()]
        if districts:
            district_conds = [Auction.address.ilike(f"%{d}%") for d in districts]
            query = query.filter(or_(*district_conds))

    if q:
        query = query.filter(Auction.address.ilike(f"%{q}%"))

    # 감정가 범위 필터
    if min_price is not None:
        query = query.filter(Auction.appraised_value >= min_price)
    if max_price is not None:
        query = query.filter(Auction.appraised_value <= max_price)

    # 유찰횟수 필터: bid_count_min=N → 유찰 N회 이상 → DB bid_count >= N+1
    if bid_count_min is not None:
        query = query.filter(Auction.bid_count >= bid_count_min + 1)

    # 건물 형태 필터
    if building_type:
        query = query.filter(Auction.building_type == building_type)

    # 사용승인연도 필터
    if build_year_min is not None:
        query = query.filter(
            Auction.build_year.isnot(None),
            Auction.build_year >= build_year_min,
        )

    # 역까지 거리 필터
    if station_radius_m is not None:
        query = query.filter(
            Auction.station_distance_m.isnot(None),
            Auction.station_distance_m <= station_radius_m,
        )

    # 전체 건수 (페이지네이션 전)
    total = query.count()

    # 정렬
    if sort == "appraised_value":
        query = query.order_by(Auction.appraised_value.desc().nullslast())
    elif sort == "auction_date":
        query = query.order_by(Auction.auction_date.asc().nullslast())
    elif sort == "minimum_bid":
        query = query.order_by(Auction.minimum_bid.asc().nullslast())
    elif sort == "bid_count":
        query = query.order_by(Auction.bid_count.desc().nullslast())
    elif sort == "discount_rate":
        # (감정가 - 최저가) / 감정가 DESC — 할인율 높은 순
        query = query.order_by(
            (
                (Auction.appraised_value - Auction.minimum_bid).cast(Float)
                / func.nullif(Auction.appraised_value.cast(Float), 0)
            )
            .desc()
            .nullslast()
        )
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

    # ML 낙찰가율 예측
    ml_prediction = _build_ml_prediction(auction, db)

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
        ml_prediction=ml_prediction,
        rounds=_parse_rounds(auction.detail),
        specification_remarks=spec_remarks,
        building_info=auction.building_info,
        market_price_info=auction.market_price_info,
        rent_price_info=auction.rent_price_info,
        location_data=location_data_raw,
        default_loan_rate=settings.DEFAULT_LOAN_RATE,
    )
