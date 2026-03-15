"""정규화 컬럼 데이터 마이그레이션 스크립트 (DB-REBUILD)

기존 JSONB 데이터에서 신규 정규화 컬럼으로 데이터를 채운다.
새 컬럼(Alembic 마이그레이션으로 추가)은 NULL로 시작하므로
이 스크립트를 한 번 실행해야 채워진다.

실행 방법:
    PYTHONPATH=backend python scripts/migrate_normalize_data.py
    PYTHONPATH=backend python scripts/migrate_normalize_data.py --dry-run
    PYTHONPATH=backend python scripts/migrate_normalize_data.py --step property_category

스텝:
    1. property_category  — property_type → normalize_property_type()
    2. lat_lng            — coordinates JSONB → lat/lng Float 컬럼
    3. building_cols      — building_info JSONB → building_type/build_year/exclusive_area_m2_real/floor_count/units_count_real
    4. auction_rounds     — detail JSONB auction_rounds → auction_rounds 테이블
    5. null_cleanup       — JSONB null 리터럴 → SQL NULL 정리 (BUG-04)
    6. current_round      — bid_count → current_round 컬럼 동기화
"""

from __future__ import annotations

import argparse
import logging
import sys
import os

# PYTHONPATH=backend 필요
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.db.auction import Auction
from app.models.db.auction_round import AuctionRound as AuctionRoundORM
from app.services.property_normalizer import normalize_property_type

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 200


def step_property_category(db: Session, dry_run: bool) -> int:
    """property_type → property_category 정규화 (NULL인 것만)"""
    q = db.query(Auction).filter(Auction.property_category.is_(None))
    total = q.count()
    logger.info("property_category: %d건 처리 예정", total)

    updated = 0
    offset = 0
    while True:
        batch = q.limit(BATCH_SIZE).offset(offset).all()
        if not batch:
            break
        for auction in batch:
            cat = normalize_property_type(auction.property_type)
            if not dry_run:
                auction.property_category = cat
            updated += 1
        if not dry_run:
            db.commit()
        offset += BATCH_SIZE
        logger.info("  property_category: %d / %d 완료", min(offset, total), total)

    logger.info("property_category 완료: %d건", updated)
    return updated


def step_lat_lng(db: Session, dry_run: bool) -> int:
    """coordinates JSONB → lat/lng Float 컬럼 (lat IS NULL인 것만)"""
    q = (
        db.query(Auction)
        .filter(Auction.lat.is_(None))
        .filter(Auction.coordinates.isnot(None))
    )
    total = q.count()
    logger.info("lat/lng: %d건 처리 예정", total)

    updated = 0
    offset = 0
    while True:
        batch = q.limit(BATCH_SIZE).offset(offset).all()
        if not batch:
            break
        for auction in batch:
            coords = auction.coordinates
            if not isinstance(coords, dict):
                continue
            try:
                lng_val = coords.get("x") or coords.get("lng")
                lat_val = coords.get("y") or coords.get("lat")
                if lng_val is not None and lat_val is not None:
                    if not dry_run:
                        auction.lng = float(lng_val)
                        auction.lat = float(lat_val)
                    updated += 1
            except (ValueError, TypeError):
                pass
        if not dry_run:
            db.commit()
        offset += BATCH_SIZE
        logger.info("  lat/lng: %d / %d 완료", min(offset, total), total)

    logger.info("lat/lng 완료: %d건", updated)
    return updated


def step_building_cols(db: Session, dry_run: bool) -> int:
    """building_info JSONB → 정규화 컬럼 (building_type IS NULL인 것만)"""
    q = (
        db.query(Auction)
        .filter(Auction.building_type.is_(None))
        .filter(Auction.building_info.isnot(None))
    )
    total = q.count()
    logger.info("building_cols: %d건 처리 예정", total)

    updated = 0
    offset = 0
    while True:
        batch = q.limit(BATCH_SIZE).offset(offset).all()
        if not batch:
            break
        for auction in batch:
            b = auction.building_info
            if not isinstance(b, dict):
                continue
            try:
                if not dry_run:
                    bt = b.get("building_type")
                    if bt is not None:
                        auction.building_type = bt
                    by = b.get("build_year")
                    if by is not None:
                        auction.build_year = int(by)
                    area = b.get("exclusive_area_m2_real") or b.get("exclusive_area_m2")
                    if area is not None:
                        auction.exclusive_area_m2_real = float(area)
                    floors = b.get("ground_floors")
                    if floors is not None:
                        auction.floor_count = int(floors)
                    units = b.get("units_count")
                    if units is not None:
                        auction.units_count_real = int(units)
                updated += 1
            except (ValueError, TypeError, KeyError):
                pass
        if not dry_run:
            db.commit()
        offset += BATCH_SIZE
        logger.info("  building_cols: %d / %d 완료", min(offset, total), total)

    logger.info("building_cols 완료: %d건", updated)
    return updated


def step_auction_rounds(db: Session, dry_run: bool) -> int:
    """detail JSONB auction_rounds → auction_rounds 테이블 (rounds 없는 것만)"""
    # auction_rounds가 아직 없는 Auction만 처리
    from sqlalchemy import not_, exists

    has_rounds = exists().where(AuctionRoundORM.auction_id == Auction.id)
    q = (
        db.query(Auction)
        .filter(not_(has_rounds))
        .filter(Auction.detail.isnot(None))
    )
    total = q.count()
    logger.info("auction_rounds: %d건 처리 예정", total)

    updated = 0
    offset = 0
    while True:
        batch = q.limit(BATCH_SIZE).offset(offset).all()
        if not batch:
            break
        for auction in batch:
            detail = auction.detail
            if not isinstance(detail, dict):
                continue
            rounds_data = detail.get("auction_rounds", [])
            if not rounds_data:
                continue
            try:
                if not dry_run:
                    for r in rounds_data:
                        round_date = r.get("round_date")
                        db.add(AuctionRoundORM(
                            auction_id=auction.id,
                            round_number=int(r.get("round_number", 1)),
                            round_date=round_date,
                            minimum_bid=r.get("minimum_bid") or None,
                            result=r.get("result") or None,
                        ))
                updated += 1
            except (ValueError, TypeError, KeyError) as e:
                logger.warning("auction_rounds 파싱 실패 [%s]: %s", auction.case_number, e)
        if not dry_run:
            db.commit()
        offset += BATCH_SIZE
        logger.info("  auction_rounds: %d / %d 완료", min(offset, total), total)

    logger.info("auction_rounds 완료: %d건", updated)
    return updated


def step_current_round(db: Session, dry_run: bool) -> int:
    """bid_count → current_round 컬럼 동기화"""
    q = db.query(Auction).filter(Auction.current_round != Auction.bid_count)
    total = q.count()
    logger.info("current_round: %d건 처리 예정", total)

    if not dry_run and total > 0:
        db.execute(
            text("UPDATE auctions SET current_round = bid_count WHERE current_round != bid_count")
        )
        db.commit()

    logger.info("current_round 완료: %d건", total)
    return total


def step_null_cleanup(db: Session, dry_run: bool) -> None:
    """JSONB null 리터럴 → SQL NULL 정리 (BUG-04)

    TypeDecorator 수정 이후 신규 저장은 SQL NULL로 올바르게 들어오지만,
    기존 데이터에는 JSON null 리터럴('null'::jsonb)이 남아있을 수 있다.
    """
    # rent_price_info는 Alembic 마이그레이션으로 jsonb로 변환됨 → jsonb_typeof 사용
    jsonb_cols = [
        "building_info",
        "land_use_info",
        "market_price_info",
        "coordinates",
        "detail",
        "location_data",
        "rent_price_info",
    ]
    json_cols: list[str] = []

    for col in jsonb_cols:
        sql = f"""
            UPDATE auctions
            SET {col} = NULL
            WHERE jsonb_typeof({col}) = 'null'
        """
        if dry_run:
            count_sql = f"SELECT COUNT(*) FROM auctions WHERE jsonb_typeof({col}) = 'null'"
            result = db.execute(text(count_sql)).scalar()
            logger.info("[dry-run] %s null 리터럴: %d건", col, result or 0)
        else:
            result = db.execute(text(sql))
            logger.info("  %s null 리터럴 → SQL NULL: %d건", col, result.rowcount)

    for col in json_cols:
        sql = f"""
            UPDATE auctions
            SET {col} = NULL
            WHERE json_typeof({col}) = 'null'
        """
        if dry_run:
            count_sql = f"SELECT COUNT(*) FROM auctions WHERE json_typeof({col}) = 'null'"
            result = db.execute(text(count_sql)).scalar()
            logger.info("[dry-run] %s null 리터럴: %d건", col, result or 0)
        else:
            result = db.execute(text(sql))
            logger.info("  %s null 리터럴 → SQL NULL: %d건", col, result.rowcount)

    if not dry_run:
        db.commit()
    logger.info("null_cleanup 완료")


ALL_STEPS = ["property_category", "lat_lng", "building_cols", "auction_rounds", "current_round", "null_cleanup"]


def main() -> None:
    parser = argparse.ArgumentParser(description="정규화 컬럼 데이터 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 건수만 출력")
    parser.add_argument(
        "--step",
        choices=ALL_STEPS,
        help="특정 스텝만 실행 (기본: 전체)",
    )
    args = parser.parse_args()

    steps = [args.step] if args.step else ALL_STEPS

    db: Session = SessionLocal()
    try:
        for step in steps:
            logger.info("=== 스텝: %s (dry_run=%s) ===", step, args.dry_run)
            if step == "property_category":
                step_property_category(db, args.dry_run)
            elif step == "lat_lng":
                step_lat_lng(db, args.dry_run)
            elif step == "building_cols":
                step_building_cols(db, args.dry_run)
            elif step == "auction_rounds":
                step_auction_rounds(db, args.dry_run)
            elif step == "current_round":
                step_current_round(db, args.dry_run)
            elif step == "null_cleanup":
                step_null_cleanup(db, args.dry_run)
    finally:
        db.close()

    logger.info("마이그레이션 완료")


if __name__ == "__main__":
    main()
