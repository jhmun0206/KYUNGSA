"""Pydantic DTO ↔ SQLAlchemy ORM 양방향 변환

기존 DTO를 절대 변경하지 않으며, ORM은 순수 영속 레이어로만 사용.
"""

from __future__ import annotations

# 기일 결과 코드 → 한글 변환 맵
ROUND_RESULT_MAP: dict[str, str | None] = {
    "매각": "매각",
    "유찰": "유찰",
    "변경": "변경",
    "취하": "취하",
    "취소": "취소",
    "진행예정": "진행예정",
    "진행중": "진행중",
    "010": "변경",
    "011": "변경",
    "008": "취하",
    "017": "취소",
    "": None,
}


def normalize_round_result(result: str | None) -> str | None:
    """기일 결과 코드를 한글로 변환 (이미 한글이면 그대로)"""
    if not result:
        return None
    stripped = result.strip()
    return ROUND_RESULT_MAP.get(stripped, stripped)

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.auction import AuctionCaseDetail
from app.models.db.auction import Auction
from app.models.db.auction_round import AuctionRound as AuctionRoundORM
from app.models.db.filter_result import FilterResultORM
from app.models.db.pipeline_run import PipelineRun
from app.models.db.registry import RegistryAnalysisORM, RegistryEventORM
from app.models.enriched_case import (
    BuildingInfo,
    EnrichedCase,
    FilterColor,
    FilterResult,
    LandUseInfo,
    MarketPriceInfo,
    PipelineResult,
    RentPriceInfo,
    RuleMatch,
)
from app.services.property_normalizer import normalize_property_type
from app.models.registry import (
    AnalyzedRight,
    Confidence,
    EventType,
    HardStopFlag,
    RegistryAnalysisResult,
    RegistryDocument,
    RegistryEvent,
    RightClassification,
    SectionType,
)


# ──────────────────────────────────────────
# Pydantic → ORM
# ──────────────────────────────────────────


def auction_detail_to_orm(
    detail: AuctionCaseDetail,
    *,
    coordinates: dict | None = None,
    building: BuildingInfo | None = None,
    land_use: LandUseInfo | None = None,
    market_price: MarketPriceInfo | None = None,
    rent_price: RentPriceInfo | None = None,
) -> Auction:
    """AuctionCaseDetail (+ enrichment) → Auction ORM"""
    orm = Auction(
        case_number=detail.case_number,
        court=detail.court,
        court_office_code=detail.court_office_code,
        address=detail.address,
        property_type=detail.property_type,
        property_category=normalize_property_type(detail.property_type),
        appraised_value=detail.appraised_value,
        minimum_bid=detail.minimum_bid,
        auction_date=detail.auction_date,
        status=detail.status,
        bid_count=detail.bid_count,
        current_round=detail.bid_count,
        coordinates=coordinates,
        building_info=building.model_dump() if building else None,
        land_use_info=land_use.model_dump() if land_use else None,
        market_price_info=market_price.model_dump() if market_price else None,
        rent_price_info=rent_price.model_dump() if rent_price else None,
        detail=detail.model_dump(mode="json"),
    )
    if coordinates is not None:
        _apply_lat_lng(orm, coordinates)
    if building is not None:
        _apply_building_normalized(orm, building)
    return orm


def filter_dto_to_orm(result: FilterResult, auction_id: str) -> FilterResultORM:
    """FilterResult DTO → FilterResultORM"""
    return FilterResultORM(
        auction_id=auction_id,
        color=result.color.value,
        passed=result.passed,
        matched_rules=[r.model_dump() for r in result.matched_rules],
        evaluated_at=result.evaluated_at,
    )


def registry_event_dto_to_orm(event: RegistryEvent, auction_id: str) -> RegistryEventORM:
    """RegistryEvent DTO → RegistryEventORM"""
    return RegistryEventORM(
        auction_id=auction_id,
        section=event.section.value,
        rank_no=event.rank_no,
        purpose=event.purpose,
        event_type=event.event_type.value,
        accepted_at=event.accepted_at,
        receipt_no=event.receipt_no,
        cause=event.cause,
        holder=event.holder,
        amount=event.amount,
        canceled=event.canceled,
        raw_text=event.raw_text,
    )


def registry_analysis_dto_to_orm(
    analysis: RegistryAnalysisResult,
    auction_id: str,
    *,
    unique_no: str | None = None,
    match_confidence: float | None = None,
    cancellation_base_event_id: str | None = None,
) -> RegistryAnalysisORM:
    """RegistryAnalysisResult DTO → RegistryAnalysisORM

    registry_events는 별도로 저장. cancellation_base_event_id는 이벤트 저장 후 매핑.
    """
    def _analyzed_right_dump(ar: AnalyzedRight) -> dict:
        return {
            "event": ar.event.model_dump(mode="json"),
            "classification": ar.classification.value,
            "reason": ar.reason,
        }

    return RegistryAnalysisORM(
        auction_id=auction_id,
        registry_unique_no=unique_no,
        registry_match_confidence=match_confidence,
        cancellation_base_event_id=cancellation_base_event_id,
        has_hard_stop=analysis.has_hard_stop,
        hard_stop_flags=[
            {"rule_id": f.rule_id, "name": f.name, "description": f.description,
             "event": f.event.model_dump(mode="json")}
            for f in analysis.hard_stop_flags
        ] if analysis.hard_stop_flags else None,
        confidence=analysis.confidence.value,
        summary=analysis.summary,
        extinguished_rights=[_analyzed_right_dump(r) for r in analysis.extinguished_rights] or None,
        surviving_rights=[_analyzed_right_dump(r) for r in analysis.surviving_rights] or None,
        uncertain_rights=[_analyzed_right_dump(r) for r in analysis.uncertain_rights] or None,
        warnings=analysis.warnings or None,
        analyzed_at=datetime.now(timezone.utc),
    )


# ──────────────────────────────────────────
# ORM → Pydantic
# ──────────────────────────────────────────


def auction_orm_to_detail(orm: Auction) -> AuctionCaseDetail:
    """Auction ORM → AuctionCaseDetail (detail JSONB 스냅샷 복원)

    detail JSONB가 AuctionCaseDetail.model_dump() 형식이 아닌 경우
    (raw API JSON 등) ValidationError가 발생할 수 있으므로 try-except로 보호.
    실패 시 정규화 컬럼에서 최소 복원한다.
    """
    if orm.detail:
        try:
            return AuctionCaseDetail.model_validate(orm.detail)
        except Exception:
            pass  # detail JSONB 형식 불일치 → 정규화 컬럼으로 복원
    # fallback: 정규화 컬럼에서 최소 복원
    return AuctionCaseDetail(
        case_number=orm.case_number,
        court=orm.court,
        address=orm.address,
        property_type=orm.property_type,
        appraised_value=orm.appraised_value or 0,
        minimum_bid=orm.minimum_bid or 0,
        auction_date=orm.auction_date,
        status=orm.status,
        bid_count=orm.bid_count,
        court_office_code=orm.court_office_code,
    )


def filter_orm_to_dto(orm: FilterResultORM) -> FilterResult:
    """FilterResultORM → FilterResult DTO"""
    return FilterResult(
        color=FilterColor(orm.color),
        passed=orm.passed,
        matched_rules=[RuleMatch.model_validate(r) for r in (orm.matched_rules or [])],
        evaluated_at=orm.evaluated_at or datetime.now(timezone.utc),
    )


def registry_event_orm_to_dto(orm: RegistryEventORM) -> RegistryEvent:
    """RegistryEventORM → RegistryEvent DTO"""
    return RegistryEvent(
        section=SectionType(orm.section),
        rank_no=orm.rank_no,
        purpose=orm.purpose,
        event_type=EventType(orm.event_type),
        accepted_at=orm.accepted_at,
        receipt_no=orm.receipt_no,
        cause=orm.cause,
        holder=orm.holder,
        amount=orm.amount,
        canceled=orm.canceled,
        raw_text=orm.raw_text,
    )


def _restore_analyzed_right(data: dict) -> AnalyzedRight:
    """JSONB에서 AnalyzedRight 복원"""
    return AnalyzedRight(
        event=RegistryEvent.model_validate(data["event"]),
        classification=RightClassification(data["classification"]),
        reason=data["reason"],
    )


def _restore_hard_stop_flag(data: dict) -> HardStopFlag:
    """JSONB에서 HardStopFlag 복원"""
    return HardStopFlag(
        rule_id=data["rule_id"],
        name=data["name"],
        description=data["description"],
        event=RegistryEvent.model_validate(data["event"]),
    )


def registry_analysis_orm_to_dto(
    orm: RegistryAnalysisORM,
    events: list[RegistryEventORM],
    document: RegistryDocument | None = None,
) -> RegistryAnalysisResult:
    """RegistryAnalysisORM + events → RegistryAnalysisResult DTO"""
    event_dtos = [registry_event_orm_to_dto(e) for e in events]
    gapgu = [e for e in event_dtos if e.section == SectionType.GAPGU]
    eulgu = [e for e in event_dtos if e.section == SectionType.EULGU]

    # 말소기준권리 복원
    cancellation_base = None
    if orm.cancellation_base_event_id:
        for evt_orm in events:
            if evt_orm.id == orm.cancellation_base_event_id:
                cancellation_base = registry_event_orm_to_dto(evt_orm)
                break

    doc = document or RegistryDocument(
        gapgu_events=gapgu,
        eulgu_events=eulgu,
        all_events=event_dtos,
        source="db",
    )

    return RegistryAnalysisResult(
        document=doc,
        cancellation_base_event=cancellation_base,
        extinguished_rights=[_restore_analyzed_right(r) for r in (orm.extinguished_rights or [])],
        surviving_rights=[_restore_analyzed_right(r) for r in (orm.surviving_rights or [])],
        uncertain_rights=[_restore_analyzed_right(r) for r in (orm.uncertain_rights or [])],
        hard_stop_flags=[_restore_hard_stop_flag(f) for f in (orm.hard_stop_flags or [])],
        has_hard_stop=orm.has_hard_stop,
        confidence=Confidence(orm.confidence),
        warnings=orm.warnings or [],
        summary=orm.summary,
    )


def auction_orm_to_enriched(orm: Auction) -> EnrichedCase:
    """Auction ORM (+ 관계) → EnrichedCase DTO (필터/등기 포함)"""
    detail = auction_orm_to_detail(orm)

    filter_result = None
    if orm.filter_result:
        filter_result = filter_orm_to_dto(orm.filter_result)

    registry_analysis = None
    registry_unique_no = None
    registry_match_confidence = None
    if orm.registry_analysis:
        ra = orm.registry_analysis
        registry_unique_no = ra.registry_unique_no
        registry_match_confidence = ra.registry_match_confidence
        registry_analysis = registry_analysis_orm_to_dto(ra, orm.registry_events)

    return EnrichedCase(
        case=detail,
        coordinates=orm.coordinates,
        building=BuildingInfo.model_validate(orm.building_info) if orm.building_info else None,
        land_use=LandUseInfo.model_validate(orm.land_use_info) if orm.land_use_info else None,
        market_price=MarketPriceInfo.model_validate(orm.market_price_info) if orm.market_price_info else None,
        filter_result=filter_result,
        registry_analysis=registry_analysis,
        registry_unique_no=registry_unique_no,
        registry_match_confidence=registry_match_confidence,
    )


# ──────────────────────────────────────────
# 정규화 컬럼 보조 함수
# ──────────────────────────────────────────


def _apply_lat_lng(auction: Auction, coordinates: dict) -> None:
    """coordinates dict → lat/lng 정규화 컬럼 추출
    coordinates = {"x": "127.0365", "y": "37.4994"}  (카카오 형식)
    """
    try:
        lng_val = coordinates.get("x") or coordinates.get("lng")
        lat_val = coordinates.get("y") or coordinates.get("lat")
        if lng_val is not None:
            auction.lng = float(lng_val)
        if lat_val is not None:
            auction.lat = float(lat_val)
    except (ValueError, TypeError):
        pass  # 좌표 파싱 실패 시 무시


def _apply_building_normalized(auction: Auction, building: BuildingInfo) -> None:
    """BuildingInfo → 정규화 컬럼 추출"""
    if building.building_type is not None:
        auction.building_type = building.building_type
    if building.build_year is not None:
        auction.build_year = building.build_year
    if building.exclusive_area_m2_real is not None:
        auction.exclusive_area_m2_real = building.exclusive_area_m2_real
    if building.ground_floors is not None:
        auction.floor_count = building.ground_floors
    if building.units_count is not None:
        auction.units_count_real = building.units_count


# ──────────────────────────────────────────
# 전체 저장 헬퍼
# ──────────────────────────────────────────


def _sync_auction_round_fields(db: Session, auction: Auction) -> None:
    """auction_rounds 테이블에서 current_round + auction_date 동기화.

    auction_rounds flush 직후, db.commit() 이전에 호출.
    """
    from sqlalchemy import func

    row = (
        db.query(
            func.max(AuctionRoundORM.round_number).label("max_round"),
            func.max(AuctionRoundORM.round_date).label("latest_date"),
        )
        .filter(AuctionRoundORM.auction_id == auction.id)
        .one()
    )
    if row.max_round is not None:
        auction.current_round = row.max_round
    if row.latest_date is not None:
        auction.auction_date = row.latest_date


def save_enriched_case(db: Session, enriched: EnrichedCase) -> Auction:
    """EnrichedCase → DB 전체 저장 (upsert 방식)

    기존 case_number가 있으면 업데이트, 없으면 생성.
    모든 하위 테이블(filter, events, analysis) 포함.
    """
    # 기존 조회
    existing = db.query(Auction).filter(Auction.case_number == enriched.case.case_number).first()

    if existing:
        auction = existing
        # 정규화 컬럼 업데이트
        auction.court = enriched.case.court
        auction.court_office_code = enriched.case.court_office_code
        auction.address = enriched.case.address
        auction.property_type = enriched.case.property_type
        auction.appraised_value = enriched.case.appraised_value
        auction.minimum_bid = enriched.case.minimum_bid
        auction.auction_date = enriched.case.auction_date
        auction.status = enriched.case.status
        auction.bid_count = enriched.case.bid_count
        auction.current_round = enriched.case.bid_count
        if enriched.coordinates is not None:
            auction.coordinates = enriched.coordinates
            _apply_lat_lng(auction, enriched.coordinates)
        # enrichment 데이터: 새 값이 있으면 업데이트, None이면 기존 값 유지
        if enriched.building is not None:
            auction.building_info = enriched.building.model_dump()
            _apply_building_normalized(auction, enriched.building)
        if enriched.land_use is not None:
            auction.land_use_info = enriched.land_use.model_dump()
        if enriched.market_price is not None:
            auction.market_price_info = enriched.market_price.model_dump()
        if enriched.rent_price is not None:
            auction.rent_price_info = enriched.rent_price.model_dump()
        if enriched.location_data is not None:
            auction.location_data = enriched.location_data.model_dump()
            if enriched.location_data.nearest_station_m is not None:
                auction.station_distance_m = enriched.location_data.nearest_station_m
        # property_category 항상 갱신 (property_type 변경 가능)
        auction.property_category = normalize_property_type(enriched.case.property_type)
        auction.detail = enriched.case.model_dump(mode="json")
        # 하위 삭제 후 재생성 (FK 순서: analysis → events → filter)
        if auction.registry_analysis:
            db.delete(auction.registry_analysis)
            db.flush()
        for evt in list(auction.registry_events):
            db.delete(evt)
        if auction.filter_result:
            db.delete(auction.filter_result)
        db.flush()
    else:
        auction = auction_detail_to_orm(
            enriched.case,
            coordinates=enriched.coordinates,
            building=enriched.building,
            land_use=enriched.land_use,
            market_price=enriched.market_price,
            rent_price=enriched.rent_price,
        )
        if enriched.location_data is not None:
            auction.location_data = enriched.location_data.model_dump()
            if enriched.location_data.nearest_station_m is not None:
                auction.station_distance_m = enriched.location_data.nearest_station_m
        db.add(auction)
        db.flush()  # id 확보

    # 필터 결과
    if enriched.filter_result:
        fr = filter_dto_to_orm(enriched.filter_result, auction.id)
        db.add(fr)

    # 등기 이벤트 + 분석
    if enriched.registry_analysis:
        ra = enriched.registry_analysis
        # 이벤트 저장
        event_id_map: dict[tuple, str] = {}
        for evt in ra.document.all_events:
            evt_orm = registry_event_dto_to_orm(evt, auction.id)
            db.add(evt_orm)
            db.flush()
            key = (evt.section.value, evt.rank_no, evt.purpose, evt.accepted_at)
            event_id_map[key] = evt_orm.id

        # 말소기준권리 이벤트 ID 매핑
        cancel_base_id = None
        if ra.cancellation_base_event:
            cb = ra.cancellation_base_event
            key = (cb.section.value, cb.rank_no, cb.purpose, cb.accepted_at)
            cancel_base_id = event_id_map.get(key)

        ra_orm = registry_analysis_dto_to_orm(
            ra,
            auction.id,
            unique_no=enriched.registry_unique_no,
            match_confidence=enriched.registry_match_confidence,
            cancellation_base_event_id=cancel_base_id,
        )
        db.add(ra_orm)

    # 기일 이력 저장 (auction_rounds) — 기존 삭제 후 재생성
    if enriched.case.auction_rounds:
        for rnd_orm in list(auction.auction_rounds):
            db.delete(rnd_orm)
        db.flush()
        for rnd in enriched.case.auction_rounds:
            db.add(AuctionRoundORM(
                auction_id=auction.id,
                round_number=rnd.round_number,
                round_date=rnd.round_date,
                minimum_bid=rnd.minimum_bid,
                result=normalize_round_result(rnd.result),
            ))
        db.flush()
        _sync_auction_round_fields(db, auction)

    db.commit()
    db.refresh(auction)
    return auction


def save_pipeline_result(db: Session, result: PipelineResult, run_id: str, court_code: str) -> PipelineRun:
    """PipelineResult → DB 저장 (pipeline_runs + 개별 cases)"""
    now = datetime.now(timezone.utc)

    run = PipelineRun(
        run_id=run_id,
        court_code=court_code,
        started_at=now,
        finished_at=now,
        total_searched=result.total_searched,
        total_enriched=result.total_enriched,
        total_filtered=result.total_filtered,
        red_count=result.red_count,
        yellow_count=result.yellow_count,
        green_count=result.green_count,
        errors=result.errors or None,
        status="COMPLETED",
    )
    db.add(run)

    for enriched in result.cases:
        save_enriched_case(db, enriched)

    db.commit()
    db.refresh(run)
    return run
