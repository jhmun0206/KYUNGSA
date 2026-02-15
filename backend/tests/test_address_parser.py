"""주소 파싱 유틸리티 테스트

Step 1에서 수집한 실제 주소 샘플(docs/address_samples.md) 기반.
"""

import pytest

from app.services.address_parser import (
    AddressParseError,
    CodefAddressParams,
    extract_codef_params,
    parse_auction_address,
)


# ============================================================
# TestRoadNameAddress — 도로명 주소 (detail API)
# ============================================================


class TestRoadNameAddress:
    """도로명 주소 파싱: '{시도} {시군구} {도로명} {번호} {상세} ({동},{건물명})'"""

    def test_basic_road_address(self) -> None:
        """기본 도로명 주소"""
        result = parse_auction_address(
            "서울특별시 종로구 새문안로5가길 28 지1층비109호 (적선동,광화문플래티넘)"
        )
        assert result.sido == "서울특별시"
        assert result.sigungu == "종로구"
        assert result.dong == "적선동"
        assert result.road_name == "새문안로5가길"
        assert result.building_number == "28"
        assert result.building_name == "광화문플래티넘"

    def test_floor_unit_extraction(self) -> None:
        """층/호 상세 추출"""
        result = parse_auction_address(
            "서울특별시 관악구 남현7길 51 6층602호 (남현동,한샘타운)"
        )
        assert result.detail == "6층602호"

    def test_basement_unit(self) -> None:
        """지하층 상세"""
        result = parse_auction_address(
            "서울특별시 관악구 남현6길 13 지1층비101호 (남현동,한샘빌라)"
        )
        assert result.sido == "서울특별시"
        assert result.sigungu == "관악구"
        assert result.dong == "남현동"
        assert result.road_name == "남현6길"
        assert result.building_number == "13"
        assert result.building_name == "한샘빌라"

    def test_another_unit(self) -> None:
        """다른 층/호"""
        result = parse_auction_address(
            "서울특별시 관악구 남현6길 13 5층502호 (남현동,한샘빌라)"
        )
        assert result.dong == "남현동"
        assert result.building_name == "한샘빌라"
        assert result.detail == "5층502호"

    def test_dong_only_paren(self) -> None:
        """괄호에 동만 있는 경우"""
        result = parse_auction_address(
            "서울특별시 강남구 테헤란로 123 (역삼동)"
        )
        assert result.dong == "역삼동"
        assert result.building_name == ""

    def test_address_text_for_road(self) -> None:
        """도로명 주소의 address_text 생성"""
        result = parse_auction_address(
            "서울특별시 종로구 새문안로5가길 28 지1층비109호 (적선동,광화문플래티넘)"
        )
        assert "적선동" in result.address_text
        assert "광화문플래티넘" in result.address_text


# ============================================================
# TestLotNumberAddress — 지번 주소 (list API / test fixture)
# ============================================================


class TestLotNumberAddress:
    """지번 주소 파싱: '{시도} {시군구} {동} {지번} {건물명}'"""

    def test_basic_lot_address(self) -> None:
        """기본 지번 주소"""
        result = parse_auction_address("서울특별시 강남구 역삼동 123-4")
        assert result.sido == "서울특별시"
        assert result.sigungu == "강남구"
        assert result.dong == "역삼동"
        assert result.lot_number == "123-4"

    def test_lot_with_building_name(self) -> None:
        """지번 + 건물명"""
        result = parse_auction_address(
            "서울특별시 강남구 역삼동 123-45 ○○아파트"
        )
        assert result.dong == "역삼동"
        assert result.lot_number == "123-45"
        assert result.building_name == "○○아파트"

    def test_lot_with_bracket_detail(self) -> None:
        """대괄호 건물 상세 (제거됨)"""
        result = parse_auction_address(
            "서울 강남구 역삼동 123-4 [건물 5층]"
        )
        assert result.sido == "서울특별시"
        assert result.dong == "역삼동"
        assert result.lot_number == "123-4"
        # 대괄호 상세는 건물명이 아님
        assert result.building_name == ""

    def test_lot_with_building_type(self) -> None:
        """지번 + 건물 용도"""
        result = parse_auction_address(
            "서울 서초구 서초동 456-7 다가구주택"
        )
        assert result.sido == "서울특별시"
        assert result.sigungu == "서초구"
        assert result.dong == "서초동"
        assert result.lot_number == "456-7"
        assert result.building_name == "다가구주택"

    def test_lot_without_sub_number(self) -> None:
        """부번 없는 지번"""
        result = parse_auction_address("서울특별시 종로구 적선동 156")
        assert result.dong == "적선동"
        assert result.lot_number == "156"

    def test_address_text_for_lot(self) -> None:
        """지번 주소의 address_text 생성"""
        result = parse_auction_address("서울특별시 강남구 역삼동 123-4")
        assert "역삼동" in result.address_text


# ============================================================
# TestSidoNormalization — 시도명 정규화
# ============================================================


class TestSidoNormalization:
    """시도 약칭 → 정식명칭"""

    def test_seoul_short(self) -> None:
        result = parse_auction_address("서울 강남구 역삼동 123")
        assert result.sido == "서울특별시"

    def test_seoul_full(self) -> None:
        result = parse_auction_address("서울특별시 강남구 역삼동 123")
        assert result.sido == "서울특별시"

    def test_busan_short(self) -> None:
        result = parse_auction_address("부산 해운대구 우동 123")
        assert result.sido == "부산광역시"

    def test_gyeonggi_short(self) -> None:
        result = parse_auction_address("경기 수원시 영통구 매탄동 123")
        assert result.sido == "경기도"

    def test_sejong(self) -> None:
        """세종시: 시군구 없음"""
        result = parse_auction_address("세종특별자치시 한솔동 123")
        assert result.sido == "세종특별자치시"
        assert result.sigungu == ""
        assert result.dong == "한솔동"

    def test_jeju(self) -> None:
        result = parse_auction_address("제주 제주시 이도동 123")
        assert result.sido == "제주특별자치도"
        assert result.sigungu == "제주시"


# ============================================================
# TestEdgeCases — 엣지 케이스
# ============================================================


class TestEdgeCases:
    """예외/엣지 케이스"""

    def test_empty_address_raises(self) -> None:
        with pytest.raises(AddressParseError, match="빈 주소"):
            parse_auction_address("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(AddressParseError, match="빈 주소"):
            parse_auction_address("   ")

    def test_unknown_sido_raises(self) -> None:
        with pytest.raises(AddressParseError, match="시도 인식 불가"):
            parse_auction_address("알수없는지역 강남구 역삼동 123")

    def test_no_sigungu_warns(self) -> None:
        """시군구 없이 동만 있는 경우 (세종시 외)"""
        result = parse_auction_address("서울특별시 역삼동 123-4")
        # 역삼동은 sigungu 아님 → warnings에 기록
        assert len(result.warnings) > 0

    def test_san_lot_number(self) -> None:
        """산번지"""
        result = parse_auction_address("서울특별시 강남구 역삼동 산123-4")
        assert result.lot_number == "산123-4"

    def test_si_gu_structure(self) -> None:
        """시+구 구조: 수원시 영통구"""
        result = parse_auction_address("경기 수원시 영통구 매탄동 123")
        # "수원시"는 시로 끝남 → sigungu로 인식
        assert result.sigungu == "수원시"
        # "영통구"는 남은 토큰에서 동으로 인식되지 않음 (구로 끝남)
        # 이 패턴은 향후 개선 필요할 수 있음


# ============================================================
# TestExtractCodefParams — 보충 정보 활용
# ============================================================


class TestExtractCodefParams:
    """extract_codef_params: property_objects 보충"""

    def test_lot_number_supplement(self) -> None:
        """lot_number 보충"""
        result = extract_codef_params(
            address="서울특별시 종로구 새문안로5가길 28 (적선동,광화문플래티넘)",
            lot_number="156",
        )
        assert result.lot_number == "156"

    def test_building_name_supplement(self) -> None:
        """building_name 보충"""
        result = extract_codef_params(
            address="서울특별시 강남구 테헤란로 123 (역삼동)",
            building_name="○○타워",
        )
        assert result.building_name == "○○타워"
        assert "○○타워" in result.address_text

    def test_no_override_existing(self) -> None:
        """이미 파싱된 값은 덮어쓰지 않음"""
        result = extract_codef_params(
            address="서울특별시 강남구 역삼동 123-4",
            lot_number="999",
        )
        # 파싱에서 이미 123-4 추출됨 → 유지
        assert result.lot_number == "123-4"

    def test_address_text_updated_with_supplement(self) -> None:
        """보충 후 address_text 갱신"""
        result = extract_codef_params(
            address="서울특별시 종로구 새문안로5가길 28 (적선동)",
            building_name="광화문플래티넘",
        )
        assert "적선동" in result.address_text
        assert "광화문플래티넘" in result.address_text

    def test_full_case_detail_scenario(self) -> None:
        """실제 AuctionCaseDetail 시나리오 시뮬레이션"""
        result = extract_codef_params(
            address="서울특별시 종로구 새문안로5가길 28 지1층비109호 (적선동,광화문플래티넘)",
            lot_number="156",
            building_name="광화문플래티넘",
        )
        assert result.sido == "서울특별시"
        assert result.sigungu == "종로구"
        assert result.dong == "적선동"
        assert result.lot_number == "156"
        assert result.road_name == "새문안로5가길"
        assert result.building_number == "28"
        assert result.building_name == "광화문플래티넘"
