"""매각결과 대량 수집기 CLI (Phase 6.5b)

대법원 PGJ158 매각결과검색 API를 통해 낙찰 완료 건을 법원별로 대량 수집.
기존 물건은 winning_bid 업데이트, 신규 물건은 기본 정보 INSERT.

사용법:
    # 서울 5개 법원 전체 (기본값)
    PYTHONPATH=backend python scripts/collect_sale_results.py

    # 특정 법원만
    PYTHONPATH=backend python scripts/collect_sale_results.py --court B000210

    # 날짜 범위 필터 (클라이언트 측)
    PYTHONPATH=backend python scripts/collect_sale_results.py --from 2026-01-01 --to 2026-02-17

    # DB 변경 없이 확인
    PYTHONPATH=backend python scripts/collect_sale_results.py --dry-run --limit 50

    # 서버 (venv 환경)
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/collect_sale_results.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal  # noqa: E402
from app.services.crawler.court_auction import CourtAuctionClient  # noqa: E402
from app.services.sale_result_collector import (  # noqa: E402
    SEOUL_COURT_CODES,
    SaleResultCollector,
)

SEOUL_COURTS = {
    "B000210": "서울중앙",
    "B000211": "서울남부",
    "B000212": "서울서부",
    "B000213": "서울북부",
    "B000214": "서울동부",
}


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def parse_date_arg(value: str) -> date:
    """YYYY-MM-DD 문자열 → date"""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"날짜 형식 오류 (YYYY-MM-DD 필요): {value}")


def run(
    court_codes: list[str],
    date_from: date | None,
    date_to: date | None,
    dry_run: bool,
    limit: int | None,
    page_delay: float,
) -> None:
    """수집 실행"""
    db = SessionLocal()
    try:
        crawler = CourtAuctionClient()
        collector = SaleResultCollector(db=db, crawler=crawler, page_delay=page_delay)
        result = collector.collect(
            court_codes=court_codes,
            date_from=date_from,
            date_to=date_to,
            dry_run=dry_run,
            limit=limit,
        )
        print(
            f"\n=== 수집 완료 ===\n"
            f"  법원 조회: {result.courts_queried}개\n"
            f"  총 수신 건수: {result.total_items}건\n"
            f"  업데이트: {result.updated}건\n"
            f"  신규 삽입: {result.new_inserted}건\n"
            f"  스킵(낙찰가 없음): {result.skipped_no_amount}건\n"
            f"  스킵(날짜 범위 밖): {result.skipped_date_filter}건\n"
            f"  스킵(이미 존재): {result.already_exists}건\n"
            f"  오류: {result.errors}건"
        )
        if dry_run:
            print("※ dry-run 모드: DB 변경 없음")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="매각결과 대량 수집기 (Phase 6.5b)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/collect_sale_results.py                          # 서울 5개 법원 (기본)
  python scripts/collect_sale_results.py --all-courts            # 전국 전체 (~12,000건)
  python scripts/collect_sale_results.py --court B000210
  python scripts/collect_sale_results.py --from 2026-01-01 --to 2026-02-17
  python scripts/collect_sale_results.py --dry-run --limit 50
""",
    )

    court_group = parser.add_mutually_exclusive_group()
    court_group.add_argument("--court", metavar="CODE", help="법원코드 (예: B000210)")
    court_group.add_argument(
        "--courts",
        metavar="CODE",
        nargs="+",
        help="법원코드 목록 (공백 구분, 예: B000210 B000214)",
    )
    court_group.add_argument(
        "--all-courts",
        action="store_true",
        help="전국 모든 법원 수집 (court_code='' 단일 전국 조회, ~12,000건)",
    )

    parser.add_argument(
        "--from",
        dest="date_from",
        type=parse_date_arg,
        default=None,
        metavar="YYYY-MM-DD",
        help="수집 시작일 (maeGiil 기준, 클라이언트 필터)",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=parse_date_arg,
        default=None,
        metavar="YYYY-MM-DD",
        help="수집 종료일 (maeGiil 기준, 클라이언트 필터)",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 건수 확인")
    parser.add_argument("--limit", type=int, default=None, help="최대 처리 건수")
    parser.add_argument(
        "--delay",
        type=float,
        default=2.5,
        help="페이지 요청 간격(초, 기본 2.5초 — WAF 대응)",
    )
    parser.add_argument("--verbose", action="store_true", help="DEBUG 로그 출력")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # 법원 코드 결정
    if args.court:
        court_codes = [args.court]
        label_str = f"{SEOUL_COURTS.get(args.court, args.court)}({args.court})"
    elif args.courts:
        court_codes = args.courts
        labels = [f"{SEOUL_COURTS.get(c, c)}({c})" for c in court_codes]
        label_str = ", ".join(labels)
    elif args.all_courts:
        court_codes = [""]  # 빈 문자열 → 전국 조회
        label_str = "전국 전체 (court_code='')"
    else:
        court_codes = SEOUL_COURT_CODES
        labels = [f"{SEOUL_COURTS.get(c, c)}({c})" for c in court_codes]
        label_str = ", ".join(labels)

    print(f"대상: {label_str}")
    if args.date_from or args.date_to:
        print(f"날짜 필터: {args.date_from or '제한없음'} ~ {args.date_to or '제한없음'}")
    if args.dry_run:
        print("※ dry-run 모드로 실행합니다.")

    run(
        court_codes=court_codes,
        date_from=args.date_from,
        date_to=args.date_to,
        dry_run=args.dry_run,
        limit=args.limit,
        page_delay=args.delay,
    )


if __name__ == "__main__":
    main()
