"""CaseEnricher 단위 테스트

외부 API 호출을 mock하여 보강 로직을 검증한다.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.auction import AuctionCaseDetail, AuctionPropertyObject
from app.models.enriched_case import EnrichedCase
from app.services.enricher import (
    CaseEnricher,
    _calc_avg_price_per_m2,
    _parse_lot_number,
    _safe_float,
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
        "lot_number": "123-4",
        "area_m2": 84.0,
    }
    defaults.update(overrides)
    return AuctionCaseDetail(**defaults)


def _make_enricher(geo=None, public=None) -> CaseEnricher:
    """mock 클라이언트를 주입한 CaseEnricher 생성"""
    return CaseEnricher(
        geo_client=geo or MagicMock(),
        public_client=public or MagicMock(),
    )


# === TestGeocoding ===


class TestGeocoding:
    """주소 → 좌표 변환 테스트"""

    def test_geocode_success(self):
        """geocode 성공 시 coordinates 설정"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "127.0365", "y": "37.4994"}
        enricher = _make_enricher(geo=geo)

        result = enricher.enrich(_make_case())

        assert result.coordinates == {"x": "127.0365", "y": "37.4994"}
        geo.geocode.assert_called_once()

    def test_geocode_uses_property_object_address_first(self):
        """property_objects가 있으면 해당 주소 우선 사용"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "1", "y": "2"}
        enricher = _make_enricher(geo=geo)

        case = _make_case(
            property_objects=[
                AuctionPropertyObject(
                    sequence=1,
                    address="서울특별시 서초구 서초동 100",
                )
            ]
        )
        enricher.enrich(case)

        geo.geocode.assert_called_once_with("서울특별시 서초구 서초동 100")

    def test_geocode_fallback_to_case_address(self):
        """property_objects 없으면 case.address 사용"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "1", "y": "2"}
        enricher = _make_enricher(geo=geo)

        case = _make_case(property_objects=[])
        enricher.enrich(case)

        geo.geocode.assert_called_once_with("서울특별시 강남구 역삼동 123-4")

    def test_geocode_failure_returns_none(self):
        """geocode 실패 시 coordinates=None"""
        geo = MagicMock()
        geo.geocode.side_effect = Exception("API 오류")
        enricher = _make_enricher(geo=geo)

        result = enricher.enrich(_make_case())

        assert result.coordinates is None


# === TestLandUse ===


class TestLandUse:
    """좌표 → 용도지역 조회 테스트"""

    def test_land_use_normal(self):
        """일반 주거지역 정상 조회"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "127.0", "y": "37.5"}
        geo.fetch_land_use.return_value = [{"name": "제3종일반주거지역"}]
        enricher = _make_enricher(geo=geo)

        result = enricher.enrich(_make_case())

        assert result.land_use is not None
        assert "제3종일반주거지역" in result.land_use.zones
        assert result.land_use.is_greenbelt is False

    def test_land_use_greenbelt(self):
        """그린벨트 감지"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "127.0", "y": "37.5"}
        geo.fetch_land_use.return_value = [{"name": "개발제한구역"}]
        enricher = _make_enricher(geo=geo)

        result = enricher.enrich(_make_case())

        assert result.land_use is not None
        assert result.land_use.is_greenbelt is True

    def test_land_use_skipped_when_no_coordinates(self):
        """좌표 없으면 용도지역 조회 스킵"""
        geo = MagicMock()
        geo.geocode.return_value = None
        enricher = _make_enricher(geo=geo)

        result = enricher.enrich(_make_case())

        assert result.land_use is None
        geo.fetch_land_use.assert_not_called()

    def test_land_use_failure_returns_none(self):
        """용도지역 조회 실패 시 None"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "127.0", "y": "37.5"}
        geo.fetch_land_use.side_effect = Exception("API 오류")
        enricher = _make_enricher(geo=geo)

        result = enricher.enrich(_make_case())

        assert result.land_use is None


# === TestBuildingRegister ===


class TestBuildingRegister:
    """건축물대장 조회 테스트"""

    def test_building_normal(self):
        """건축물대장 정상 조회"""
        public = MagicMock()
        public.fetch_building_register.return_value = [
            {
                "mainPurpsCdNm": "공동주택",
                "strctCdNm": "철근콘크리트구조",
                "totArea": "120.5",
                "useAprDay": "20100315",
            }
        ]
        enricher = _make_enricher(public=public)

        result = enricher.enrich(_make_case())

        assert result.building is not None
        assert result.building.main_purpose == "공동주택"
        assert result.building.structure == "철근콘크리트구조"
        assert result.building.total_area == 120.5
        assert result.building.violation is False

    def test_building_violation_detected(self):
        """위반건축물 감지"""
        public = MagicMock()
        public.fetch_building_register.return_value = [
            {
                "mainPurpsCdNm": "근린생활시설",
                "etcStrct": "위반건축물",
                "totArea": "50",
            }
        ]
        enricher = _make_enricher(public=public)

        result = enricher.enrich(_make_case())

        assert result.building is not None
        assert result.building.violation is True

    def test_building_no_sigungu_match(self):
        """서울 외 지역이면 building=None (MVP 한계)"""
        public = MagicMock()
        enricher = _make_enricher(public=public)

        case = _make_case(address="경기도 수원시 팔달구 매산동 1-2")
        result = enricher.enrich(case)

        assert result.building is None
        public.fetch_building_register.assert_not_called()

    def test_building_no_lot_number(self):
        """지번 없으면 building=None"""
        public = MagicMock()
        enricher = _make_enricher(public=public)

        case = _make_case(lot_number="", property_objects=[])
        result = enricher.enrich(case)

        assert result.building is None

    def test_building_failure_returns_none(self):
        """건축물대장 조회 실패 시 None"""
        public = MagicMock()
        public.fetch_building_register.side_effect = Exception("API 오류")
        enricher = _make_enricher(public=public)

        result = enricher.enrich(_make_case())

        assert result.building is None


# === TestMarketPrice ===


class TestMarketPrice:
    """시세(실거래가) 조회 테스트"""

    def test_market_price_normal(self):
        """정상 조회 시 평균 단가 계산"""
        public = MagicMock()
        public.fetch_apt_trade.return_value = [
            {"dealAmount": "50,000", "excluUseAr": "84.99"},
            {"dealAmount": "52,000", "excluUseAr": "84.99"},
        ]
        enricher = _make_enricher(public=public)

        result = enricher.enrich(_make_case())

        assert result.market_price is not None
        assert result.market_price.avg_price_per_m2 is not None
        assert result.market_price.avg_price_per_m2 > 0
        assert result.market_price.trade_count == 2

    def test_market_price_no_trades(self):
        """거래 없으면 trade_count=0, avg=None"""
        public = MagicMock()
        public.fetch_apt_trade.return_value = []
        enricher = _make_enricher(public=public)

        result = enricher.enrich(_make_case())

        assert result.market_price is not None
        assert result.market_price.trade_count == 0
        assert result.market_price.avg_price_per_m2 is None

    def test_market_price_no_lawd_cd(self):
        """법정동코드 추출 불가 시 market_price=None"""
        public = MagicMock()
        enricher = _make_enricher(public=public)

        case = _make_case(address="경기도 수원시 팔달구 매산동 1-2")
        result = enricher.enrich(case)

        assert result.market_price is None
        public.fetch_apt_trade.assert_not_called()

    def test_market_price_failure_returns_none(self):
        """시세 조회 실패 시 None"""
        public = MagicMock()
        public.fetch_apt_trade.side_effect = Exception("API 오류")
        enricher = _make_enricher(public=public)

        result = enricher.enrich(_make_case())

        assert result.market_price is None


# === TestEnrichIntegration ===


class TestEnrichIntegration:
    """보강 통합 테스트"""

    def test_full_enrichment(self):
        """모든 API 성공 시 전체 보강 완료"""
        geo = MagicMock()
        geo.geocode.return_value = {"x": "127.0", "y": "37.5"}
        geo.fetch_land_use.return_value = [{"name": "제1종일반주거지역"}]

        public = MagicMock()
        public.fetch_building_register.return_value = [
            {"mainPurpsCdNm": "공동주택", "totArea": "84.0"}
        ]
        public.fetch_apt_trade.return_value = [
            {"dealAmount": "60,000", "excluUseAr": "84.99"}
        ]

        enricher = _make_enricher(geo=geo, public=public)
        result = enricher.enrich(_make_case())

        assert result.coordinates is not None
        assert result.land_use is not None
        assert result.building is not None
        assert result.market_price is not None
        assert result.case.case_number == "2025타경10001"

    def test_all_apis_fail_still_returns_enriched_case(self):
        """모든 API 실패해도 EnrichedCase 반환 (fail-open)"""
        geo = MagicMock()
        geo.geocode.side_effect = Exception("geocode 실패")

        public = MagicMock()
        public.fetch_building_register.side_effect = Exception("building 실패")
        public.fetch_apt_trade.side_effect = Exception("market 실패")

        enricher = _make_enricher(geo=geo, public=public)
        result = enricher.enrich(_make_case())

        assert isinstance(result, EnrichedCase)
        assert result.case.case_number == "2025타경10001"
        assert result.coordinates is None
        assert result.land_use is None
        assert result.building is None
        assert result.market_price is None

    def test_enrich_batch(self):
        """배치 보강"""
        geo = MagicMock()
        geo.geocode.return_value = None
        public = MagicMock()
        public.fetch_building_register.return_value = []
        public.fetch_apt_trade.return_value = []

        enricher = _make_enricher(geo=geo, public=public)

        cases = [_make_case(case_number=f"2025타경1000{i}") for i in range(3)]
        with patch("app.services.enricher.time.sleep"):
            results = enricher.enrich_batch(cases, delay=0)

        assert len(results) == 3
        assert all(isinstance(r, EnrichedCase) for r in results)


# === TestHelpers ===


class TestHelpers:
    """유틸리티 함수 테스트"""

    # _parse_lot_number
    def test_parse_lot_simple(self):
        assert _parse_lot_number("156") == ("0156", "0000")

    def test_parse_lot_with_sub(self):
        assert _parse_lot_number("1086-12") == ("1086", "0012")

    def test_parse_lot_already_padded(self):
        assert _parse_lot_number("0001-0001") == ("0001", "0001")

    def test_parse_lot_empty(self):
        assert _parse_lot_number("") == ("", "")

    # _calc_avg_price_per_m2
    def test_calc_avg_normal(self):
        trades = [
            {"dealAmount": "50,000", "excluUseAr": "84.99"},
            {"dealAmount": "52,000", "excluUseAr": "84.99"},
        ]
        avg = _calc_avg_price_per_m2(trades)
        assert avg is not None
        # 50000만원=5억, 52000만원=5.2억 → 평균 5.1억원 / 84.99㎡ ≈ 600만/㎡
        assert 5_000_000 < avg < 7_000_000  # 대략 600만/㎡

    def test_calc_avg_empty_trades(self):
        assert _calc_avg_price_per_m2([]) is None

    def test_calc_avg_invalid_data(self):
        trades = [{"dealAmount": "", "excluUseAr": ""}]
        assert _calc_avg_price_per_m2(trades) is None

    # _safe_float
    def test_safe_float_normal(self):
        assert _safe_float("123.45") == 123.45

    def test_safe_float_comma(self):
        assert _safe_float("1,234.5") == 1234.5

    def test_safe_float_empty(self):
        assert _safe_float("") is None

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_invalid(self):
        assert _safe_float("abc") is None
