"""CODEF 검색 결과 매칭 테스트"""

import pytest

from app.services.address_parser import CodefAddressParams
from app.services.registry.matcher import (
    MatchResult,
    NoMatchError,
    RegistryMatcher,
)


@pytest.fixture()
def matcher() -> RegistryMatcher:
    return RegistryMatcher()


@pytest.fixture()
def search_results() -> list[dict]:
    """복수 검색 결과 (실제 CODEF 응답 형태)"""
    return [
        {
            "commUniqueNo": "11460000012345",
            "commAddrLotNumber": "서울특별시 강남구 역삼동 123-45",
            "resType": "집합건물",
            "resUserNm": "홍OO",
            "resState": "현행",
        },
        {
            "commUniqueNo": "11460000012346",
            "commAddrLotNumber": "서울특별시 강남구 역삼동 123-46",
            "resType": "집합건물",
            "resUserNm": "김OO",
            "resState": "현행",
        },
        {
            "commUniqueNo": "11460000099999",
            "commAddrLotNumber": "서울특별시 강남구 역삼동 456-7 ○○빌딩",
            "resType": "건물",
            "resUserNm": "이OO",
            "resState": "현행",
        },
    ]


# ============================================================
# TestLotExactMatch — 지번 완전 일치
# ============================================================


class TestLotExactMatch:
    """지번 완전 일치 매칭"""

    def test_exact_lot_match(
        self, matcher: RegistryMatcher, search_results: list[dict]
    ) -> None:
        """동 + 지번 일치 → confidence 1.0"""
        target = CodefAddressParams(
            sido="서울특별시", sigungu="강남구", dong="역삼동",
            lot_number="123-45",
        )
        result = matcher.match(search_results, target)
        assert result.unique_no == "11460000012345"
        assert result.confidence == 1.0
        assert result.match_method == "lot_exact"

    def test_second_lot_match(
        self, matcher: RegistryMatcher, search_results: list[dict]
    ) -> None:
        """두 번째 결과와 일치"""
        target = CodefAddressParams(
            sido="서울특별시", sigungu="강남구", dong="역삼동",
            lot_number="123-46",
        )
        result = matcher.match(search_results, target)
        assert result.unique_no == "11460000012346"
        assert result.confidence == 1.0

    def test_san_lot_match(self, matcher: RegistryMatcher) -> None:
        """산번지 일치"""
        results = [
            {
                "commUniqueNo": "AAA",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 산123-4",
            }
        ]
        target = CodefAddressParams(dong="역삼동", lot_number="산123-4")
        result = matcher.match(results, target)
        assert result.unique_no == "AAA"
        assert result.confidence == 1.0


# ============================================================
# TestBuildingNameMatch — 건물명 매칭
# ============================================================


class TestBuildingNameMatch:
    """건물명 포함 매칭"""

    def test_building_name_match(
        self, matcher: RegistryMatcher, search_results: list[dict]
    ) -> None:
        """건물명 포함 → confidence 0.8~0.9"""
        target = CodefAddressParams(
            sido="서울특별시", sigungu="강남구", dong="역삼동",
            building_name="○○빌딩",
        )
        result = matcher.match(search_results, target)
        assert result.unique_no == "11460000099999"
        assert result.confidence >= 0.8
        assert result.match_method == "building_name"

    def test_building_with_dong_higher_confidence(
        self, matcher: RegistryMatcher
    ) -> None:
        """동 + 건물명 일치 → 동만 일치보다 높은 confidence"""
        results = [
            {
                "commUniqueNo": "BBB",
                "commAddrLotNumber": "서울특별시 강남구 삼성동 아이파크타워",
            }
        ]
        target = CodefAddressParams(dong="삼성동", building_name="아이파크타워")
        result = matcher.match(results, target)
        assert result.confidence == 0.9


# ============================================================
# TestLotPrefixMatch — 지번 부분 일치
# ============================================================


class TestLotPrefixMatch:
    """지번 본번만 일치"""

    def test_lot_prefix(self, matcher: RegistryMatcher) -> None:
        """123-45에서 123만 일치"""
        results = [
            {
                "commUniqueNo": "CCC",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 123",
            }
        ]
        target = CodefAddressParams(dong="역삼동", lot_number="123-45")
        result = matcher.match(results, target)
        assert result.unique_no == "CCC"
        assert result.confidence == 0.6
        assert result.match_method == "lot_prefix"


# ============================================================
# TestDongOnlyMatch — 동만 일치
# ============================================================


class TestDongOnlyMatch:
    """동만 일치 (weakest)"""

    def test_dong_only(self, matcher: RegistryMatcher) -> None:
        """동만 일치 → confidence 0.3"""
        results = [
            {
                "commUniqueNo": "DDD",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 999-99",
            }
        ]
        target = CodefAddressParams(dong="역삼동", lot_number="777-7")
        result = matcher.match(results, target)
        assert result.unique_no == "DDD"
        assert result.confidence == 0.3
        assert result.match_method == "dong_only"


# ============================================================
# TestNoMatch — 매칭 실패
# ============================================================


class TestNoMatch:
    """매칭 실패"""

    def test_empty_results(self, matcher: RegistryMatcher) -> None:
        """빈 검색 결과"""
        target = CodefAddressParams(dong="역삼동")
        with pytest.raises(NoMatchError, match="비어있습니다"):
            matcher.match([], target)

    def test_no_dong_match(self, matcher: RegistryMatcher) -> None:
        """동이 전혀 일치하지 않음"""
        results = [
            {
                "commUniqueNo": "EEE",
                "commAddrLotNumber": "서울특별시 서초구 서초동 100",
            }
        ]
        target = CodefAddressParams(dong="역삼동", lot_number="123-4")
        with pytest.raises(NoMatchError, match="매칭 실패"):
            matcher.match(results, target)


# ============================================================
# TestBestSelection — 최선 후보 선택
# ============================================================


class TestBestSelection:
    """여러 후보 중 최선 선택"""

    def test_lot_exact_beats_building_name(
        self, matcher: RegistryMatcher
    ) -> None:
        """지번 일치 > 건물명 일치"""
        results = [
            {
                "commUniqueNo": "BUILDING",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 999 테스트빌딩",
            },
            {
                "commUniqueNo": "LOT",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 123-45",
            },
        ]
        target = CodefAddressParams(
            dong="역삼동", lot_number="123-45", building_name="테스트빌딩"
        )
        result = matcher.match(results, target)
        assert result.unique_no == "LOT"
        assert result.confidence == 1.0

    def test_building_name_beats_dong_only(
        self, matcher: RegistryMatcher
    ) -> None:
        """건물명 일치 > 동만 일치"""
        results = [
            {
                "commUniqueNo": "DONG",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 999",
            },
            {
                "commUniqueNo": "BLDG",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 테스트빌딩",
            },
        ]
        target = CodefAddressParams(
            dong="역삼동", building_name="테스트빌딩"
        )
        result = matcher.match(results, target)
        assert result.unique_no == "BLDG"
        assert result.confidence >= 0.8


# ============================================================
# TestMatchResult — 결과 속성
# ============================================================


class TestMatchResult:
    """MatchResult 속성 검증"""

    def test_matched_address_preserved(
        self, matcher: RegistryMatcher, search_results: list[dict]
    ) -> None:
        """매칭된 주소가 보존됨"""
        target = CodefAddressParams(dong="역삼동", lot_number="123-45")
        result = matcher.match(search_results, target)
        assert result.matched_address == "서울특별시 강남구 역삼동 123-45"

    def test_confidence_capped_at_1(self, matcher: RegistryMatcher) -> None:
        """confidence는 1.0을 넘지 않음"""
        results = [
            {
                "commUniqueNo": "X",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 123-45",
            }
        ]
        target = CodefAddressParams(dong="역삼동", lot_number="123-45")
        result = matcher.match(results, target)
        assert result.confidence <= 1.0
