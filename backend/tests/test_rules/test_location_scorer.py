"""LocationScorer 단위 테스트 (Phase 6)

서브스코어 곡선, 유형별 가중합, 신뢰도, fail-open, 통합 테스트.
모두 mock 전용 — 외부 API 미호출.
"""

from __future__ import annotations

import pytest

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import LandUseInfo, LocationData
from app.services.rules.location_scorer import (
    STATION_FLOOR,
    LocationScorer,
    _calc_amenity_score,
    _calc_land_use_score,
    _calc_school_score,
    _calc_station_score,
    _interpolate,
)


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

def _make_case(property_type: str = "아파트") -> AuctionCaseDetail:
    """최소 AuctionCaseDetail 생성"""
    return AuctionCaseDetail(
        case_number="2025타경99999",
        court="서울중앙지방법원",
        address="서울특별시 강남구 역삼동 123",
        property_type=property_type,
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
        bid_count=1,
        status="진행",
    )


def _make_location(
    nearest_station_m: int | None = None,
    nearest_school_m: int | None = None,
    amenity_count_500m: int = 0,
    categories_fetched: list[str] | None = None,
) -> LocationData:
    return LocationData(
        nearest_station_m=nearest_station_m,
        nearest_school_m=nearest_school_m,
        amenity_count_500m=amenity_count_500m,
        categories_fetched=categories_fetched or [],
    )


# ─────────────────────────────────────────────
# TestInterpolate
# ─────────────────────────────────────────────

class TestInterpolate:
    def test_below_first_point(self):
        curve = [(0, 100), (500, 85)]
        assert _interpolate(curve, -10) == 100.0

    def test_above_last_point_clamps(self):
        curve = [(0, 100), (500, 85), (3000, 10)]
        assert _interpolate(curve, 5000) == 10.0

    def test_exact_point(self):
        curve = [(0, 100), (500, 85), (1000, 55)]
        assert _interpolate(curve, 500) == pytest.approx(85.0, abs=0.1)

    def test_midpoint(self):
        # (0,100)~(500,85) 250m → 100 + 0.5*(85-100) = 92.5
        curve = [(0, 100), (500, 85)]
        assert _interpolate(curve, 250) == pytest.approx(92.5, abs=0.1)


# ─────────────────────────────────────────────
# TestStationScore
# ─────────────────────────────────────────────

class TestStationScore:
    def test_none_returns_floor(self):
        """역 없음 → 하한값 10 반환"""
        assert _calc_station_score(None) == STATION_FLOOR

    def test_200m_high_score(self):
        # 0→100, 500→85, 200m: t=0.4, 100+0.4*(85-100)=94
        result = _calc_station_score(200)
        assert result == pytest.approx(94.0, abs=0.5)

    def test_700m_mid_score(self):
        # 500→85, 800→68, t=(700-500)/300=0.667, 85+0.667*(68-85)=73.7
        result = _calc_station_score(700)
        assert result == pytest.approx(73.7, abs=1.0)

    def test_1800m_low_score(self):
        # 1500→35, 2000→20, t=(1800-1500)/500=0.6, 35+0.6*(20-35)=26
        result = _calc_station_score(1800)
        assert result == pytest.approx(26.0, abs=1.0)

    def test_3000m_or_beyond_equals_floor(self):
        """3000m 이상 → 하한 10점 (클램프)"""
        assert _calc_station_score(3000) == pytest.approx(10.0, abs=0.1)
        assert _calc_station_score(5000) == pytest.approx(10.0, abs=0.1)

    def test_0m_returns_100(self):
        assert _calc_station_score(0) == pytest.approx(100.0, abs=0.1)


# ─────────────────────────────────────────────
# TestAmenityScore
# ─────────────────────────────────────────────

class TestAmenityScore:
    def test_zero_count(self):
        assert _calc_amenity_score(0) == pytest.approx(0.0, abs=0.1)

    def test_three_count(self):
        assert _calc_amenity_score(3) == pytest.approx(40.0, abs=0.1)

    def test_seven_count(self):
        assert _calc_amenity_score(7) == pytest.approx(75.0, abs=0.1)

    def test_above_15_clamps_to_95(self):
        """15개+ 상한 95 (클램프)"""
        assert _calc_amenity_score(15) == pytest.approx(95.0, abs=0.1)
        assert _calc_amenity_score(20) == pytest.approx(95.0, abs=0.1)

    def test_12_interpolated(self):
        # 10→85, 15→95, t=(12-10)/5=0.4, 85+0.4*(95-85)=89
        assert _calc_amenity_score(12) == pytest.approx(89.0, abs=1.0)


# ─────────────────────────────────────────────
# TestSchoolScore
# ─────────────────────────────────────────────

class TestSchoolScore:
    def test_none_returns_zero(self):
        """1500m 내 학교 없음 → 0점"""
        assert _calc_school_score(None) == 0.0

    def test_within_500m_returns_100(self):
        assert _calc_school_score(300) == pytest.approx(100.0, abs=0.1)
        assert _calc_school_score(500) == pytest.approx(100.0, abs=0.1)

    def test_1200m_mid_score(self):
        # 1000→60, 1500→40, t=(1200-1000)/500=0.4, 60+0.4*(40-60)=52
        assert _calc_school_score(1200) == pytest.approx(52.0, abs=1.0)

    def test_1500m_clamps(self):
        assert _calc_school_score(1500) == pytest.approx(40.0, abs=0.1)


# ─────────────────────────────────────────────
# TestLandUseScore
# ─────────────────────────────────────────────

class TestLandUseScore:
    def test_commercial(self):
        assert _calc_land_use_score(["일반상업지역"]) == pytest.approx(100.0)

    def test_quasi_residential(self):
        assert _calc_land_use_score(["준주거지역"]) == pytest.approx(80.0)

    def test_second_general_residential(self):
        assert _calc_land_use_score(["제2종일반주거지역"]) == pytest.approx(70.0)

    def test_first_general_residential(self):
        assert _calc_land_use_score(["제1종일반주거지역"]) == pytest.approx(60.0)

    def test_quasi_industrial(self):
        assert _calc_land_use_score(["준공업지역"]) == pytest.approx(50.0)

    def test_empty_zones(self):
        assert _calc_land_use_score([]) == pytest.approx(30.0)

    def test_unknown_zone(self):
        assert _calc_land_use_score(["자연녹지지역"]) == pytest.approx(30.0)


# ─────────────────────────────────────────────
# TestLocationScorer — 유형별 가중합
# ─────────────────────────────────────────────

class TestLocationScorerPropertyCategory:
    def setup_method(self):
        self.scorer = LocationScorer()

    def test_apartment_uses_station_amenity_school(self):
        """아파트: station×0.45 + amenity×0.25 + school×0.30"""
        loc = _make_location(
            nearest_station_m=0,     # station_score = 100
            nearest_school_m=0,      # school_score  = 100
            amenity_count_500m=15,   # amenity_score = 95
            categories_fetched=["SW8", "SC4", "MT1", "CS2", "HP8"],
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        expected_base = 100 * 0.45 + 95 * 0.25 + 100 * 0.30
        assert result.base_score == pytest.approx(expected_base, abs=1.0)
        assert result.property_category == "아파트"

    def test_building_uses_station_amenity(self):
        """꼬마빌딩: station×0.55 + amenity×0.45"""
        loc = _make_location(
            nearest_station_m=0,   # station_score = 100
            amenity_count_500m=0,  # amenity_score = 0
            categories_fetched=["SW8", "MT1", "CS2", "HP8"],
        )
        result = self.scorer.score(_make_case("근린상가"), loc)
        assert result is not None
        expected_base = 100 * 0.55 + 0 * 0.45
        assert result.base_score == pytest.approx(expected_base, abs=1.0)
        assert result.property_category == "꼬마빌딩"

    def test_land_uses_station_land_use(self):
        """토지: station×0.30 + land_use×0.70"""
        loc = _make_location(
            nearest_station_m=0,   # station_score = 100
            categories_fetched=["SW8"],
        )
        land_use = LandUseInfo(zones=["일반상업지역"], is_greenbelt=False)
        result = self.scorer.score(_make_case("토지"), loc, land_use)
        assert result is not None
        expected_base = 100 * 0.30 + 100 * 0.70
        assert result.base_score == pytest.approx(expected_base, abs=1.0)
        assert result.property_category == "토지"


# ─────────────────────────────────────────────
# TestLocationScorer — 신뢰도
# ─────────────────────────────────────────────

class TestLocationScorerConfidence:
    def setup_method(self):
        self.scorer = LocationScorer()

    def test_high_confidence_with_5_categories(self):
        loc = _make_location(
            nearest_station_m=300,
            categories_fetched=["SW8", "SC4", "MT1", "CS2", "HP8"],
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        assert result.confidence == "HIGH"
        assert result.confidence_multiplier == pytest.approx(1.0)

    def test_medium_confidence_with_2_categories(self):
        loc = _make_location(
            nearest_station_m=300,
            categories_fetched=["SW8", "SC4"],
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        assert result.confidence == "MEDIUM"

    def test_low_confidence_with_1_category(self):
        loc = _make_location(
            nearest_station_m=300,
            categories_fetched=["SW8"],
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        assert result.confidence == "LOW"
        assert result.confidence_multiplier == pytest.approx(0.70)

    def test_building_auto_downgrades_to_medium(self):
        """꼬마빌딩: 5개 카테고리 성공해도 MEDIUM으로 제한"""
        loc = _make_location(
            nearest_station_m=100,
            categories_fetched=["SW8", "SC4", "MT1", "CS2", "HP8"],
        )
        result = self.scorer.score(_make_case("근린상가"), loc)
        assert result is not None
        assert result.confidence == "MEDIUM"
        assert result.confidence_multiplier == pytest.approx(0.85)
        assert any("MEDIUM" in w for w in result.warnings)


# ─────────────────────────────────────────────
# TestLocationScorer — fail-open
# ─────────────────────────────────────────────

class TestLocationScorerFailOpen:
    def setup_method(self):
        self.scorer = LocationScorer()

    def test_none_location_data_returns_none(self):
        """좌표 없음 → location_data=None → score() None 반환"""
        result = self.scorer.score(_make_case("아파트"), None)
        assert result is None

    def test_partial_api_failure_uses_floor(self):
        """SW8 실패(카테고리 미취득) → nearest_station_m=None → 하한 10점"""
        loc = _make_location(
            nearest_station_m=None,          # SW8 API 실패
            amenity_count_500m=5,
            nearest_school_m=300,
            categories_fetched=["SC4", "MT1", "CS2", "HP8"],  # SW8 없음
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        assert result.sub_scores.station_score == pytest.approx(STATION_FLOOR, abs=0.1)


# ─────────────────────────────────────────────
# TestLocationScorer — 통합
# ─────────────────────────────────────────────

class TestLocationScorerIntegration:
    def setup_method(self):
        self.scorer = LocationScorer()

    def test_excellent_apartment_scores_above_80(self):
        """우수 입지 아파트 → A등급 수준 (≥80) 기대"""
        loc = _make_location(
            nearest_station_m=300,   # 역 300m
            nearest_school_m=400,    # 학교 400m
            amenity_count_500m=9,    # 편의시설 9개
            categories_fetched=["SW8", "SC4", "MT1", "CS2", "HP8"],
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        assert result.score >= 80.0
        assert result.confidence == "HIGH"

    def test_poor_location_scores_below_30(self):
        """역 없음 + 편의시설 0 + 학교 없음 → 낮은 점수"""
        loc = _make_location(
            nearest_station_m=None,
            nearest_school_m=None,
            amenity_count_500m=0,
            categories_fetched=["SW8", "SC4", "MT1", "CS2", "HP8"],
        )
        result = self.scorer.score(_make_case("아파트"), loc)
        assert result is not None
        # station=10(floor), amenity=0, school=0
        # base = 10*0.45 + 0*0.25 + 0*0.30 = 4.5
        assert result.score < 30.0
