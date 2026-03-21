"""기일경과 물건 대법원 재조회 스크립트

auction_date < today AND status IN ('진행', '기일경과') 인 물건을
대법원에 개별 재조회해서 auction_date / status / bid_count / minimum_bid 갱신.

- 대법원 API에서 미래 기일을 반환하면 → auction_date 업데이트, status='진행' 복원
- 동일한 과거 기일이거나 API 실패 → 변경 없음 (매각완료/취하는 SaleResultCollector 담당)
- 점수 재산출은 하지 않음 (rescore는 --rescore-db 사용)

사용법:
    # 변경 내용 확인만 (DB 저장 없음)
    PYTHONPATH=backend python scripts/fix_past_due.py --dry-run --max 20 -v

    # 100건 테스트
    PYTHONPATH=backend python scripts/fix_past_due.py --max 100 -v

    # 전체 실행 (2,146건)
    PYTHONPATH=backend python scripts/fix_past_due.py

    # 특정 법원만
    PYTHONPATH=backend python scripts/fix_past_due.py --court B000210

서버 (venv 환경):
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/fix_past_due.py --max 100 -v
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal  # noqa: E402
from app.models.db.auction import Auction  # noqa: E402
from app.models.db.converters import auction_orm_to_detail  # noqa: E402
from app.services.crawler.court_auction import CourtAuctionClient  # noqa: E402

logger = logging.getLogger(__name__)

# 서울 5개 법원코드
SEOUL_COURTS = {
    "B000210": "서울중앙",
    "B000214": "서울동부",
    "B000212": "서울서부",
    "B000211": "서울남부",
    "B000213": "서울북부",
}


def setup_logging(verbose: bool = False) -> None:
    """로깅 설정"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def update_past_due(
    max_items: int = 0,
    court_code: str | None = None,
    delay: float = 1.0,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """기일경과 물건 재조회 및 업데이트

    Args:
        max_items: 최대 처리 건수 (0=전체)
        court_code: 특정 법원만 처리 (None=전체)
        delay: 물건 간 대기 시간(초) — 대법원 IP 차단 방지
        dry_run: True면 DB 저장 없이 확인만
        verbose: True면 변경 없음 케이스도 출력

    Returns:
        처리 결과 dict
    """
    db = SessionLocal()
    crawler = CourtAuctionClient()

    try:
        today = date.today()

        # 1. 기일경과 + 진행 중 과거기일 물건 조회
        query = (
            db.query(Auction)
            .filter(
                Auction.auction_date < today,
                Auction.auction_date.isnot(None),
                Auction.status.in_(["진행", "기일경과"]),
            )
            .order_by(Auction.auction_date.desc())
        )

        if court_code:
            query = query.filter(Auction.court_office_code == court_code)

        total = query.count()
        court_label = SEOUL_COURTS.get(court_code, court_code) if court_code else "전체"
        print(f"기일경과 재조회 대상: {total}건 ({court_label})")

        if max_items > 0:
            query = query.limit(max_items)

        auctions: list[Auction] = query.all()

        # 2. 대법원 세션 초기화 (목록 조회 없이 상세조회하면 세션 쿠키 없어 실패)
        print("대법원 세션 초기화 중...")
        crawler.warm_up_session()

        updated = 0
        skipped = 0
        errors = 0
        target_count = len(auctions)

        for i, auction in enumerate(auctions, 1):
            if i > 1:
                time.sleep(delay)

            try:
                # DB JSONB에서 internal_case_number 복원
                detail_dto = auction_orm_to_detail(auction)
                case_num = detail_dto.internal_case_number or auction.case_number

                # 대법원 상세 재조회
                fresh = crawler.fetch_case_detail(
                    case_number=case_num,
                    court_office_code=auction.court_office_code or "",
                    property_sequence="1",
                )

                changed: list[str] = []

                # auction_date 갱신 (핵심: 미래 기일로 변경됐는지 확인)
                if fresh.auction_date and fresh.auction_date != auction.auction_date:
                    changed.append(
                        f"auction_date: {auction.auction_date} → {fresh.auction_date}"
                    )
                    if not dry_run:
                        auction.auction_date = fresh.auction_date

                # status 복원: 새 기일이 미래이고 현재 기일경과이면 진행으로 되돌림
                new_date = fresh.auction_date or auction.auction_date
                if new_date and new_date >= today and auction.status == "기일경과":
                    changed.append("status: 기일경과 → 진행")
                    if not dry_run:
                        auction.status = "진행"

                # bid_count 갱신 (유찰 후 증가)
                if fresh.bid_count and fresh.bid_count != auction.bid_count:
                    changed.append(
                        f"bid_count: {auction.bid_count} → {fresh.bid_count}"
                    )
                    if not dry_run:
                        auction.bid_count = fresh.bid_count
                        auction.current_round = fresh.bid_count

                # minimum_bid 갱신 (유찰 후 감소)
                if fresh.minimum_bid and fresh.minimum_bid != auction.minimum_bid:
                    changed.append(
                        f"minimum_bid: {auction.minimum_bid:,} → {fresh.minimum_bid:,}"
                    )
                    if not dry_run:
                        auction.minimum_bid = fresh.minimum_bid

                if changed:
                    if not dry_run:
                        auction.updated_at = datetime.now(timezone.utc)
                        db.commit()
                    updated += 1
                    suffix = " (dry-run)" if dry_run else ""
                    print(
                        f"[{i}/{target_count}] {auction.case_number}: "
                        + ", ".join(changed)
                        + suffix
                    )
                else:
                    skipped += 1
                    if verbose:
                        print(
                            f"[{i}/{target_count}] {auction.case_number}: "
                            f"변경없음 (date={fresh.auction_date}, "
                            f"status={fresh.status}, "
                            f"bid={fresh.bid_count})"
                        )

            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                errors += 1
                logger.warning("재조회 실패 [%s]: %s", auction.case_number, e)
                if verbose:
                    print(f"[{i}/{target_count}] {auction.case_number}: 오류 — {e}")

        return {
            "total_target": total,
            "processed": target_count,
            "updated": updated,
            "skipped_no_change": skipped,
            "errors": errors,
            "dry_run": dry_run,
        }

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="기일경과 물건 대법원 재조회 및 auction_date/status 업데이트"
    )
    parser.add_argument("--max", type=int, default=0, help="최대 처리 건수 (0=전체)")
    parser.add_argument(
        "--court", type=str, default=None,
        help="특정 법원만 처리 (예: B000210 = 서울중앙)",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="물건 간 대기 시간(초, 기본 1.0) — 대법원 IP 차단 방지",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 확인만")
    parser.add_argument("-v", "--verbose", action="store_true", help="변경없음 케이스도 출력")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if args.dry_run:
        print("*** DRY-RUN 모드: DB 저장 없음 ***\n")

    result = update_past_due(
        max_items=args.max,
        court_code=args.court,
        delay=args.delay,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(f"\n{'='*50}")
    print("기일경과 재조회 완료")
    print(f"{'='*50}")
    print(f"  전체 대상   : {result['total_target']}건")
    print(f"  처리        : {result['processed']}건")
    print(f"  업데이트    : {result['updated']}건")
    print(f"  변경없음    : {result['skipped_no_change']}건")
    print(f"  오류        : {result['errors']}건")
    if args.dry_run:
        print("  *** DRY-RUN: 실제 저장 없음 ***")
    print()


if __name__ == "__main__":
    main()
