"""1단 필터링 파이프라인 CLI

사용법:
    python scripts/run_pipeline.py --court B000210 --max 5 --delay 3
    python scripts/run_pipeline.py --max 3 --output results.json
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.pipeline import AuctionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KYUNGSA 1단 필터링 파이프라인",
    )
    parser.add_argument(
        "--court",
        default="",
        help="법원코드 (예: B000210, 빈 문자열이면 전체)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=5,
        dest="max_items",
        help="최대 처리 물건 수 (기본: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="보강 API 호출 간 대기 시간 초 (기본: 3.0)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="결과 JSON 저장 경로 (미지정 시 저장 안 함)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  KYUNGSA — 1단 필터링 파이프라인")
    print("=" * 60)
    print(f"  법원코드: {args.court or '(전체)'}")
    print(f"  최대 처리: {args.max_items}건")
    print(f"  API 딜레이: {args.delay}초")
    print("=" * 60)

    pipeline = AuctionPipeline()
    result = pipeline.run(
        court_code=args.court,
        max_items=args.max_items,
        enrich_delay=args.delay,
    )

    # 결과 테이블 출력
    print(f"\n{'='*60}")
    print(f"  검색: {result.total_searched}건 | 보강: {result.total_enriched}건 | 필터: {result.total_filtered}건")
    print(f"  RED: {result.red_count} | YELLOW: {result.yellow_count} | GREEN: {result.green_count}")
    print(f"{'='*60}")

    for i, ec in enumerate(result.cases):
        color = ec.filter_result.color.value if ec.filter_result else "N/A"
        passed = ec.filter_result.passed if ec.filter_result else "N/A"
        addr = ec.case.address[:30] + "..." if len(ec.case.address) > 30 else ec.case.address

        print(f"\n  [{i+1}] {ec.case.case_number}")
        print(f"      주소: {addr}")
        print(f"      감정가: {ec.case.appraised_value:,}원 | 최저가: {ec.case.minimum_bid:,}원")
        print(f"      결과: {color} (통과: {passed})")

        if ec.filter_result and ec.filter_result.matched_rules:
            for rule in ec.filter_result.matched_rules:
                print(f"      → [{rule.rule_id}] {rule.rule_name}: {rule.description}")

    if result.errors:
        print(f"\n  --- 오류 ({len(result.errors)}건) ---")
        for err in result.errors:
            print(f"  ⚠ {err}")

    # JSON 저장
    if args.output:
        output_data = result.model_dump(mode="json")
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n  → 결과 저장: {args.output}")

    print()


if __name__ == "__main__":
    main()
