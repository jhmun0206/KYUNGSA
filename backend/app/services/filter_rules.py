"""1단 필터 룰 정의

RED: 즉시 제외 (passed=False)
YELLOW: 주의 필요 (passed=True, 경고 부착)
GREEN: 아무 룰도 매칭되지 않음

각 룰은 (EnrichedCase) -> str | None 함수.
None이면 매칭 없음, 문자열이면 사유.
룰 변경 시 반드시 docs/rules/에 기록하고 테스트를 동반할 것.
"""

from typing import Callable

from app.models.enriched_case import EnrichedCase

RuleFunc = Callable[[EnrichedCase], str | None]


# === RED 룰 (즉시 제외) ===


def check_r001_greenbelt(ec: EnrichedCase) -> str | None:
    """R001: 개발제한구역 (그린벨트)"""
    if ec.land_use and ec.land_use.is_greenbelt:
        return "개발제한구역(그린벨트)에 위치하여 개발·이용 제한"
    return None


def check_r002_building_violation(ec: EnrichedCase) -> str | None:
    """R002: 위반건축물"""
    if ec.building and ec.building.violation:
        return "건축물대장 상 위반건축물로 등재"
    # 물건명세서 비고에서도 확인
    remarks = ec.case.specification_remarks or ""
    if "위반건축물" in remarks:
        return "물건명세서 비고에 위반건축물 기재"
    return None


def check_r003_land_only(ec: EnrichedCase) -> str | None:
    """R003: 토지/임야 단독 (건물 없음 → 법정지상권 위험)"""
    prop_type = ec.case.property_type
    if prop_type in ("토지", "임야"):
        return f"물건 유형이 '{prop_type}'으로 건물 없는 토지 단독 매각"
    if ec.case.property_objects:
        types = {obj.real_estate_type for obj in ec.case.property_objects}
        if types and types <= {"토지", "임야"}:
            return "매각 대상이 토지/임야만으로 구성"
    return None


# === YELLOW 룰 (주의) ===


def check_y001_multiple_failures(ec: EnrichedCase) -> str | None:
    """Y001: 3회 이상 유찰"""
    if ec.case.failed_count >= 3:
        return f"유찰 {ec.case.failed_count}회 (수요 부진 또는 권리관계 복잡 가능성)"
    return None


def check_y002_price_gap(ec: EnrichedCase) -> str | None:
    """Y002: 감정가 vs 시세 괴리 30% 이상"""
    if not ec.market_price or ec.market_price.avg_price_per_m2 is None:
        return None
    area = ec.case.area_m2
    if not area or area <= 0:
        return None
    estimated_market = ec.market_price.avg_price_per_m2 * area
    if estimated_market <= 0:
        return None
    appraised = ec.case.appraised_value
    if appraised <= 0:
        return None
    gap_ratio = abs(appraised - estimated_market) / estimated_market
    if gap_ratio >= 0.3:
        return (
            f"감정가({appraised:,}원)와 추정시세({estimated_market:,.0f}원) "
            f"괴리율 {gap_ratio:.0%}"
        )
    return None


def check_y003_no_building_record(ec: EnrichedCase) -> str | None:
    """Y003: 건축물대장 미확인"""
    if ec.building is None:
        # 토지/임야는 건축물대장 없는 게 정상
        if ec.case.property_type in ("토지", "임야"):
            return None
        return "건축물대장 조회 결과 없음 (미등재 또는 조회 실패)"
    return None


# 룰 레지스트리: (id, name, func)
RED_RULES: list[tuple[str, str, RuleFunc]] = [
    ("R001", "개발제한구역", check_r001_greenbelt),
    ("R002", "위반건축물", check_r002_building_violation),
    ("R003", "토지단독매각", check_r003_land_only),
]

YELLOW_RULES: list[tuple[str, str, RuleFunc]] = [
    ("Y001", "다수유찰", check_y001_multiple_failures),
    ("Y002", "시세괴리", check_y002_price_gap),
    ("Y003", "건축물대장미확인", check_y003_no_building_record),
]
