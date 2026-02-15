"""KYUNGSA 실전 E2E 검증 스크립트

실제 API를 호출하여 파이프라인 각 단계를 검증한다.
대법원 크롤러가 WAF 차단 중이므로, 주소 기반으로 각 서비스를 개별 검증.

단계:
  1_address_parse : 주소 파싱 (CodefAddressParams 추출)
  1_geocode       : 카카오 Geocode (주소→좌표)
  1_land_use      : Vworld 용도지역 (좌표→용도)
  1_building      : 건축물대장 (시군구+법정동+번지)
  1_market_price  : 실거래가 (시군구+거래월)
  2_codef_search  : CODEF 주소 검색 (주소→고유번호)
  2_codef_fetch   : CODEF 등기부 열람 (고유번호→등기부)
  2_registry_parse: 등기부 파싱 (RegistryDocument 변환)
  2_registry_analyze: 등기부 분석 (말소기준+인수/소멸+HS)

사용법:
  cd /Users/jeonghwan/Desktop/KYUNGSA
  PYTHONPATH=backend python scripts/e2e_validate.py
  PYTHONPATH=backend python scripts/e2e_validate.py --targets scripts/e2e_targets.json
  PYTHONPATH=backend python scripts/e2e_validate.py --skip-codef
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime

# 프로젝트 루트에서 실행 가정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.services.address_parser import (
    AddressParseError,
    parse_auction_address,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("e2e_validate")


# ── 결과 모델 ─────────────────────────────────────────


@dataclass
class StageResult:
    stage: str
    status: str  # PASS / FAIL / SKIP / PARTIAL
    detail: str = ""
    error: str = ""
    duration_ms: int = 0


@dataclass
class CaseResult:
    case_id: int
    address: str
    stages: list[StageResult] = field(default_factory=list)

    @property
    def overall(self) -> str:
        statuses = [s.status for s in self.stages]
        if all(s == "PASS" for s in statuses):
            return "ALL_PASS"
        if all(s in ("FAIL", "SKIP") for s in statuses):
            return "ALL_FAIL"
        return "PARTIAL"


@dataclass
class E2EReport:
    started_at: str = ""
    finished_at: str = ""
    api_status: dict = field(default_factory=dict)
    cases: list[CaseResult] = field(default_factory=list)
    bugs_found: list[str] = field(default_factory=list)


# ── 유틸 ─────────────────────────────────────────────


def _timer():
    """간단한 타이머"""
    start = time.time()

    class Timer:
        @property
        def ms(self):
            return int((time.time() - start) * 1000)

    return Timer()


def separator(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ── API 가용성 확인 ───────────────────────────────────


def check_api_availability() -> dict[str, str]:
    """각 서비스 API 키 존재 여부 확인"""
    status = {}

    # 카카오
    if settings.KAKAO_REST_API_KEY:
        status["카카오_Geocode"] = "SET"
    else:
        status["카카오_Geocode"] = "UNSET"

    # Vworld
    if settings.VWORLD_API_KEY:
        status["Vworld"] = "SET"
    else:
        status["Vworld"] = "UNSET"

    # 공공데이터
    if settings.PUBLIC_DATA_API_KEY:
        status["공공데이터"] = "SET"
    else:
        status["공공데이터"] = "UNSET"

    # CODEF
    svc_type = settings.CODEF_SERVICE_TYPE
    if svc_type == "demo":
        has_codef = bool(
            settings.CODEF_DEMO_CLIENT_ID and settings.CODEF_DEMO_CLIENT_SECRET
        )
    elif svc_type == "production":
        has_codef = bool(
            settings.CODEF_CLIENT_ID and settings.CODEF_CLIENT_SECRET
        )
    else:
        has_codef = bool(
            settings.CODEF_SANDBOX_CLIENT_ID
            and settings.CODEF_SANDBOX_CLIENT_SECRET
        )
    status["CODEF"] = "SET" if has_codef else "UNSET"
    status["CODEF_SERVICE_TYPE"] = svc_type

    return status


# ── 단계별 검증 ───────────────────────────────────────


def stage_address_parse(target: dict, result: CaseResult) -> dict | None:
    """1단 주소 파싱"""
    t = _timer()
    try:
        params = parse_auction_address(target["address"])
        detail_parts = []
        if params.sido:
            detail_parts.append(f"sido={params.sido}")
        if params.sigungu:
            detail_parts.append(f"sigungu={params.sigungu}")
        if params.dong:
            detail_parts.append(f"dong={params.dong}")
        if params.lot_number:
            detail_parts.append(f"lot={params.lot_number}")
        if params.road_name:
            detail_parts.append(f"road={params.road_name}")
        if params.building_number:
            detail_parts.append(f"bldg_no={params.building_number}")
        if params.building_name:
            detail_parts.append(f"bldg={params.building_name}")
        if params.warnings:
            detail_parts.append(f"warn={params.warnings}")

        result.stages.append(
            StageResult(
                stage="1_address_parse",
                status="PASS",
                detail=", ".join(detail_parts),
                duration_ms=t.ms,
            )
        )
        return {
            "sido": params.sido,
            "sigungu": params.sigungu,
            "dong": params.dong,
            "lot_number": params.lot_number,
            "road_name": params.road_name,
            "building_number": params.building_number,
            "building_name": params.building_name,
            "address_text": params.address_text,
        }
    except AddressParseError as e:
        result.stages.append(
            StageResult(
                stage="1_address_parse",
                status="FAIL",
                error=str(e),
                duration_ms=t.ms,
            )
        )
        return None


def stage_geocode(target: dict, result: CaseResult, api_status: dict) -> dict | None:
    """1단 카카오 Geocode"""
    if api_status.get("카카오_Geocode") != "SET":
        result.stages.append(
            StageResult(stage="1_geocode", status="SKIP", detail="API 키 없음")
        )
        return None

    from app.services.crawler.geo_client import GeoClient

    t = _timer()
    try:
        client = GeoClient()
        geo_result = client.geocode(target["address"])
        if geo_result:
            result.stages.append(
                StageResult(
                    stage="1_geocode",
                    status="PASS",
                    detail=f"x={geo_result['x']}, y={geo_result['y']}",
                    duration_ms=t.ms,
                )
            )
            return {"x": geo_result["x"], "y": geo_result["y"]}
        else:
            result.stages.append(
                StageResult(
                    stage="1_geocode",
                    status="FAIL",
                    error="결과 없음",
                    duration_ms=t.ms,
                )
            )
            return None
    except Exception as e:
        result.stages.append(
            StageResult(
                stage="1_geocode",
                status="FAIL",
                error=str(e)[:200],
                duration_ms=t.ms,
            )
        )
        return None


def stage_land_use(
    coords: dict | None, result: CaseResult, api_status: dict
) -> None:
    """1단 Vworld 용도지역"""
    if api_status.get("Vworld") != "SET":
        result.stages.append(
            StageResult(stage="1_land_use", status="SKIP", detail="API 키 없음")
        )
        return
    if not coords:
        result.stages.append(
            StageResult(
                stage="1_land_use", status="SKIP", detail="좌표 없음 (Geocode 실패)"
            )
        )
        return

    from app.services.crawler.geo_client import GeoClient

    t = _timer()
    try:
        client = GeoClient()
        land_use = client.fetch_land_use(coords["x"], coords["y"])
        if land_use:
            names = [item.get("name", "") for item in land_use[:3]]
            result.stages.append(
                StageResult(
                    stage="1_land_use",
                    status="PASS",
                    detail=f"{len(land_use)}건: {', '.join(names)}",
                    duration_ms=t.ms,
                )
            )
        else:
            result.stages.append(
                StageResult(
                    stage="1_land_use",
                    status="PASS",
                    detail="0건 (결과 없음, 에러는 아님)",
                    duration_ms=t.ms,
                )
            )
    except Exception as e:
        result.stages.append(
            StageResult(
                stage="1_land_use",
                status="FAIL",
                error=str(e)[:200],
                duration_ms=t.ms,
            )
        )


def stage_building(target: dict, result: CaseResult, api_status: dict) -> None:
    """1단 건축물대장"""
    if api_status.get("공공데이터") != "SET":
        result.stages.append(
            StageResult(stage="1_building", status="SKIP", detail="API 키 없음")
        )
        return

    from app.services.crawler.public_api import PublicDataClient

    sigungu_cd = target.get("sigungu_cd", "")
    bjdong_cd = target.get("bjdong_cd", "")
    if not sigungu_cd or not bjdong_cd:
        result.stages.append(
            StageResult(
                stage="1_building",
                status="SKIP",
                detail="sigungu_cd/bjdong_cd 없음",
            )
        )
        return

    t = _timer()
    try:
        client = PublicDataClient()
        items = client.fetch_building_register(sigungu_cd, bjdong_cd, "0001", "0000")
        result.stages.append(
            StageResult(
                stage="1_building",
                status="PASS",
                detail=f"{len(items)}건",
                duration_ms=t.ms,
            )
        )
    except Exception as e:
        result.stages.append(
            StageResult(
                stage="1_building",
                status="FAIL",
                error=str(e)[:200],
                duration_ms=t.ms,
            )
        )


def stage_market_price(target: dict, result: CaseResult, api_status: dict) -> None:
    """1단 실거래가"""
    if api_status.get("공공데이터") != "SET":
        result.stages.append(
            StageResult(stage="1_market_price", status="SKIP", detail="API 키 없음")
        )
        return

    from app.services.crawler.public_api import PublicDataClient

    sigungu_cd = target.get("sigungu_cd", "")
    if not sigungu_cd:
        result.stages.append(
            StageResult(
                stage="1_market_price", status="SKIP", detail="sigungu_cd 없음"
            )
        )
        return

    t = _timer()
    try:
        client = PublicDataClient()
        items = client.fetch_apt_trade(sigungu_cd, "202601")
        result.stages.append(
            StageResult(
                stage="1_market_price",
                status="PASS",
                detail=f"{len(items)}건 (202601)",
                duration_ms=t.ms,
            )
        )
    except Exception as e:
        result.stages.append(
            StageResult(
                stage="1_market_price",
                status="FAIL",
                error=str(e)[:200],
                duration_ms=t.ms,
            )
        )


def stage_codef_search(
    parsed_addr: dict | None,
    result: CaseResult,
    api_status: dict,
    skip_codef: bool,
) -> str | None:
    """2단 CODEF 주소검색"""
    if skip_codef:
        result.stages.append(
            StageResult(stage="2_codef_search", status="SKIP", detail="--skip-codef")
        )
        return None
    if api_status.get("CODEF") != "SET":
        result.stages.append(
            StageResult(stage="2_codef_search", status="SKIP", detail="API 키 없음")
        )
        return None
    if not parsed_addr:
        result.stages.append(
            StageResult(
                stage="2_codef_search", status="SKIP", detail="주소 파싱 실패"
            )
        )
        return None

    from app.services.crawler.codef_client import CodefClient
    from app.services.registry.codef_provider import CodefRegistryProvider

    t = _timer()
    try:
        provider = CodefRegistryProvider(codef_client=CodefClient())
        results_list = provider.search_by_address(
            sido=parsed_addr["sido"],
            sigungu=parsed_addr["sigungu"],
            addr_dong=parsed_addr["dong"],
            addr_lot_number=parsed_addr["lot_number"],
            building_name=parsed_addr["building_name"],
            address=parsed_addr["address_text"],
            addr_road_name=parsed_addr["road_name"],
            addr_building_number=parsed_addr["building_number"],
        )
        if results_list:
            unique_no = results_list[0].get("commUniqueNo", "")
            addr_display = results_list[0].get("commAddrLotNumber", "")[:40]
            result.stages.append(
                StageResult(
                    stage="2_codef_search",
                    status="PASS",
                    detail=f"{len(results_list)}건, unique_no={unique_no}, addr={addr_display}",
                    duration_ms=t.ms,
                )
            )
            return unique_no
        else:
            result.stages.append(
                StageResult(
                    stage="2_codef_search",
                    status="FAIL",
                    error="검색 결과 0건",
                    duration_ms=t.ms,
                )
            )
            return None
    except Exception as e:
        err_msg = str(e)[:200]
        # 2-Way 인증은 SKIP 처리
        if "2-Way" in err_msg or "TwoWay" in err_msg or "CF-03002" in err_msg:
            result.stages.append(
                StageResult(
                    stage="2_codef_search",
                    status="SKIP",
                    detail="2-Way 추가인증 필요",
                    duration_ms=t.ms,
                )
            )
        else:
            result.stages.append(
                StageResult(
                    stage="2_codef_search",
                    status="FAIL",
                    error=err_msg,
                    duration_ms=t.ms,
                )
            )
        return None


def stage_codef_fetch_and_analyze(
    unique_no: str | None,
    parsed_addr: dict | None,
    result: CaseResult,
    api_status: dict,
    skip_codef: bool,
) -> None:
    """2단 CODEF 등기부 열람 + 파싱 + 분석"""
    if skip_codef:
        result.stages.append(
            StageResult(
                stage="2_registry_full", status="SKIP", detail="--skip-codef"
            )
        )
        return
    if not unique_no:
        result.stages.append(
            StageResult(
                stage="2_registry_full", status="SKIP", detail="고유번호 없음"
            )
        )
        return

    from app.services.crawler.codef_client import CodefClient
    from app.services.parser.registry_analyzer import RegistryAnalyzer
    from app.services.registry.codef_provider import CodefRegistryProvider
    from app.services.registry.pipeline import RegistryPipeline

    t = _timer()
    try:
        provider = CodefRegistryProvider(codef_client=CodefClient())
        analyzer = RegistryAnalyzer()
        reg_pipeline = RegistryPipeline(provider=provider, analyzer=analyzer)

        addr = parsed_addr or {}
        reg_result = reg_pipeline.analyze_by_unique_no(
            unique_no=unique_no,
            addr_sido=addr.get("sido", ""),
            addr_sigungu=addr.get("sigungu", ""),
            addr_dong=addr.get("dong", ""),
            addr_lot_number=addr.get("lot_number", ""),
            addr_road_name=addr.get("road_name", ""),
            addr_building_number=addr.get("building_number", ""),
        )

        analysis = reg_result.analysis
        events_count = len(reg_result.registry_document.all_events)
        base_desc = ""
        if analysis.cancellation_base_event:
            base = analysis.cancellation_base_event
            base_desc = f"{base.event_type.value}"

        hs_list = [f.rule_id for f in analysis.hard_stop_flags]
        survive = len(analysis.surviving_rights)
        extinct = len(analysis.extinguished_rights)

        detail = (
            f"events={events_count}, base={base_desc or 'None'}, "
            f"HS={hs_list or 'None'}, survive={survive}, extinct={extinct}, "
            f"confidence={analysis.confidence.value}"
        )

        result.stages.append(
            StageResult(
                stage="2_registry_full",
                status="PASS",
                detail=detail,
                duration_ms=t.ms,
            )
        )
    except Exception as e:
        err_msg = str(e)[:200]
        if "2-Way" in err_msg or "TwoWay" in err_msg:
            result.stages.append(
                StageResult(
                    stage="2_registry_full",
                    status="SKIP",
                    detail="2-Way 추가인증 필요",
                    duration_ms=t.ms,
                )
            )
        else:
            result.stages.append(
                StageResult(
                    stage="2_registry_full",
                    status="FAIL",
                    error=err_msg,
                    duration_ms=t.ms,
                )
            )


# ── 물건 1건 검증 ─────────────────────────────────────


def validate_case(
    target: dict, api_status: dict, skip_codef: bool
) -> CaseResult:
    """물건 1건 전체 파이프라인 검증"""
    case_result = CaseResult(
        case_id=target["id"],
        address=target["address"],
    )

    # 1단: 주소 파싱
    parsed_addr = stage_address_parse(target, case_result)

    # 1단: Geocode
    coords = stage_geocode(target, case_result, api_status)

    # 1단: 용도지역
    stage_land_use(coords, case_result, api_status)

    # 1단: 건축물대장
    stage_building(target, case_result, api_status)

    # 1단: 실거래가
    stage_market_price(target, case_result, api_status)

    # API 간 쿨다운
    time.sleep(1)

    # 2단: CODEF 주소 검색
    unique_no = stage_codef_search(parsed_addr, case_result, api_status, skip_codef)

    # 2단: 등기부 열람 + 분석
    stage_codef_fetch_and_analyze(
        unique_no, parsed_addr, case_result, api_status, skip_codef
    )

    return case_result


# ── 보고서 생성 ───────────────────────────────────────


STATUS_ICON = {
    "PASS": "✅",
    "FAIL": "❌",
    "SKIP": "⏭️",
    "PARTIAL": "⚠️",
}


def generate_report(report: E2EReport, output_path: str) -> None:
    """마크다운 보고서 생성"""
    lines = []
    lines.append(f"# E2E 검증 보고서 — {report.started_at[:10]}")
    lines.append("")

    # 요약
    all_pass = sum(1 for c in report.cases if c.overall == "ALL_PASS")
    partial = sum(1 for c in report.cases if c.overall == "PARTIAL")
    all_fail = sum(1 for c in report.cases if c.overall == "ALL_FAIL")

    lines.append("## 요약")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|------|-----|")
    lines.append(f"| 검증 대상 | {len(report.cases)}건 |")
    lines.append(f"| ALL_PASS | {all_pass}건 |")
    lines.append(f"| PARTIAL | {partial}건 |")
    lines.append(f"| ALL_FAIL | {all_fail}건 |")
    lines.append(f"| 발견된 버그 | {len(report.bugs_found)}건 |")
    lines.append(f"| 시작 | {report.started_at} |")
    lines.append(f"| 종료 | {report.finished_at} |")
    lines.append("")

    # API 상태
    lines.append("## API 접근 상태")
    lines.append("")
    lines.append("| 서비스 | 상태 |")
    lines.append("|--------|------|")
    for svc, st in report.api_status.items():
        icon = "✅" if st == "SET" else "❌"
        lines.append(f"| {svc} | {icon} {st} |")
    lines.append("")

    # 물건별 결과
    lines.append("## 물건별 결과")
    lines.append("")
    for case in report.cases:
        icon = STATUS_ICON.get(case.overall, "❓")
        lines.append(f"### 물건 {case.case_id}: {case.address}")
        lines.append(f"**결과: {icon} {case.overall}**")
        lines.append("")
        lines.append("| 단계 | 상태 | 상세 | 소요 |")
        lines.append("|------|------|------|------|")
        for s in case.stages:
            s_icon = STATUS_ICON.get(s.status, "❓")
            detail = s.detail or s.error or ""
            # 테이블 안에서 | 문자 이스케이프
            detail = detail.replace("|", "\\|")
            lines.append(
                f"| {s.stage} | {s_icon} {s.status} | {detail} | {s.duration_ms}ms |"
            )
        lines.append("")

    # 버그
    if report.bugs_found:
        lines.append("## 발견된 버그")
        lines.append("")
        lines.append("| # | 설명 |")
        lines.append("|---|------|")
        for i, bug in enumerate(report.bugs_found, 1):
            lines.append(f"| {i} | {bug} |")
        lines.append("")

    # 결론
    lines.append("## 결론")
    lines.append("")
    if all_fail == len(report.cases):
        lines.append("- 전체 파이프라인 동작 여부: ❌ 전체 실패")
    elif all_pass == len(report.cases):
        lines.append("- 전체 파이프라인 동작 여부: ✅ 전체 통과")
    else:
        lines.append(
            f"- 전체 파이프라인 동작 여부: ⚠️ 부분 통과 ({all_pass}/{len(report.cases)})"
        )
    lines.append("")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n  → 보고서 저장: {output_path}")


# ── 메인 ─────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="KYUNGSA E2E 검증")
    parser.add_argument(
        "--targets",
        default=os.path.join(os.path.dirname(__file__), "e2e_targets.json"),
        help="검증 대상 JSON 파일 경로",
    )
    parser.add_argument(
        "--skip-codef",
        action="store_true",
        help="CODEF 등기부 단계 스킵 (API 비용 절약)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        dest="max_cases",
        help="최대 검증 건수 (0=전체)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  KYUNGSA — 실전 E2E 검증")
    print("=" * 60)

    # 타겟 로드
    with open(args.targets, encoding="utf-8") as f:
        targets = json.load(f)

    if args.max_cases > 0:
        targets = targets[: args.max_cases]

    print(f"  대상: {len(targets)}건")
    print(f"  CODEF: {'스킵' if args.skip_codef else '실행'}")

    # API 가용성
    separator("API 키 상태")
    api_status = check_api_availability()
    for svc, st in api_status.items():
        icon = "✅" if st == "SET" else "❌"
        print(f"  {svc}: {icon} {st}")

    # 보고서 초기화
    report = E2EReport(
        started_at=datetime.now().isoformat(),
        api_status=api_status,
    )

    # 각 물건 검증
    for i, target in enumerate(targets):
        separator(f"물건 {target['id']}/{len(targets)}: {target['address'][:40]}")
        print(f"  유형: {target.get('property_type', '?')} | {target.get('note', '')}")

        case_result = validate_case(target, api_status, args.skip_codef)
        report.cases.append(case_result)

        # 진행 상황 출력
        for s in case_result.stages:
            icon = STATUS_ICON.get(s.status, "?")
            line = f"  {icon} {s.stage}: "
            if s.status == "PASS":
                line += s.detail[:60]
            elif s.status == "FAIL":
                line += f"ERROR: {s.error[:60]}"
                # 버그 기록
                report.bugs_found.append(
                    f"[물건{target['id']}] {s.stage}: {s.error[:100]}"
                )
            elif s.status == "SKIP":
                line += s.detail[:60]
            print(line)

        print(f"  → 종합: {STATUS_ICON.get(case_result.overall, '?')} {case_result.overall}")

        # API 쿨다운
        if i < len(targets) - 1:
            time.sleep(2)

    report.finished_at = datetime.now().isoformat()

    # 최종 요약
    separator("최종 요약")
    all_pass = sum(1 for c in report.cases if c.overall == "ALL_PASS")
    partial = sum(1 for c in report.cases if c.overall == "PARTIAL")
    all_fail = sum(1 for c in report.cases if c.overall == "ALL_FAIL")
    print(f"  ALL_PASS: {all_pass}건 | PARTIAL: {partial}건 | ALL_FAIL: {all_fail}건")
    print(f"  발견된 버그: {len(report.bugs_found)}건")

    # 보고서 저장
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "docs",
        "review",
        f"{date_str}_e2e_validation.md",
    )
    generate_report(report, report_path)

    # JSON 원본도 저장
    json_path = report_path.replace(".md", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "started_at": report.started_at,
                "finished_at": report.finished_at,
                "api_status": report.api_status,
                "bugs_found": report.bugs_found,
                "cases": [
                    {
                        "case_id": c.case_id,
                        "address": c.address,
                        "overall": c.overall,
                        "stages": [asdict(s) for s in c.stages],
                    }
                    for c in report.cases
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  → JSON 저장: {json_path}")


if __name__ == "__main__":
    main()
