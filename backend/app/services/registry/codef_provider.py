"""CODEF 등기부등본 조회 제공자

CodefClient의 토큰 관리/재시도를 재사용하면서,
등기부등본 전용 엔드포인트를 호출하고 CodefRegistryMapper로 매핑한다.

CODEF 등기부등본 API (API 문서 기준):
  - password: 인터넷등기소 비회원 로그인 비밀번호 (숫자 4자리) → RSA 암호화
  - ePrepayNo: 선불전자지급수단번호 (12자리) → 평문
  - ePrepayPass: 선불전자지급수단 비밀번호 → 평문 (RSA 아님!)
  - inquiryType=0: 고유번호로 찾기 → addr_* 파라미터 불필요
  - 주소검색 API: data 필드가 리스트로 반환 (dict가 아님)
"""

import base64
import logging
from typing import Any

from app.config import settings
from app.models.registry import RegistryDocument
from app.services.crawler.codef_client import CodefApiError, CodefClient
from app.services.registry.codef_mapper import CodefRegistryMapper
from app.services.registry.provider import (
    RegistryProvider,
    RegistryTwoWayAuthRequired,
)

logger = logging.getLogger(__name__)

# 유효한 전화번호 시작 번호 (CODEF API 문서)
VALID_PHONE_PREFIXES = (
    "010", "011", "016", "017", "018", "019",
    "070", "02", "031", "032", "033", "041", "042", "043",
    "0502", "0505", "051", "052", "053", "054", "055",
    "061", "062", "063", "064",
)


class CodefRegistryProvider(RegistryProvider):
    """CODEF API를 통한 등기부등본 조회

    CodefClient._request()를 직접 호출하여 토큰 관리를 재사용한다.
    응답은 CodefRegistryMapper로 RegistryDocument로 변환한다.

    inquiryType=0 (고유번호로 찾기) 사용:
      - 주소 파라미터(addr_*) 불필요
      - 추가인증(2-Way) 불필요
      - uniqueNo만으로 바로 열람
    """

    def __init__(
        self,
        codef_client: CodefClient | None = None,
        mapper: CodefRegistryMapper | None = None,
    ) -> None:
        self._client = codef_client or CodefClient()
        self._mapper = mapper or CodefRegistryMapper()

    def fetch_registry(
        self,
        unique_no: str,
        realty_type: str = "3",
        **kwargs: Any,
    ) -> RegistryDocument:
        """고유번호로 등기부등본 조회 → RegistryDocument 반환

        inquiryType=0 사용으로 주소 파라미터 불필요.
        기존 호출자 호환성을 위해 addr_* kwargs는 받되 무시한다.

        Args:
            unique_no: 부동산 고유번호 (14자리, 하이픈 자동 제거)
            realty_type: 부동산 유형 (1: 토지, 2: 건물, 3: 집합건물)
            **kwargs: 기존 호환용 (addr_sido, addr_dong 등 — 무시됨)

        Returns:
            RegistryDocument (source="codef")
        """
        # 하이픈 제거 (14자리 숫자만)
        clean_unique_no = unique_no.replace("-", "")

        payload = self._build_registry_payload(clean_unique_no, realty_type)

        logger.info("CODEF 등기부등본 조회: unique_no=%s (inquiryType=0)", clean_unique_no)
        data = self._client._request(
            settings.CODEF_REGISTRY_ENDPOINT, payload
        )

        # 추가인증(2-Way) 요구 감지
        self._check_two_way_auth(data)

        return self._mapper.map_response(data)

    def _build_registry_payload(self, unique_no: str, realty_type: str) -> dict:
        """CODEF 부동산등기부등본 열람 요청 payload 생성

        API 문서: CODEF_API_개발가이드_부동산등기부등본_열람발급.pdf
        inquiryType=0 (고유번호로 찾기) 사용 → 주소 파라미터 불필요, 추가인증 불필요
        """
        password = settings.IROS_PASSWORD
        encrypted_password = self._encrypt_rsa(password) if password else ""

        return {
            "organization": "0002",
            "inquiryType": "0",                              # 고유번호로 찾기
            "uniqueNo": unique_no,
            "realtyType": realty_type,
            "phoneNo": settings.IROS_PHONE_NO,
            "password": encrypted_password,                  # RSA 암호화 (4자리 비밀번호)
            "jointMortgageJeonseYN": "1",
            "tradingYN": "1",
            "issueType": "1",                                # 열람 (발급보다 저렴)
            "registerSummaryYN": "1",
            "recordStatus": "0",
            "warningSkipYN": "1",                            # 경고 무시 (자동화)
            "ePrepayNo": settings.IROS_EPREPAY_NO,           # 평문
            "ePrepayPass": settings.IROS_EPREPAY_PASS,       # 평문 (RSA 아님!)
        }

    def search_by_address(
        self,
        sido: str,
        sigungu: str = "",
        addr_dong: str = "",
        addr_lot_number: str = "",
        building_name: str = "",
        dong: str = "",
        ho: str = "",
        search_gbn: str = "1",
        realty_type: str = "1",
        addr_road_name: str = "",
        addr_building_number: str = "",
        address: str = "",
    ) -> list[dict[str, Any]]:
        """주소 검색 → 고유번호 목록 반환

        Args:
            sido: 시/도 (예: "서울특별시")
            sigungu: 시/군/구 (예: "강남구")
            addr_dong: 법정동 (예: "역삼동")
            addr_lot_number: 지번 (예: "123-45")
            building_name: 건물명 (예: "○○아파트")
            dong: 건물 동 (예: "1")
            ho: 호 (예: "804")
            search_gbn: 검색구분 (기본값 "1")
            realty_type: 부동산유형 (1: 토지, 2: 건물, 3: 집합건물)
            addr_road_name: 도로명 (예: "테헤란로")
            addr_building_number: 건물번호 (예: "406")
            address: 주소 검색어 (예: "역삼동 아이파크")

        Returns:
            고유번호 정보 목록 (commUniqueNo, commAddrLotNumber, resType 등)
        """
        payload = {
            "organization": "0002",
            "searchGbn": search_gbn,
            "uniqueNo": "",
            "realtyType": realty_type,
            "addrSido": sido,
            "addrSigungu": sigungu,
            "addrDong": addr_dong,
            "addrLotNumber": addr_lot_number,
            "addrRoadName": addr_road_name,
            "addrBuildingNumber": addr_building_number,
            "address": address,
            "buildingName": building_name,
            "dong": dong,
            "ho": ho,
            "inputSelect": "0",
            "recordStatus": "",
            "electronicClosedYN": "",
        }

        logger.info(
            "CODEF 주소검색: %s %s %s", sido, addr_dong or sigungu, building_name or addr_lot_number
        )

        try:
            data = self._client._request(
                "/v1/kr/public/ck/real-estate/address", payload
            )
        except CodefApiError as e:
            if e.code == "CF-13007" and realty_type != "3":
                # CF-13007: 결과 과다 → realtyType=3(집합건물)으로 재시도
                logger.warning(
                    "CODEF CF-13007 결과 과다, realtyType=3으로 재시도: %s %s",
                    addr_dong or sigungu, building_name or addr_lot_number,
                )
                payload["realtyType"] = "3"
                data = self._client._request(
                    "/v1/kr/public/ck/real-estate/address", payload
                )
            else:
                raise

        # CODEF 실제 응답: data가 리스트로 반환됨 (성공 시)
        # dict인 경우 resSearchList 키 확인 (호환성)
        if isinstance(data, list):
            return data
        return data.get("resSearchList", [])

    @staticmethod
    def validate_phone_no(phone_no: str | None = None) -> bool:
        """전화번호 유효성 검사 (CODEF API 문서 기준)"""
        no = phone_no or settings.IROS_PHONE_NO
        if not no:
            return False
        return any(no.startswith(p) for p in VALID_PHONE_PREFIXES)

    @staticmethod
    def validate_eprepay_no() -> bool:
        """선불전자지급수단번호 유효성 검사 (12자리)"""
        no = settings.IROS_EPREPAY_NO
        if not no:
            return False
        if len(no) != 12:
            logger.warning(
                "선불전자지급수단번호가 12자리가 아닙니다 (%d자리). "
                "전자민원캐시 번호를 확인하세요. (https://minwon.cashgate.co.kr)",
                len(no),
            )
            return False
        return True

    @staticmethod
    def _encrypt_rsa(plaintext: str) -> str:
        """CODEF RSA 공개키 암호화 (PKCS1_v1_5 + Base64)

        CODEF에서 발급한 공개키로 평문을 암호화하여 Base64 문자열로 반환.
        공식 SDK(codef-python RegisterAccount.py)와 동일한 구현.

        Args:
            plaintext: 암호화할 평문

        Returns:
            Base64 인코딩된 암호문

        Raises:
            RuntimeError: 공개키 미설정 또는 pycryptodome 미설치
        """
        public_key = settings.CODEF_PUBLIC_KEY
        if not public_key:
            raise RuntimeError(
                "CODEF_PUBLIC_KEY가 설정되지 않았습니다. "
                ".env 파일에 CODEF 공개키를 설정하세요."
            )

        try:
            from Crypto.Cipher import PKCS1_v1_5 as Cipher_PKCS1_v1_5
            from Crypto.PublicKey import RSA
        except ImportError:
            raise RuntimeError(
                "pycryptodome이 필요합니다: pip install pycryptodome"
            )

        key_der = base64.b64decode(public_key)
        key_pub = RSA.import_key(key_der)
        cipher = Cipher_PKCS1_v1_5.new(key_pub)
        cipher_text = cipher.encrypt(plaintext.encode("utf-8"))
        return base64.b64encode(cipher_text).decode("utf-8")

    @staticmethod
    def _check_two_way_auth(data: dict) -> None:
        """CODEF 추가인증(2-Way) 요구 감지"""
        if isinstance(data, dict) and data.get("continue2Way"):
            raise RegistryTwoWayAuthRequired(
                jti=data.get("jti", ""),
                two_way_timestamp=data.get("twoWayTimestamp", ""),
            )
