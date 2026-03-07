"""b_code 백필 스크립트

coordinates는 있지만 b_code가 없는 기존 auctions에 대해
카카오 Geocode API를 재호출하여 b_code/main_address_no/sub_address_no를 저장한다.

실행:
    PYTHONPATH=backend python scripts/backfill_bcode.py
    PYTHONPATH=backend python scripts/backfill_bcode.py --max 3 -v
    nohup bash -c 'PYTHONPATH=backend python scripts/backfill_bcode.py' > ~/backfill_bcode.log 2>&1 &
"""

import argparse
import logging
import sys
import time

from sqlalchemy import text

from app.database import SessionLocal
from app.models.db.auction import Auction
from app.services.crawler.geo_client import GeoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

RATE_LIMIT_SEC = 1.0  # 카카오 API: 초당 10건 한도, 안전하게 1초 대기


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="b_code 백필 스크립트")
    parser.add_argument("--max", type=int, default=0, help="처리할 최대 건수 (0=전체)")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose 로그")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    geo = GeoClient()
    db = SessionLocal()

    try:
        # b_code가 없는 auctions 조회 (coordinates IS NOT NULL)
        # PostgreSQL: coordinates->>'b_code' IS NULL
        # SQLite(테스트): JSON_EXTRACT(coordinates, '$.b_code') IS NULL
        rows = (
            db.query(Auction)
            .filter(Auction.coordinates.is_not(None))
            .filter(
                text("(coordinates->>'b_code') IS NULL")
            )
            .order_by(Auction.created_at.asc())
            .all()
        )

        total = len(rows)
        if args.max and total > args.max:
            rows = rows[: args.max]
            logger.info("처리 대상: %d건 (전체 %d건 중 --max %d건 제한)", len(rows), total, args.max)
        else:
            logger.info("처리 대상: %d건 (b_code 없는 전체)", total)

        if not rows:
            logger.info("처리할 데이터 없음. 종료.")
            return

        success = 0
        fail = 0

        for i, auction in enumerate(rows, 1):
            address = auction.address or ""
            if not address:
                logger.debug("[%d/%d] 주소 없음: %s", i, len(rows), auction.case_number)
                fail += 1
                continue

            try:
                result = geo.geocode(address)
            except Exception as e:
                logger.warning(
                    "[%d/%d] geocode 실패 [%s]: %s",
                    i, len(rows), auction.case_number, e
                )
                fail += 1
                time.sleep(RATE_LIMIT_SEC)
                continue

            if not result:
                logger.debug(
                    "[%d/%d] geocode 결과 없음 [%s]: %s",
                    i, len(rows), auction.case_number, address
                )
                fail += 1
                time.sleep(RATE_LIMIT_SEC)
                continue

            b_code = result.get("b_code", "")
            main_no = result.get("main_address_no", "")
            sub_no = result.get("sub_address_no", "")

            if not b_code:
                logger.debug(
                    "[%d/%d] b_code 없음 [%s]: %s",
                    i, len(rows), auction.case_number, address
                )
                fail += 1
                time.sleep(RATE_LIMIT_SEC)
                continue

            # 기존 coordinates에 b_code 필드만 merge (x, y 덮어쓰지 않음)
            existing = dict(auction.coordinates or {})
            existing["b_code"] = b_code
            existing["main_address_no"] = main_no
            existing["sub_address_no"] = sub_no
            auction.coordinates = existing

            if args.verbose:
                logger.debug(
                    "[%d/%d] 업데이트 [%s]: b_code=%s main=%s sub=%s",
                    i, len(rows), auction.case_number, b_code, main_no, sub_no
                )

            success += 1

            # 100건마다 커밋 + 진행 로그
            if i % 100 == 0:
                db.commit()
                logger.info(
                    "진행: %d/%d (성공: %d, 실패: %d)",
                    i, len(rows), success, fail
                )

            time.sleep(RATE_LIMIT_SEC)

        # 마지막 커밋
        db.commit()

        logger.info(
            "완료: 전체 %d건 처리 — 성공: %d, 실패: %d",
            len(rows), success, fail
        )

    except KeyboardInterrupt:
        logger.info("사용자 중단. 현재까지 커밋.")
        db.commit()
    except Exception as e:
        logger.exception("예외 발생: %s", e)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
