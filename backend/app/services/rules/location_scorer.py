"""입지 점수 산출기 (Phase 6)

역세권/편의시설/학군/용도지역 4개 서브스코어로 입지 매력도를 0~100으로 산출한다.
데이터 소스: 카카오 로컬 카테고리 검색 API (무료, fail-open).

=== 설계 원칙 ===
- 좌표 없음(coordinates=None) → location_data=None → score() → None 반환
  TotalScorer가 재정규화로 입지 pillar 제외 처리
- 선형 보간 (sigmoid/지수 곡선 미사용)
- 꼬마빌딩: 신뢰도 최대 MEDIUM (유동인구/대로변 데이터 미확보로 과대평가 방지)
- nearest_station_m=None (역 없음) → 하한값 10.0 반환 (0점 패널티 없음)
"""

from __future__ import annotations

import logging

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import LandUseInfo, LocationData
from app.models.scores import LocationScoreResult, LocationSubScores

logger = logging.getLogger(__name__)

# 유형별 내부 가중치 (합=1.0)
LOCATION_WEIGHTS: dict[str, dict[str, float]] = {
    "아파트":   {"station": 0.45, "amenity": 0.25, "school": 0.30},
    "꼬마빌딩": {"station": 0.55, "amenity": 0.45},
    "토지":     {"station": 0.30, "land_use": 0.70},
}

DEFAULT_CATEGORY = "꼬마빌딩"

# 역세권 곡선: (거리m, 점수) — 3000m 이상은 하한 10점
STATION_CURVE: list[tuple[int, float]] = [
    (0, 100), (500, 85), (800, 68), (1000, 55), (1500, 35), (2000, 20), (3000, 10),
]
STATION_FLOOR = 10.0  # nearest_station_m=None or ≥3000m 하한값

# 편의시설 곡선: (개수, 점수) — 15개+ 상한 95
AMENITY_CURVE: list[tuple[int, float]] = [
    (0, 0), (1, 15), (3, 40), (5, 60), (7, 75), (10, 85), (15, 95),
]

# 학군 곡선: (거리m, 점수) — 없음(None) → 0
SCHOOL_CURVE: list[tuple[int, float]] = [
    (0, 100), (500, 100), (800, 80), (1000, 60), (1500, 40),
]

# 용도지역 점수 (토지 전용) — 키워드 우선순위 매칭
LAND_USE_KEYWORD_SCORES: list[tuple[str, float]] = [
    ("상업지역", 100.0),
    ("준주거", 80.0),
    ("2종일반주거", 70.0),
    ("제2종일반주거", 70.0),
    ("1종일반주거", 60.0),
    ("제1종일반주거", 60.0),
    ("준공업", 50.0),
]
DEFAULT_LAND_USE_SCORE = 30.0

# 물건 유형 분류 (total_scorer.py와 동일)
_APARTMENT_TYPES = frozenset({"아파트", "오피스텔", "주상복합", "연립", "빌라"})
_LAND_TYPES = frozenset({"토지", "임야", "전", "답", "대지"})

SCORER_VERSION = "v1.0"


def _interpolate(curve: list[tuple[int | float, float]], value: float) -> float:
    """선형 보간 — 범위 외 경계값 클램프"""
    if value <= curve[0][0]:
        return curve[0][1]
    if value >= curve[-1][0]:
        return curve[-1][1]
    for i in range(1, len(curve)):
        x0, y0 = curve[i - 1]
        x1, y1 = curve[i]
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return curve[-1][1]


def _calc_station_score(nearest_station_m: int | None) -> float:
    """역세권 점수 산출

    nearest_station_m=None: 역 없음 or 미취득 → 하한 10.0 반환
    """
    if nearest_station_m is None:
        return STATION_FLOOR
    return _interpolate(STATION_CURVE, nearest_station_m)


def _calc_amenity_score(amenity_count: int) -> float:
    """편의시설 점수 산출 (500m 내 마트+편의점+병원 합산 개수)"""
    return _interpolate(AMENITY_CURVE, float(amenity_count))


def _calc_school_score(nearest_school_m: int | None) -> float:
    """학군 점수 산출 (아파트 전용)

    nearest_school_m=None: 1500m 내 학교 없음 → 0점
    """
    if nearest_school_m is None:
        return 0.0
    return _interpolate(SCHOOL_CURVE, nearest_school_m)


def _calc_land_use_score(zones: list[str]) -> float:
    """용도지역 점수 산출 (토지 전용)

    LandUseInfo.zones 문자열 목록에서 키워드 우선 매칭.
    """
    if not zones:
        return DEFAULT_LAND_USE_SCORE
    zone_str = " ".join(zones)
    for keyword, score in LAND_USE_KEYWORD_SCORES:
        if keyword in zone_str:
            return score
    return DEFAULT_LAND_USE_SCORE


class LocationScorer:
    """입지 점수 산출기 (Phase 6)

    카카오 카테고리 검색 결과(LocationData)와 용도지역 정보(LandUseInfo)를
    바탕으로 역세권/편의시설/학군/용도지역 서브스코어를 산출하고
    물건 유형별 가중 합산으로 최종 입지 점수를 반환한다.
    """

    def score(
        self,
        case: AuctionCaseDetail,
        location_data: LocationData | None,
        land_use: LandUseInfo | None = None,
    ) -> LocationScoreResult | None:
        """입지 점수 산출

        Args:
            case: 경매 물건 상세 (property_type 참조)
            location_data: 카카오 카테고리 검색 결과. None이면 좌표 없음 → None 반환.
            land_use: 용도지역 정보 (토지 유형에서 사용)

        Returns:
            LocationScoreResult, 또는 location_data=None 시 None
        """
        if location_data is None:
            return None

        warnings: list[str] = []
        category = self._classify_property(case.property_type)

        # 서브스코어 산출
        station_score = _calc_station_score(location_data.nearest_station_m)
        amenity_score = _calc_amenity_score(location_data.amenity_count_500m)
        school_score = _calc_school_score(location_data.nearest_school_m)
        land_use_score = _calc_land_use_score(land_use.zones if land_use else [])

        sub_scores = LocationSubScores(
            station_score=round(station_score, 1),
            amenity_score=round(amenity_score, 1),
            school_score=round(school_score, 1),
            land_use_score=round(land_use_score, 1),
        )

        # 유형별 가중 합산
        weights = LOCATION_WEIGHTS.get(category, LOCATION_WEIGHTS[DEFAULT_CATEGORY])
        if category == "아파트":
            base_score = (
                station_score * weights["station"]
                + amenity_score * weights["amenity"]
                + school_score * weights["school"]
            )
        elif category == "꼬마빌딩":
            base_score = (
                station_score * weights["station"]
                + amenity_score * weights["amenity"]
            )
        else:  # 토지
            base_score = (
                station_score * weights["station"]
                + land_use_score * weights["land_use"]
            )
        base_score = round(base_score, 1)

        # 신뢰도 결정
        confidence, conf_multiplier = self._determine_confidence(
            category, location_data.categories_fetched
        )

        # 꼬마빌딩: max MEDIUM (유동인구/대로변 데이터 미확보로 과대평가 방지)
        if category == "꼬마빌딩" and confidence == "HIGH":
            confidence = "MEDIUM"
            conf_multiplier = 0.85
            warnings.append(
                "꼬마빌딩 입지 신뢰도: MEDIUM으로 제한 (유동인구/대로변 데이터 미확보)"
            )

        final_score = round(base_score * conf_multiplier, 1)
        final_score = max(0.0, min(100.0, final_score))

        return LocationScoreResult(
            score=final_score,
            base_score=base_score,
            sub_scores=sub_scores,
            confidence=confidence,
            confidence_multiplier=conf_multiplier,
            property_category=category,
            warnings=warnings,
            scorer_version=SCORER_VERSION,
        )

    @staticmethod
    def _classify_property(property_type: str) -> str:
        """물건 유형 → 카테고리 (아파트/꼬마빌딩/토지)"""
        if not property_type:
            return DEFAULT_CATEGORY
        for keyword in _APARTMENT_TYPES:
            if keyword in property_type:
                return "아파트"
        for keyword in _LAND_TYPES:
            if keyword in property_type:
                return "토지"
        return DEFAULT_CATEGORY

    @staticmethod
    def _determine_confidence(
        category: str,
        categories_fetched: list[str],
    ) -> tuple[str, float]:
        """API 성공 카테고리 수 기반 신뢰도 결정

        4개+ → HIGH, 2~3개 → MEDIUM, 1개 → LOW
        (꼬마빌딩 HIGH→MEDIUM 강등은 score() 호출 후 처리)
        """
        count = len(categories_fetched)
        if count >= 4:
            return "HIGH", 1.0
        if count >= 2:
            return "MEDIUM", 0.85
        return "LOW", 0.70
