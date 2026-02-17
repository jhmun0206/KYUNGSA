"""낙찰결과 수집기 CLI (Phase 6.5)

status='매각'인 Auction의 Score에 실제 낙찰가/낙찰가율/예측오차를 채워넣는다.
수집 결과는 Phase 5F 백테스트/캘리브레이션에서 활용된다.

사용법:
    # 전체 법원
    PYTHONPATH=backend python scripts/collect_winning_bids.py

    # 특정 법원만
    PYTHONPATH=backend python scripts/collect_winning_bids.py --court B000210

    # DB 변경 없이 수집 가능 건수 확인
    PYTHONPATH=backend python scripts/collect_winning_bids.py --dry-run --limit 10

서버 (venv 환경):
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/collect_winning_bids.py --all-seoul
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal  # noqa: E402
from app.services.crawler.court_auction import CourtAuctionClient  # noqa: E402
from app.services.winning_bid_collector import WinningBidCollector  # noqa: E402

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


def run_collect(
    court_office_code: str | None,
    dry_run: bool,
    limit: int | None,
) -> None:
    """낙찰결과 수집 실행"""
    db = SessionLocal()
    try:
        crawler = CourtAuctionClient()
        collector = WinningBidCollector(db=db, crawler=crawler)
        result = collector.collect(
            court_office_code=court_office_code,
            dry_run=dry_run,
            limit=limit,
        )
        label = f"[{court_office_code or '전체'}]"
        print(
            f"{label} 완료: 조회={result.total_queried} "
            f"업데이트={result.updated} "
            f"스킵={result.skipped} "
            f"오류={result.errors}"
        )
        if dry_run:
            print("※ dry-run 모드: DB 변경 없음")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="낙찰결과 수집기 (Phase 6.5)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--court", help="법원코드 (예: B000210)")
    group.add_argument("--all-seoul", action="store_true", help="서울 5개 법원 전체 수집")
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 확인만")
    parser.add_argument("--limit", type=int, default=None, help="최대 처리 건수")
    parser.add_argument("--verbose", action="store_true", help="DEBUG 로그 출력")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.all_seoul:
        for code, name in SEOUL_COURTS.items():
            print(f"\n=== {name} ({code}) ===")
            run_collect(
                court_office_code=code,
                dry_run=args.dry_run,
                limit=args.limit,
            )
    else:
        run_collect(
            court_office_code=args.court,
            dry_run=args.dry_run,
            limit=args.limit,
        )


if __name__ == "__main__":
    main()
