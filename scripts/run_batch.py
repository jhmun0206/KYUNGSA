"""배치 수집기 CLI

대법원 경매정보를 수집하여 DB에 저장한다.

사용법:
    PYTHONPATH=backend python scripts/run_batch.py --court B000210
    PYTHONPATH=backend python scripts/run_batch.py --court B000210 --max 10 --force
    PYTHONPATH=backend python scripts/run_batch.py --all-seoul
    PYTHONPATH=backend python scripts/run_batch.py --court B000210 --dry-run

서버 (venv 환경):
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/run_batch.py --all-seoul
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
from app.services.batch_collector import BatchCollector, BatchResult  # noqa: E402

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
    # httpx 로그 억제
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def print_result(result: BatchResult) -> None:
    """결과 요약 출력"""
    elapsed = ""
    if result.finished_at and result.started_at:
        dt = (result.finished_at - result.started_at).total_seconds()
        elapsed = f" ({dt:.1f}초)"

    print(f"\n{'='*50}")
    print(f"배치 수집 완료: {result.court_code}{elapsed}")
    print(f"{'='*50}")
    print(f"  Run ID     : {result.run_id}")
    print(f"  검색 건수  : {result.total_searched}")
    print(f"  총 페이지  : {result.total_pages}")
    print(f"  처리       : {result.processed}")
    print(f"  스킵(기존) : {result.skipped}")
    print(f"  신규 저장  : {result.new_count}")
    print(f"  업데이트   : {result.updated_count}")
    print(f"  RED        : {result.red_count}")
    print(f"  YELLOW     : {result.yellow_count}")
    print(f"  GREEN      : {result.green_count}")
    if result.errors:
        print(f"  에러       : {len(result.errors)}")
        for err in result.errors[:5]:
            print(f"    - {err}")
        if len(result.errors) > 5:
            print(f"    ... 외 {len(result.errors) - 5}건")
    print()


def run_single_court(
    court_code: str,
    max_items: int,
    force: bool,
    delay: float,
    dry_run: bool,
) -> BatchResult:
    """단일 법원 수집"""
    court_name = SEOUL_COURTS.get(court_code, court_code)
    print(f"\n수집 시작: {court_name} ({court_code})")

    db = SessionLocal()
    try:
        collector = BatchCollector(db=db)
        result = collector.collect(
            court_code=court_code,
            max_items=max_items,
            force_update=force,
            enrich_delay=delay,
            dry_run=dry_run,
        )
        print_result(result)
        return result
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="KYUNGSA 배치 수집기")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--court", type=str, help="법원코드 (예: B000210)")
    group.add_argument(
        "--all-seoul", action="store_true", help="서울 5개 법원 순차 수집"
    )
    parser.add_argument("--max", type=int, default=0, help="최대 처리 건수 (0=전체)")
    parser.add_argument("--force", action="store_true", help="기존 데이터 덮어쓰기")
    parser.add_argument("--delay", type=float, default=2.0, help="물건 간 대기 시간(초)")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 수집만")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로깅")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if args.dry_run:
        print("*** DRY-RUN 모드: DB 저장 없이 수집만 수행 ***\n")

    if args.all_seoul:
        results: list[BatchResult] = []
        for code, name in SEOUL_COURTS.items():
            result = run_single_court(
                court_code=code,
                max_items=args.max,
                force=args.force,
                delay=args.delay,
                dry_run=args.dry_run,
            )
            results.append(result)

        # 전체 요약
        total_processed = sum(r.processed for r in results)
        total_errors = sum(len(r.errors) for r in results)
        print(f"\n{'='*50}")
        print(f"전체 서울 수집 완료: {total_processed}건 처리, {total_errors}건 에러")
        print(f"{'='*50}")
    else:
        run_single_court(
            court_code=args.court,
            max_items=args.max,
            force=args.force,
            delay=args.delay,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
