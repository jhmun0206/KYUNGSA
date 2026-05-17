"""bulk_registry_analysis.py — 등기 분석 일괄 실행 + 자동 재채점

본인 입찰 후보군(grade A/B)을 일괄 등기 분석하여 legal_score를 회복시킨다.

비용 안내:
  주소검색 20pt + 등기열람 100pt = 120pt/건
  --max 50 (기본) → 6,000pt
  진행중 grade A/B 추정 ~200건 → 24,000pt

절대 규칙:
  - dry-run으로 대상/비용 확인 후 사용자 승인 받고 실행
  - 분석 성공한 건은 자동 재채점 (Fix 3과 동일 로직)
  - 재채점 실패해도 유료 등기 분석은 보존

사용법:
  # dry-run (실호출 없음, 안전)
  PYTHONPATH=backend python scripts/bulk_registry_analysis.py --dry-run

  # 실호출 (반드시 dry-run으로 비용 확인 후)
  PYTHONPATH=backend python scripts/bulk_registry_analysis.py --grade A,B --status 진행 --max 50

서버 (venv):
  cd /home/eric/projects/KYUNGSA
  PYTHONPATH=backend backend/.venv/bin/python scripts/bulk_registry_analysis.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal  # noqa: E402
from app.models.db.auction import Auction  # noqa: E402
from app.models.db.registry import RegistryAnalysisORM  # noqa: E402
from app.models.db.score import Score  # noqa: E402

logger = logging.getLogger(__name__)

COST_PER_QUERY_PT = 120  # 틸코 주소검색(20pt) + 등기열람(100pt)


def select_targets(
    db,
    *,
    grades: list[str],
    status: str | None,
    max_items: int,
    skip_existing: bool,
) -> list[Auction]:
    """대상 물건 선정 — grade 필터 + status 필터 + (선택) 기존 분석 보유 제외"""
    q = (
        db.query(Auction)
        .join(Score, Score.auction_id == Auction.id)
        .filter(Score.grade.in_(grades))
    )
    if status:
        q = q.filter(Auction.status == status)
    if skip_existing:
        q = q.outerjoin(
            RegistryAnalysisORM,
            (RegistryAnalysisORM.case_number == Auction.case_number)
            & (RegistryAnalysisORM.property_sequence == Auction.property_sequence),
        ).filter(RegistryAnalysisORM.id.is_(None))
    q = q.order_by(Score.total_score.desc())
    if max_items > 0:
        q = q.limit(max_items)
    return q.all()


def analyze_one(db, auction: Auction) -> bool:
    """단건 분석 + 저장 + 재채점 (auctions.py 엔드포인트와 동일 패턴)."""
    from app.services.batch_collector import BatchCollector, BatchResult
    from app.services.parser.registry_analyzer import RegistryAnalyzer
    from app.services.parser.registry_parser import RegistryParser
    from app.services.registry.tilko_provider import TilkoRegistryProvider

    try:
        provider = TilkoRegistryProvider()
        pin, xml_str = provider.fetch_by_address(auction.address)
    except Exception as e:
        print(f"  [실패] {auction.case_number}: 틸코 조회 실패 — {e}")
        return False

    analysis = None
    try:
        reg_doc = RegistryParser().parse_text(xml_str)
        analysis = RegistryAnalyzer().analyze(reg_doc)
    except Exception as e:
        print(f"  [경고] {auction.case_number}: 분석 실패 (XML만 저장) — {e}")

    now = datetime.now(timezone.utc)
    orm = RegistryAnalysisORM(
        auction_id=auction.id,
        case_number=auction.case_number,
        property_sequence=auction.property_sequence or 1,
        fetched_by_user_id=None,
        fetched_at=now,
        registry_unique_no=pin,
        has_hard_stop=analysis.has_hard_stop if analysis else False,
        hard_stop_flags=(
            [getattr(f, "rule_id", str(f)) for f in analysis.hard_stop_flags]
            if analysis else []
        ),
        confidence=(analysis.confidence.value if analysis else "HIGH"),
        summary=(analysis.summary if analysis else ""),
        extinguished_rights=[],
        surviving_rights=[],
        uncertain_rights=[],
        warnings=(list(analysis.warnings) if analysis else []),
        analyzed_at=now,
    )
    db.add(orm)
    db.commit()

    # 자동 재채점 (Fix 3과 동일 로직)
    try:
        collector = BatchCollector(db=db)
        collector._skip_occupancy = False
        fake_result = BatchResult(
            run_id=f"bulk_registry_{uuid.uuid4().hex[:8]}",
            court_code=auction.court_office_code or "",
        )
        collector._rescore_single_from_db(
            auction_orm=auction, result=fake_result, dry_run=False
        )
    except Exception as e:
        print(f"  [경고] {auction.case_number}: 재채점 실패 (분석은 보존) — {e}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="등기 분석 일괄 실행 + 자동 재채점 (틸코 유료 API)"
    )
    parser.add_argument("--grade", default="A,B", help="대상 등급 (콤마 구분, 기본 A,B)")
    parser.add_argument("--status", default="진행", help="대상 status (기본 '진행', 빈문자열=전체)")
    parser.add_argument("--max", type=int, default=50, help="최대 처리 건수 (안전장치, 기본 50)")
    parser.add_argument("--dry-run", action="store_true", help="실호출 없이 대상+예상 비용만 출력")
    parser.add_argument(
        "--include-existing", action="store_true",
        help="이미 등기 분석 보유한 건도 포함 (기본: 제외)",
    )
    parser.add_argument("--yes", action="store_true", help="확인 프롬프트 자동 yes (위험)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    grades = [g.strip() for g in args.grade.split(",") if g.strip()]
    status = args.status if args.status != "" else None

    db = SessionLocal()
    try:
        targets = select_targets(
            db, grades=grades, status=status, max_items=args.max,
            skip_existing=not args.include_existing,
        )
        total_pt = len(targets) * COST_PER_QUERY_PT

        print("=== bulk_registry_analysis ===")
        print(f"  등급         : {grades}")
        print(f"  status       : {status or '(전체)'}")
        print(f"  max          : {args.max}")
        print(f"  기존 분석    : {'포함' if args.include_existing else '제외'}")
        print(f"  대상         : {len(targets)}건")
        print(f"  예상 비용    : {len(targets)}건 × {COST_PER_QUERY_PT}pt = {total_pt}pt")
        print()

        if not targets:
            print("대상 없음. 종료.")
            return

        print("--- 대상 미리보기 (최대 10건, total_score 내림차순) ---")
        for i, a in enumerate(targets[:10], 1):
            addr = (a.address or "")[:50]
            print(f"  [{i}] {a.case_number} seq={a.property_sequence} status={a.status} addr={addr}")
        if len(targets) > 10:
            print(f"  ... 외 {len(targets) - 10}건")

        if args.dry_run:
            print("\n*** DRY-RUN 모드: 실호출 없음. 종료. ***")
            return

        if not args.yes:
            ans = input(f"\n총 {total_pt}pt 소비 예정. 계속? [y/N]: ").strip().lower()
            if ans != "y":
                print("취소.")
                return

        ok, ng = 0, 0
        for i, auction in enumerate(targets, 1):
            print(f"[{i}/{len(targets)}] {auction.case_number} seq={auction.property_sequence}")
            if analyze_one(db, auction):
                ok += 1
            else:
                ng += 1

        print(f"\n=== 완료: 성공 {ok}건 / 실패 {ng}건 / 소비 약 {ok * COST_PER_QUERY_PT}pt ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
