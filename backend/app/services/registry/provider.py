"""등기부등본 조회 제공자 인터페이스

다양한 등기부등본 조회 경로(CODEF, Tilko, 수동 PDF 등)를
통일된 인터페이스로 추상화한다.
MVP에서는 CodefRegistryProvider만 구현.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.models.registry import RegistryDocument


class RegistryProvider(ABC):
    """등기부등본 조회 제공자 추상 클래스"""

    @abstractmethod
    def fetch_registry(
        self,
        unique_no: str,
        realty_type: str = "3",
    ) -> RegistryDocument:
        """고유번호로 등기부등본 조회 → RegistryDocument 반환

        Args:
            unique_no: 부동산 고유번호 (14자리)
            realty_type: 부동산 유형 (1: 토지, 2: 건물, 3: 집합건물)

        Returns:
            RegistryDocument
        """
        ...

    @abstractmethod
    def search_by_address(
        self,
        sido: str,
        sigungu: str,
        dong: str = "",
        ho: str = "",
        building_name: str = "",
        addr_lot_number: str = "",
    ) -> list[dict[str, Any]]:
        """주소 검색 → 고유번호 목록 반환

        Args:
            sido: 시/도 (예: "서울특별시")
            sigungu: 시/군/구 (예: "강남구")
            dong: 동/호 (예: "501")
            ho: 호 (예: "804")
            building_name: 건물명 (예: "○○아파트")
            addr_lot_number: 지번 (예: "123-45")

        Returns:
            고유번호 정보 목록
        """
        ...


class RegistryTwoWayAuthRequired(Exception):
    """CODEF 추가인증(2-Way) 요구 시 발생하는 예외"""

    def __init__(
        self,
        jti: str = "",
        two_way_timestamp: str = "",
        message: str = "추가인증이 필요합니다",
    ) -> None:
        self.jti = jti
        self.two_way_timestamp = two_way_timestamp
        super().__init__(message)
