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
from app.services.notifier import send_telegram, format_batch_summary  # noqa: E402

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


def notify_result(result: BatchResult, *, court_label: str) -> None:
    """텔레그램 알림 전송 (신규 A/B등급 있을 때만)"""
    if result.new_grade_a > 0 or result.new_grade_b > 0:
        msg = format_batch_summary(
            court_code=result.court_code,
            court_label=court_label,
            total_searched=result.total_searched,
            new_count=result.new_count,
            new_a=result.new_grade_a,
            new_b=result.new_grade_b,
            errors=len(result.errors),
        )
        send_telegram(msg)


def run_rescore_db(
    court_code: str | None,
    coverage_below: float,
    max_items: int,
    delay: float,
    dry_run: bool,
    skip_occupancy: bool = False,
    score_exists: bool = False,
) -> BatchResult:
    """DB 기반 재채점"""
    label = SEOUL_COURTS.get(court_code, court_code) if court_code else "전체"
    scope = "Score 보유 물건만" if score_exists else "Score 없는 건 포함"
    print(f"\nDB 재채점 시작: {label} (coverage < {coverage_below:.0%}, {scope})")

    db = SessionLocal()
    try:
        collector = BatchCollector(db=db)
        result = collector.rescore_db(
            court_code=court_code,
            coverage_below=coverage_below,
            max_items=max_items,
            enrich_delay=delay,
            dry_run=dry_run,
            skip_occupancy=skip_occupancy,
            score_exists=score_exists,
        )
        print_result(result)
        return result
    finally:
        db.close()


def run_single_court(
    court_code: str,
    max_items: int,
    force: bool,
    delay: float,
    dry_run: bool,
    skip_occupancy: bool = False,
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
            skip_occupancy=skip_occupancy,
        )
        print_result(result)
        return result
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="KYUNGSA 배치 수집기")

    # --court / --all-seoul 은 서로 배타적
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--court", type=str, help="법원코드 (예: B000210)")
    group.add_argument(
        "--all-seoul", action="store_true", help="서울 5개 법원 순차 수집"
    )

    # --rescore-db 는 독립 플래그 (--court 와 조합 가능)
    parser.add_argument(
        "--rescore-db", action="store_true",
        help="DB 기반 재채점 모드 (대법원 API 검색 없이 DB에서 직접 물건 재채점)",
    )
    parser.add_argument(
        "--coverage-below", type=float, default=0.30,
        help="--rescore-db 시 이 미만 coverage 물건만 재채점 (기본값 0.30)",
    )
    parser.add_argument(
        "--score-exists", action="store_true",
        help="--rescore-db 시 Score가 이미 있는 물건만 처리 (Score 없는 건 제외)",
    )

    parser.add_argument("--max", type=int, default=0, help="최대 처리 건수 (0=전체)")
    parser.add_argument("--force", action="store_true", help="기존 데이터 덮어쓰기")
    parser.add_argument("--delay", type=float, default=2.0, help="물건 간 대기 시간(초)")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 수집만")
    parser.add_argument(
        "--skip-occupancy", action="store_true",
        help="현황조사서 조회 스킵 (550 에러 회피용)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로깅")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    # 모드 검증
    if not (args.court or args.all_seoul or args.rescore_db):
        parser.error("--court, --all-seoul, 또는 --rescore-db 중 하나를 지정하세요")
    if args.all_seoul and args.rescore_db:
        parser.error("--all-seoul 과 --rescore-db 는 함께 사용할 수 없습니다")

    if args.dry_run:
        print("*** DRY-RUN 모드: DB 저장 없이 수집만 수행 ***\n")

    if args.rescore_db:
        run_rescore_db(
            court_code=args.court,  # None 이면 전체 법원
            coverage_below=args.coverage_below,
            max_items=args.max,
            delay=args.delay,
            dry_run=args.dry_run,
            skip_occupancy=args.skip_occupancy,
            score_exists=args.score_exists,
        )
        return

    if args.all_seoul:
        results: list[BatchResult] = []
        for code, name in SEOUL_COURTS.items():
            result = run_single_court(
                court_code=code,
                max_items=args.max,
                force=args.force,
                delay=args.delay,
                dry_run=args.dry_run,
                skip_occupancy=args.skip_occupancy,
            )
            results.append(result)

        # 전체 요약
        total_processed = sum(r.processed for r in results)
        total_errors = sum(len(r.errors) for r in results)
        print(f"\n{'='*50}")
        print(f"전체 서울 수집 완료: {total_processed}건 처리, {total_errors}건 에러")
        print(f"{'='*50}")

        # 텔레그램 알림 (전체 합산)
        if not args.dry_run:
            total_a = sum(r.new_grade_a for r in results)
            total_b = sum(r.new_grade_b for r in results)
            total_new = sum(r.new_count for r in results)
            total_searched = sum(r.total_searched for r in results)
            if total_a > 0 or total_b > 0:
                msg = format_batch_summary(
                    court_code="서울전체",
                    court_label="서울 5개 법원",
                    total_searched=total_searched,
                    new_count=total_new,
                    new_a=total_a,
                    new_b=total_b,
                    errors=total_errors,
                )
                send_telegram(msg)
    else:
        result = run_single_court(
            court_code=args.court,
            max_items=args.max,
            force=args.force,
            delay=args.delay,
            dry_run=args.dry_run,
            skip_occupancy=args.skip_occupancy,
        )
        # 텔레그램 알림 (단일 법원)
        if not args.dry_run:
            court_label = SEOUL_COURTS.get(args.court, args.court)
            notify_result(result, court_label=court_label)


if __name__ == "__main__":
    main()
