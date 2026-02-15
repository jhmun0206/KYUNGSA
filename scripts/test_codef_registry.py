"""CODEF 등기부등본 데모 API 실제 호출 테스트

⚠️ 실행 시 전자민원캐시가 차감됩니다! (건당 700~1,000원)
⚠️ .env 파일에 모든 CODEF 키가 설정되어 있어야 합니다.

사용법:
    # Step 1: 주소 검색 (캐시 미차감)
    python scripts/test_codef_registry.py --step search

    # Step 2: 등기부등본 열람 (캐시 차감!)
    python scripts/test_codef_registry.py --step fetch --unique-no <고유번호>

    # Step 3: 전체 (검색 → 열람 → 분석)
    python scripts/test_codef_registry.py --step full

환경변수 필요:
    CODEF_SERVICE_TYPE=demo
    CODEF_DEMO_CLIENT_ID=...
    CODEF_DEMO_CLIENT_SECRET=...
    CODEF_PUBLIC_KEY=...
    IROS_PHONE_NO=...
    IROS_PASSWORD=...
    IROS_EPREPAY_NO=...
    IROS_EPREPAY_PASS=...
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# backend를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("test_codef_registry")


def check_env() -> list[str]:
    """필수 환경변수 체크 → 누락 목록 반환"""
    required = {
        "CODEF_DEMO_CLIENT_ID": settings.CODEF_DEMO_CLIENT_ID,
        "CODEF_DEMO_CLIENT_SECRET": settings.CODEF_DEMO_CLIENT_SECRET,
        "CODEF_PUBLIC_KEY": settings.CODEF_PUBLIC_KEY,
        "IROS_PHONE_NO": settings.IROS_PHONE_NO,
        "IROS_PASSWORD": settings.IROS_PASSWORD,
        "IROS_EPREPAY_NO": settings.IROS_EPREPAY_NO,
        "IROS_EPREPAY_PASS": settings.IROS_EPREPAY_PASS,
    }
    missing = [k for k, v in required.items() if not v]
    return missing


def step_search(
    sido: str = "서울특별시",
    sigungu: str = "강남구",
    addr_dong: str = "",
    addr_lot_number: str = "",
    building_name: str = "",
    dong: str = "",
    ho: str = "",
    address: str = "",
) -> list[dict]:
    """Step 1: 주소 검색 (캐시 미차감)"""
    from app.services.registry.codef_provider import CodefRegistryProvider

    provider = CodefRegistryProvider()
    logger.info("=== 주소 검색 시작 ===")
    logger.info("  시도: %s, 시군구: %s, 동: %s, 지번: %s, 건물명: %s, 주소: %s",
                sido, sigungu, addr_dong, addr_lot_number, building_name, address)

    try:
        results = provider.search_by_address(
            sido=sido,
            sigungu=sigungu,
            addr_dong=addr_dong,
            addr_lot_number=addr_lot_number,
            building_name=building_name,
            dong=dong,
            ho=ho,
            address=address,
        )
        logger.info("검색 결과: %d건", len(results))
        for i, item in enumerate(results[:10]):  # 최대 10건 출력
            logger.info("  [%d] %s", i + 1, json.dumps(item, ensure_ascii=False, indent=2))
        return results
    except Exception as e:
        logger.error("주소 검색 실패: %s", e)
        raise


def step_fetch(unique_no: str, realty_type: str = "3") -> dict:
    """Step 2: 등기부등본 열람 (캐시 차감!)"""
    from app.services.registry.codef_provider import CodefRegistryProvider

    provider = CodefRegistryProvider()
    logger.info("=== 등기부등본 열람 시작 ===")
    logger.info("  고유번호: %s, 부동산유형: %s", unique_no, realty_type)

    try:
        doc = provider.fetch_registry(unique_no, realty_type)
        logger.info("=== 열람 성공 ===")
        logger.info("  source: %s", doc.source)
        logger.info("  신뢰도: %s", doc.parse_confidence)
        logger.info("  갑구 이벤트: %d건", len(doc.gapgu_events))
        logger.info("  을구 이벤트: %d건", len(doc.eulgu_events))
        logger.info("  전체 이벤트: %d건", len(doc.all_events))

        if doc.title:
            logger.info("  주소: %s", doc.title.address)
            logger.info("  면적: %s㎡", doc.title.area)
            logger.info("  구조: %s", doc.title.structure)

        for evt in doc.all_events:
            logger.info(
                "  [%s] %s %s | %s | %s | %s원 | 말소=%s",
                evt.section.value,
                evt.rank_no or "-",
                evt.event_type.value,
                evt.accepted_at or "-",
                evt.holder or "-",
                f"{evt.amount:,}" if evt.amount else "-",
                evt.canceled,
            )

        # 원시 응답도 JSON으로 저장 (fixture 교체용)
        output_path = Path(__file__).parent.parent / "backend" / "tests" / "fixtures" / "codef_registry_real_response.json"
        # RegistryDocument는 Pydantic → dict 변환
        doc_dict = doc.model_dump(mode="json")
        output_path.write_text(
            json.dumps(doc_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("  RegistryDocument JSON 저장: %s", output_path)

        return doc_dict

    except Exception as e:
        logger.error("등기부등본 열람 실패: %s", e)
        raise


def step_analyze(unique_no: str, realty_type: str = "3") -> None:
    """Step 3: 열람 + 분석"""
    from app.services.parser.registry_analyzer import RegistryAnalyzer
    from app.services.registry.codef_provider import CodefRegistryProvider

    provider = CodefRegistryProvider()
    analyzer = RegistryAnalyzer()

    logger.info("=== 등기부등본 열람 + 분석 ===")
    doc = provider.fetch_registry(unique_no, realty_type)

    logger.info("--- 파싱 결과 ---")
    logger.info("  이벤트 수: 갑구 %d / 을구 %d", len(doc.gapgu_events), len(doc.eulgu_events))

    result = analyzer.analyze(doc)

    logger.info("--- 분석 결과 ---")
    if result.cancellation_base_event:
        base = result.cancellation_base_event
        logger.info("  말소기준권리: %s (%s) - %s",
                     base.event_type.value, base.accepted_at, result.cancellation_base_reason)
    else:
        logger.info("  말소기준권리: 없음")

    logger.info("  소멸 권리: %d건", len(result.extinguished_rights))
    for r in result.extinguished_rights:
        logger.info("    - %s %s (%s)", r.event.event_type.value, r.event.accepted_at, r.reason)

    logger.info("  인수 권리: %d건", len(result.surviving_rights))
    for r in result.surviving_rights:
        logger.info("    - %s %s (%s)", r.event.event_type.value, r.event.accepted_at, r.reason)

    logger.info("  불확실: %d건", len(result.uncertain_rights))
    for r in result.uncertain_rights:
        logger.info("    - %s %s (%s)", r.event.event_type.value, r.event.accepted_at, r.reason)

    logger.info("  Hard Stop: %s (%d건)", result.has_hard_stop, len(result.hard_stop_flags))
    for hs in result.hard_stop_flags:
        logger.info("    - [%s] %s: %s", hs.rule_id, hs.name, hs.description)

    logger.info("  신뢰도: %s", result.confidence)
    logger.info("  요약: %s", result.summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="CODEF 등기부등본 데모 API 테스트")
    parser.add_argument(
        "--step",
        choices=["search", "fetch", "full", "env-check"],
        default="env-check",
        help="실행 단계 (기본: env-check)",
    )
    parser.add_argument("--unique-no", help="부동산 고유번호 (14자리)")
    parser.add_argument("--realty-type", default="3", help="부동산유형 (1:토지, 2:건물, 3:집합건물)")
    parser.add_argument("--sido", default="서울특별시")
    parser.add_argument("--sigungu", default="강남구")
    parser.add_argument("--addr-dong", default="", help="법정동 (예: 역삼동)")
    parser.add_argument("--addr-lot-number", default="", help="지번 (예: 123-45)")
    parser.add_argument("--building-name", default="")
    parser.add_argument("--dong", default="", help="건물 동 (예: 1)")
    parser.add_argument("--ho", default="", help="호 (예: 804)")
    parser.add_argument("--address", default="", help="주소 (예: 테헤란로 406)")
    args = parser.parse_args()

    # 환경변수 체크
    missing = check_env()
    if missing:
        logger.error("누락된 환경변수: %s", ", ".join(missing))
        logger.error(".env 파일을 확인하세요.")
        if args.step != "env-check":
            sys.exit(1)
    else:
        logger.info("환경변수 체크 완료 — 모든 필수 변수 설정됨")

    # CODEF_SERVICE_TYPE 확인
    logger.info("CODEF_SERVICE_TYPE: %s", settings.CODEF_SERVICE_TYPE)
    if settings.CODEF_SERVICE_TYPE != "demo":
        logger.warning("⚠️  CODEF_SERVICE_TYPE이 'demo'가 아닙니다: %s", settings.CODEF_SERVICE_TYPE)
        logger.warning("   데모 API를 사용하려면 CODEF_SERVICE_TYPE=demo 으로 설정하세요.")

    if args.step == "env-check":
        return

    if args.step == "search":
        step_search(
            sido=args.sido,
            sigungu=args.sigungu,
            addr_dong=args.addr_dong,
            addr_lot_number=args.addr_lot_number,
            building_name=args.building_name,
            dong=args.dong,
            ho=args.ho,
            address=args.address,
        )

    elif args.step == "fetch":
        if not args.unique_no:
            logger.error("--unique-no 파라미터가 필요합니다")
            sys.exit(1)
        step_fetch(args.unique_no, args.realty_type)

    elif args.step == "full":
        if not args.unique_no:
            logger.error("--unique-no 파라미터가 필요합니다")
            sys.exit(1)
        step_analyze(args.unique_no, args.realty_type)


if __name__ == "__main__":
    main()
