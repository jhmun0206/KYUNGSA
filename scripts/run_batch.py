"""배치 수집기 CLI

대법원 경매정보를 수집하여 DB에 저장한다.

사용법:
    PYTHONPATH=backend python scripts/run_batch.py --court B000210
    PYTHONPATH=backend python scripts/run_batch.py --court B000210 --max 10 --force
    PYTHONPATH=backend python scripts/run_batch.py --all-seoul
    PYTHONPATH=backend python scripts/run_batch.py --all-gyeonggi
    PYTHONPATH=backend python scripts/run_batch.py --all-courts
    PYTHONPATH=backend python scripts/run_batch.py --court B000210 --dry-run

서버 (venv 환경):
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/run_batch.py --all-seoul
    PYTHONPATH=backend .venv/bin/python scripts/run_batch.py --all-gyeonggi
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal  # noqa: E402
from app.services.batch_collector import BatchCollector, BatchResult  # noqa: E402
from app.services.notifier import send_telegram, format_batch_summary  # noqa: E402

# 서울 6개 법원코드 (DB 실측 기준, 2026-03-27 검증)
SEOUL_COURTS = {
    "B000210": "서울중앙",
    "B000211": "서울동부",
    "B000212": "서울남부",
    "B000213": "서울북부",
    "B000215": "서울서부",
    "B000214": "의정부",   # 의정부지방법원 — 수도권 수집 편의상 서울 그룹 유지
}

# 경기/인천 법원코드 (DB 실측 기준, 2026-03-27 검증)
# 주의: 의정부(B000214)는 SEOUL_COURTS에 포함됨 — 중복 수집 방지
GYEONGGI_COURTS = {
    "B000250": "수원",
    "B000251": "성남",
    "B000240": "인천",
    "B000241": "부천",
    "B214807": "고양",
    "B000253": "평택",
    "B000254": "안양",
    "B214804": "남양주",
    "B250826": "안산",
}

# 수도권 전체 (서울 + 경기/인천)
# 처리 순서 의도:
#   1) B000240(인천): stuck 패턴 해소 — SIGTERM 도착 전 우선 완료
#   2) 서울 + 나머지 경기/인천
#   3) B000250(수원): 가장 큰 법원 (~1100건) — 마지막에 배치
ALL_COURTS = {
    "B000240": "인천",
    "B000210": "서울중앙",
    "B000211": "서울동부",
    "B000212": "서울남부",
    "B000213": "서울북부",
    "B000215": "서울서부",
    "B000214": "의정부",
    "B000251": "성남",
    "B000241": "부천",
    "B214807": "고양",
    "B000253": "평택",
    "B000254": "안양",
    "B214804": "남양주",
    "B250826": "안산",
    "B000250": "수원",
}


class GracefulTermination(Exception):
    """SIGTERM 수신 시 발생 — collect()의 except Exception에 잡혀
    PipelineRun.finished_at이 기록된 뒤 루프에서 중단 처리된다.
    (기존에는 SIGTERM 즉사로 finished_at=NULL stuck run이 매일 쌓였음)"""


_terminating = False


def _sigterm_handler(signum, frame):  # noqa: ANN001
    global _terminating
    _terminating = True
    raise GracefulTermination(f"signal {signum} 수신 — 우아 종료")


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
    active_only: bool = True,
    status_filter: str | None = None,
    missing_location_only: bool = False,
    missing_building_info_only: bool = False,
) -> BatchResult:
    """DB 기반 재채점"""
    label = ALL_COURTS.get(court_code, court_code) if court_code else "전체"
    scope = "Score 보유 물건만" if score_exists else "Score 없는 건 포함"
    active_label = "진행중만" if active_only else "매각 포함 전체"
    status_label = f", status={status_filter}" if status_filter else ""
    loc_label = ", location_data IS NULL + lat 있는 건만" if missing_location_only else ""
    bld_label = ", building_info IS NULL 진행 물건만" if missing_building_info_only else ""
    print(f"\nDB 재채점 시작: {label} (coverage < {coverage_below:.0%}, {scope}, {active_label}{status_label}{loc_label}{bld_label})")

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
            active_only=active_only,
            status_filter=status_filter,
            missing_location_only=missing_location_only,
            missing_building_info_only=missing_building_info_only,
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
    court_name = ALL_COURTS.get(court_code, court_code)
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

    # --court / --all-seoul / --all-gyeonggi / --all-courts 는 서로 배타적
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--court", type=str, help="법원코드 (예: B000210)")
    group.add_argument("--all-seoul", action="store_true", help="서울 5개 법원 순차 수집")
    group.add_argument("--all-gyeonggi", action="store_true", help="경기/인천 7개 법원 순차 수집")
    group.add_argument("--all-courts", action="store_true", help="수도권 전체 법원 순차 수집 (서울+경기/인천)")

    # --rescore-db 는 독립 플래그 (--court 와 조합 가능)
    parser.add_argument(
        "--rescore-db", action="store_true",
        help="DB 기반 재채점 모드 (대법원 API 검색 없이 DB에서 직접 물건 재채점)",
    )
    # --update-station-names 는 독립 플래그 (--court 와 조합 가능)
    parser.add_argument(
        "--update-station-names", action="store_true",
        help="기존 DB 물건에 역 이름/호선 정보 보완 (station_distance_m 있고 name 없는 건)",
    )
    parser.add_argument(
        "--station-delay", type=float, default=0.3,
        help="--update-station-names 물건 간 대기 시간(초, 기본 0.3)",
    )
    # --fix-duplicate-units 는 독립 플래그 (--court 와 조합 가능)
    parser.add_argument(
        "--fix-duplicate-units", action="store_true",
        help="building_info.units 중복 제거 (floor=0 전유부 행, ho 기준 dedup)",
    )
    parser.add_argument(
        "--coverage-below", type=float, default=0.30,
        help="--rescore-db 시 이 미만 coverage 물건만 재채점 (기본값 0.30)",
    )
    parser.add_argument(
        "--score-exists", action="store_true",
        help="--rescore-db 시 Score가 이미 있는 물건만 처리 (Score 없는 건 제외)",
    )
    parser.add_argument(
        "--active-only", action="store_true", default=True,
        help="--rescore-db 시 매각/취하/기각/변경 완료 물건 제외 (기본값 True)",
    )
    parser.add_argument(
        "--include-sold", action="store_true",
        help="--rescore-db 시 매각 완료 물건도 포함 (--active-only 비활성화)",
    )
    parser.add_argument(
        "--status", type=str, default=None,
        help="--rescore-db 시 특정 status 물건만 처리 (예: 진행)",
    )
    parser.add_argument(
        "--missing-location", action="store_true",
        help="--rescore-db 시 location_data IS NULL AND lat IS NOT NULL 인 물건만 처리",
    )
    parser.add_argument(
        "--missing-building-info", action="store_true",
        help="building_info IS NULL 인 '진행' 물건만 재채점 (--rescore-db 자동 활성화)",
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
    signal.signal(signal.SIGTERM, _sigterm_handler)

    # 모드 검증
    update_station = getattr(args, "update_station_names", False)
    fix_dup_units = getattr(args, "fix_duplicate_units", False)
    missing_building = getattr(args, "missing_building_info", False)
    # --missing-building-info 는 --rescore-db 자동 활성화
    if missing_building:
        args.rescore_db = True
    all_group = args.all_seoul or args.all_gyeonggi or args.all_courts
    if not (args.court or all_group or args.rescore_db or update_station or fix_dup_units):
        parser.error("--court, --all-seoul, --all-gyeonggi, --all-courts, --rescore-db, --update-station-names, 또는 --fix-duplicate-units 중 하나를 지정하세요")
    if all_group and args.rescore_db:
        parser.error("--all-seoul/--all-gyeonggi/--all-courts 와 --rescore-db 는 함께 사용할 수 없습니다")

    if args.dry_run:
        print("*** DRY-RUN 모드: DB 저장 없이 수집만 수행 ***\n")

    if fix_dup_units:
        court_label = ALL_COURTS.get(args.court, args.court) if args.court else "전체"
        print(f"\nbuilding_info.units 중복 제거 시작 ({court_label})")
        db = SessionLocal()
        try:
            collector = BatchCollector(db=db)
            result = collector.fix_duplicate_units(
                court_code=args.court,
                max_items=args.max,
                dry_run=args.dry_run,
            )
            print(f"\nunits 중복 제거 완료: {result}")
        finally:
            db.close()
        return

    if update_station:
        court_label = ALL_COURTS.get(args.court, args.court) if args.court else "전체"
        print(f"\n역 이름/호선 보완 시작 ({court_label})")
        db = SessionLocal()
        try:
            collector = BatchCollector(db=db)
            result = collector.update_station_names(
                max_items=args.max,
                delay=args.station_delay,
                dry_run=args.dry_run,
                court_code=args.court,
            )
            print(f"\n역 이름/호선 보완 완료: {result}")
        finally:
            db.close()
        return

    if args.rescore_db:
        # --force → coverage_below=1.01 (coverage는 0~1이므로 전체 대상)
        effective_coverage = 1.01 if args.force else args.coverage_below
        run_rescore_db(
            court_code=args.court,  # None 이면 전체 법원
            coverage_below=effective_coverage,
            max_items=args.max,
            delay=args.delay,
            dry_run=args.dry_run,
            skip_occupancy=args.skip_occupancy,
            score_exists=args.score_exists,
            active_only=not args.include_sold,
            status_filter=args.status,
            missing_location_only=args.missing_location,
            missing_building_info_only=missing_building,
        )
        return

    if args.all_seoul or args.all_gyeonggi or args.all_courts:
        if args.all_seoul:
            target_courts = SEOUL_COURTS
            label_all = "서울 5개 법원"
            code_all = "서울전체"
        elif args.all_gyeonggi:
            target_courts = GYEONGGI_COURTS
            label_all = "경기/인천 7개 법원"
            code_all = "경기인천전체"
        else:  # all_courts
            target_courts = ALL_COURTS
            label_all = "수도권 전체 법원"
            code_all = "수도권전체"

        results: list[BatchResult] = []
        aborted = False
        for code, name in target_courts.items():
            # 법원별 실패 격리 — 한 법원의 예외가 나머지 법원 수집을 죽이지 않는다
            try:
                result = run_single_court(
                    court_code=code,
                    max_items=args.max,
                    force=args.force,
                    delay=args.delay,
                    dry_run=args.dry_run,
                    skip_occupancy=args.skip_occupancy,
                )
                results.append(result)
            except GracefulTermination:
                print(f"\n!!! SIGTERM 수신 — {name}({code}) 처리 중 중단, 이후 법원 스킵")
                aborted = True
                break
            except Exception as e:
                print(f"\n!!! {name}({code}) 수집 실패 (다음 법원 계속): {e}")
                continue
            if _terminating:
                aborted = True
                break

        # 전체 요약
        total_processed = sum(r.processed for r in results)
        total_errors = sum(len(r.errors) for r in results)
        status_label = " (SIGTERM 중단됨)" if aborted else ""
        print(f"\n{'='*50}")
        print(f"{label_all} 수집 완료{status_label}: {total_processed}건 처리, {total_errors}건 에러")
        print(f"{'='*50}")

        # 텔레그램 알림 (전체 합산)
        if not args.dry_run:
            total_a = sum(r.new_grade_a for r in results)
            total_b = sum(r.new_grade_b for r in results)
            total_new = sum(r.new_count for r in results)
            total_searched = sum(r.total_searched for r in results)
            if total_a > 0 or total_b > 0:
                msg = format_batch_summary(
                    court_code=code_all,
                    court_label=label_all,
                    total_searched=total_searched,
                    new_count=total_new,
                    new_a=total_a,
                    new_b=total_b,
                    errors=total_errors,
                )
                send_telegram(msg)
        if aborted:
            sys.exit(1)
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
            court_label = ALL_COURTS.get(args.court, args.court)
            notify_result(result, court_label=court_label)


if __name__ == "__main__":
    main()
