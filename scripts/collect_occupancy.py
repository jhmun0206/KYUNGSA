"""현황조사서 수집기 CLI (Phase 7-2)

대법원 경매정보에서 현황조사서(selectCurstExmndc) JSON을 수집하여 DB에 저장한다.

사용법:
    # 단건 수집
    PYTHONPATH=backend python scripts/collect_occupancy.py \
      --case-number 20220130112176 --court B000210 --seq 1

    # DB 분석대기 물건 일괄 수집 (backfill)
    PYTHONPATH=backend python scripts/collect_occupancy.py \
      --backfill --court B000210 --limit 50 --delay 3

    # dry-run (API 호출 + 파싱만, DB 미저장)
    PYTHONPATH=backend python scripts/collect_occupancy.py \
      --backfill --court B000210 --dry-run --limit 5

서버 (venv 환경):
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/collect_occupancy.py --backfill --court B000210
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.crawler.court_auction import CourtAuctionClient  # noqa: E402
from app.services.occupancy.service import OccupancyService  # noqa: E402

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


def run_single(
    case_number: str,
    court: str,
    seq: str,
    formatted: str | None,
    dry_run: bool,
) -> None:
    """단건 수집"""
    db = SessionLocal()
    try:
        crawler = CourtAuctionClient()
        svc = OccupancyService(db=db, crawler=crawler)

        if dry_run:
            # dry-run: API 호출 + 파싱만
            raw = crawler.fetch_occupancy_report(case_number, court, seq)
            if not raw:
                print("현황조사서 응답 없음")
                return
            from app.services.occupancy.parser import OccupancyParser

            parser = OccupancyParser()
            dto = parser.parse(raw, formatted or case_number, court)
            print(f"파싱 완료: 임차인 {len(dto.tenants)}명, 물건 {len(dto.properties)}건")
            for t in dto.tenants:
                print(
                    f"  - {t.tenant_name} ({t.party_type}) "
                    f"보증금={t.deposit_raw} 월세={t.monthly_rent_raw} "
                    f"전입={t.move_in_date_raw}"
                )
        else:
            report = svc.collect_and_save(
                internal_case_number=case_number,
                court_office_code=court,
                property_sequence=seq,
                formatted_case_number=formatted or case_number,
            )
            if report:
                print(f"저장 완료: {report.case_number}")
            else:
                print("현황조사서 없음")
    finally:
        db.close()


def run_backfill(
    court: str | None,
    limit: int,
    delay: float,
    dry_run: bool,
) -> None:
    """DB 분석대기 물건 일괄 수집"""
    db = SessionLocal()
    try:
        crawler = CourtAuctionClient()
        svc = OccupancyService(db=db, crawler=crawler)

        # 분석대기 물건 조회
        where_clause = "WHERE occupancy_status = '분석대기'"
        params: dict = {}
        if court:
            where_clause += " AND court_office_code = :court"
            params["court"] = court

        query = text(
            f"SELECT case_number, court_office_code, "
            f"COALESCE(detail->>'internal_case_number', '') as internal_cn, "
            f"COALESCE(detail->>'property_sequence', '1') as prop_seq "
            f"FROM auctions {where_clause} "
            f"ORDER BY created_at DESC LIMIT :limit"
        )
        params["limit"] = limit

        rows = db.execute(query, params).fetchall()
        total = len(rows)
        print(f"대상: {total}건 (court={court or '전체'})")

        success = 0
        skip = 0
        errors = 0

        for idx, row in enumerate(rows, 1):
            case_number = row[0]
            court_code = row[1]
            internal_cn = row[2]
            prop_seq = row[3] or "1"

            if not internal_cn:
                print(f"  [{idx}/{total}] {case_number}: internal_case_number 없음 → 스킵")
                skip += 1
                continue

            try:
                if dry_run:
                    raw = crawler.fetch_occupancy_report(internal_cn, court_code, prop_seq)
                    tenant_cnt = len(raw.get("dlt_curstExmndcDtl", [])) if raw else 0
                    print(f"  [{idx}/{total}] {case_number}: 임차인 {tenant_cnt}명 (dry-run)")
                else:
                    report = svc.collect_and_save(
                        internal_case_number=internal_cn,
                        court_office_code=court_code,
                        property_sequence=prop_seq,
                        formatted_case_number=case_number,
                    )
                    tenant_cnt = len(report.tenants) if report else 0
                    print(f"  [{idx}/{total}] {case_number}: 임차인 {tenant_cnt}명")

                success += 1
            except Exception as e:
                print(f"  [{idx}/{total}] {case_number}: 오류 — {e}")
                errors += 1
                try:
                    db.rollback()
                except Exception:
                    pass

            if idx < total:
                time.sleep(delay)

        print(f"\n완료: 성공={success} 스킵={skip} 오류={errors} / 전체={total}")
        if dry_run:
            print("※ dry-run 모드: DB 변경 없음")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="현황조사서 수집기 (Phase 7-2)")

    # 모드 선택
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case-number", help="내부 사건번호 (단건 수집)")
    group.add_argument("--backfill", action="store_true", help="DB 분석대기 물건 일괄 수집")

    # 단건 수집 옵션
    parser.add_argument("--court", help="법원코드 (예: B000210)")
    parser.add_argument("--seq", default="1", help="물건순서 (기본: 1)")
    parser.add_argument("--formatted", help="포맷된 사건번호 (단건 시 DB 저장용)")

    # backfill 옵션
    parser.add_argument("--limit", type=int, default=100, help="최대 처리 건수 (기본: 100)")
    parser.add_argument("--delay", type=float, default=3.0, help="건별 대기 시간 초 (기본: 3.0)")

    # 공통 옵션
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 확인만")
    parser.add_argument("--verbose", action="store_true", help="DEBUG 로그 출력")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.case_number:
        if not args.court:
            parser.error("--case-number 사용 시 --court 필수")
        run_single(
            case_number=args.case_number,
            court=args.court,
            seq=args.seq,
            formatted=args.formatted,
            dry_run=args.dry_run,
        )
    else:
        run_backfill(
            court=args.court,
            limit=args.limit,
            delay=args.delay,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
