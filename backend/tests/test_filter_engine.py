"""FilterEngine + 개별 룰 단위 테스트

룰 매칭 로직과 FilterEngine의 색상 결정/CostGate를 검증한다.
"""

import pytest

from app.models.auction import AuctionCaseDetail, AuctionPropertyObject
from app.models.enriched_case import (
    BuildingInfo,
    EnrichedCase,
    FilterColor,
    LandUseInfo,
    MarketPriceInfo,
)
from app.services.filter_engine import FilterEngine
from app.services.filter_rules import (
    check_r001_greenbelt,
    check_r002_building_violation,
    check_r003_land_only,
    check_y001_multiple_failures,
    check_y002_price_gap,
    check_y003_no_building_record,
)


# --- 테스트 헬퍼 ---

def _make_case(**overrides) -> AuctionCaseDetail:
    """테스트용 AuctionCaseDetail 생성"""
    defaults = {
        "case_number": "2025타경10001",
        "court": "서울중앙지방법원",
        "property_type": "아파트",
        "address": "서울특별시 강남구 역삼동 123-4",
        "appraised_value": 500_000_000,
        "minimum_bid": 400_000_000,
        "area_m2": 84.0,
    }
    defaults.update(overrides)
    return AuctionCaseDetail(**defaults)


def _make_enriched(**overrides) -> EnrichedCase:
    """테스트용 EnrichedCase 생성"""
    # EnrichedCase 전용 필드 (AuctionCaseDetail과 이름 충돌 방지)
    enriched_keys = {"coordinates", "building", "land_use", "market_price", "filter_result"}
    case_overrides = {}
    enriched_overrides = {}
    for k, v in overrides.items():
        if k in enriched_keys:
            enriched_overrides[k] = v
        else:
            case_overrides[k] = v
    return EnrichedCase(case=_make_case(**case_overrides), **enriched_overrides)


# === TestRedRules ===


class TestRedRules:
    """RED 룰 개별 테스트"""

    # R001: 개발제한구역
    def test_r001_greenbelt_matched(self):
        ec = _make_enriched(
            land_use=LandUseInfo(zones=["개발제한구역"], is_greenbelt=True)
        )
        assert check_r001_greenbelt(ec) is not None

    def test_r001_not_greenbelt(self):
        ec = _make_enriched(
            land_use=LandUseInfo(zones=["제3종일반주거지역"], is_greenbelt=False)
        )
        assert check_r001_greenbelt(ec) is None

    def test_r001_no_land_use(self):
        ec = _make_enriched(land_use=None)
        assert check_r001_greenbelt(ec) is None

    # R002: 위반건축물
    def test_r002_building_violation(self):
        ec = _make_enriched(
            building=BuildingInfo(violation=True)
        )
        assert check_r002_building_violation(ec) is not None

    def test_r002_specification_remarks(self):
        ec = _make_enriched(
            specification_remarks="본 물건은 위반건축물에 해당합니다",
        )
        assert check_r002_building_violation(ec) is not None

    def test_r002_no_violation(self):
        ec = _make_enriched(
            building=BuildingInfo(violation=False),
            specification_remarks="",
        )
        assert check_r002_building_violation(ec) is None

    # R003: 토지단독매각
    def test_r003_land_type(self):
        ec = _make_enriched(property_type="토지")
        assert check_r003_land_only(ec) is not None

    def test_r003_forestry_type(self):
        ec = _make_enriched(property_type="임야")
        assert check_r003_land_only(ec) is not None

    def test_r003_property_objects_all_land(self):
        ec = _make_enriched(
            property_type="아파트",
            property_objects=[
                AuctionPropertyObject(sequence=1, real_estate_type="토지"),
                AuctionPropertyObject(sequence=2, real_estate_type="임야"),
            ],
        )
        # property_type은 "아파트"지만 실제 물건은 토지/임야만
        assert check_r003_land_only(ec) is not None

    def test_r003_apartment_not_matched(self):
        ec = _make_enriched(property_type="아파트")
        assert check_r003_land_only(ec) is None

    def test_r003_mixed_objects_not_matched(self):
        ec = _make_enriched(
            property_type="건물",
            property_objects=[
                AuctionPropertyObject(sequence=1, real_estate_type="전유"),
                AuctionPropertyObject(sequence=2, real_estate_type="토지"),
            ],
        )
        assert check_r003_land_only(ec) is None


# === TestYellowRules ===


class TestYellowRules:
    """YELLOW 룰 개별 테스트"""

    # Y001: 다수유찰
    def test_y001_three_failures(self):
        ec = _make_enriched(failed_count=3)
        assert check_y001_multiple_failures(ec) is not None

    def test_y001_five_failures(self):
        ec = _make_enriched(failed_count=5)
        result = check_y001_multiple_failures(ec)
        assert result is not None
        assert "5회" in result

    def test_y001_two_failures_not_matched(self):
        ec = _make_enriched(failed_count=2)
        assert check_y001_multiple_failures(ec) is None

    def test_y001_zero_failures(self):
        ec = _make_enriched(failed_count=0)
        assert check_y001_multiple_failures(ec) is None

    # Y002: 시세괴리
    def test_y002_large_gap_matched(self):
        """감정가 5억 vs 시세 단가로 계산한 추정시세 3억 → 66% 괴리"""
        ec = _make_enriched(
            appraised_value=500_000_000,
            area_m2=84.0,
            market_price=MarketPriceInfo(
                avg_price_per_m2=3_571_000,  # 3억/84㎡ ≈ 357만/㎡
                trade_count=5,
            ),
        )
        assert check_y002_price_gap(ec) is not None

    def test_y002_small_gap_not_matched(self):
        """감정가 5억 vs 추정시세 4.5억 → 11% 괴리"""
        ec = _make_enriched(
            appraised_value=500_000_000,
            area_m2=84.0,
            market_price=MarketPriceInfo(
                avg_price_per_m2=5_357_000,  # 4.5억/84㎡ ≈ 535만/㎡
                trade_count=5,
            ),
        )
        assert check_y002_price_gap(ec) is None

    def test_y002_no_market_price(self):
        ec = _make_enriched(market_price=None)
        assert check_y002_price_gap(ec) is None

    def test_y002_no_area(self):
        ec = _make_enriched(
            area_m2=None,
            market_price=MarketPriceInfo(avg_price_per_m2=5_000_000),
        )
        assert check_y002_price_gap(ec) is None

    # Y003: 건축물대장미확인
    def test_y003_no_building_matched(self):
        ec = _make_enriched(building=None, property_type="아파트")
        assert check_y003_no_building_record(ec) is not None

    def test_y003_land_excluded(self):
        """토지는 건축물대장 없어도 정상"""
        ec = _make_enriched(building=None, property_type="토지")
        assert check_y003_no_building_record(ec) is None

    def test_y003_forestry_excluded(self):
        ec = _make_enriched(building=None, property_type="임야")
        assert check_y003_no_building_record(ec) is None

    def test_y003_building_exists_not_matched(self):
        ec = _make_enriched(building=BuildingInfo())
        assert check_y003_no_building_record(ec) is None


# === TestFilterEngine ===


class TestFilterEngine:
    """FilterEngine 통합 테스트"""

    def setup_method(self):
        self.engine = FilterEngine()

    def test_green_no_rules_matched(self):
        """아무 룰도 매칭 안 되면 GREEN"""
        ec = _make_enriched(
            building=BuildingInfo(violation=False),
            land_use=LandUseInfo(is_greenbelt=False),
            failed_count=0,
        )
        result = self.engine.evaluate(ec)

        assert result.color == FilterColor.GREEN
        assert result.passed is True
        assert len(result.matched_rules) == 0

    def test_red_blocks(self):
        """RED 매칭 → passed=False"""
        ec = _make_enriched(
            land_use=LandUseInfo(zones=["개발제한구역"], is_greenbelt=True),
        )
        result = self.engine.evaluate(ec)

        assert result.color == FilterColor.RED
        assert result.passed is False
        assert any(r.rule_id == "R001" for r in result.matched_rules)

    def test_yellow_allows(self):
        """YELLOW만 매칭 → passed=True"""
        ec = _make_enriched(
            failed_count=5,
            building=BuildingInfo(violation=False),
            land_use=LandUseInfo(is_greenbelt=False),
        )
        result = self.engine.evaluate(ec)

        assert result.color == FilterColor.YELLOW
        assert result.passed is True
        assert any(r.rule_id == "Y001" for r in result.matched_rules)

    def test_red_plus_yellow_is_red(self):
        """RED+YELLOW 동시 매칭 → RED 우선"""
        ec = _make_enriched(
            property_type="토지",
            failed_count=5,
            building=None,
        )
        result = self.engine.evaluate(ec)

        assert result.color == FilterColor.RED
        assert result.passed is False
        # RED(R003)과 YELLOW(Y001) 모두 기록됨
        rule_ids = {r.rule_id for r in result.matched_rules}
        assert "R003" in rule_ids
        assert "Y001" in rule_ids

    def test_all_none_fields_green(self):
        """보강 데이터 전부 None이어도 GREEN 가능"""
        ec = _make_enriched(
            property_type="아파트",
            failed_count=0,
            building=None,  # Y003 매칭됨
            land_use=None,
            market_price=None,
        )
        result = self.engine.evaluate(ec)

        # building=None이면 Y003 매칭 (아파트는 건축물대장 필요)
        assert result.color == FilterColor.YELLOW
        assert result.passed is True

    def test_evaluate_batch(self):
        """배치 평가"""
        cases = [
            _make_enriched(
                building=BuildingInfo(violation=False),
                land_use=LandUseInfo(is_greenbelt=False),
                failed_count=0,
            ),
            _make_enriched(
                property_type="토지",
            ),
        ]
        results = self.engine.evaluate_batch(cases)

        assert len(results) == 2
        assert results[0].filter_result.color == FilterColor.GREEN
        assert results[1].filter_result.color == FilterColor.RED


# === TestCostGate ===


class TestCostGate:
    """CostGate (passed 필드) 검증"""

    def setup_method(self):
        self.engine = FilterEngine()

    def test_red_blocks_cost_gate(self):
        ec = _make_enriched(
            land_use=LandUseInfo(zones=["개발제한구역"], is_greenbelt=True),
        )
        result = self.engine.evaluate(ec)
        assert result.passed is False

    def test_yellow_passes_cost_gate(self):
        ec = _make_enriched(
            failed_count=5,
            building=BuildingInfo(violation=False),
            land_use=LandUseInfo(is_greenbelt=False),
        )
        result = self.engine.evaluate(ec)
        assert result.passed is True

    def test_green_passes_cost_gate(self):
        ec = _make_enriched(
            building=BuildingInfo(violation=False),
            land_use=LandUseInfo(is_greenbelt=False),
            failed_count=0,
        )
        result = self.engine.evaluate(ec)
        assert result.passed is True
