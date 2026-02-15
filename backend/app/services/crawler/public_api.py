"""공공 데이터 API 클라이언트 (무료, 1단 수집)

data.go.kr 공공데이터포털 API 연동.
- 아파트 매매 실거래가
- 아파트 전월세 실거래가
- 상업업무용 매매 실거래가
- 건축물대장 기본개요
- 개별공시지가
※ API 키: PUBLIC_DATA_API_KEY 환경변수로 관리
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# data.go.kr 엔드포인트 (apis.data.go.kr 통합 게이트웨이)
ENDPOINTS = {
    "apt_trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "apt_rent": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    "commercial_trade": "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
    "building_register": "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo",
    "land_price": "https://apis.data.go.kr/1611000/nsdi/IndvdLandPriceService/attr/getIndvdLandPriceAttr",
}


class PublicDataClient:
    """공공데이터포털 API 클라이언트

    모든 메서드는 data.go.kr 엔드포인트 호출 후 XML/JSON 파싱하여 반환.
    """

    def __init__(self) -> None:
        self._api_key = settings.PUBLIC_DATA_API_KEY

    def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """공통 GET 요청"""
        params["serviceKey"] = self._api_key
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        return response

    @staticmethod
    def _parse_xml_items(xml_text: str) -> list[dict[str, str]]:
        """XML 응답에서 item 목록 추출"""
        root = ET.fromstring(xml_text)
        items = root.findall(".//item")
        results = []
        for item in items:
            row = {}
            for child in item:
                row[child.tag] = (child.text or "").strip()
            results.append(row)
        return results

    # === 아파트 매매 실거래가 ===

    def fetch_apt_trade(self, lawd_cd: str, deal_ymd: str) -> list[dict[str, str]]:
        """아파트 매매 실거래가 조회

        Args:
            lawd_cd: 법정동코드 앞 5자리 (예: "11680" = 강남구)
            deal_ymd: 계약년월 (예: "202601")

        Returns:
            거래 목록 [{거래금액, 법정동, 아파트, 전용면적, ...}, ...]
        """
        params = {"LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd, "numOfRows": "100", "pageNo": "1"}
        logger.info("아파트 매매 실거래가 조회: %s / %s", lawd_cd, deal_ymd)
        response = self._get(ENDPOINTS["apt_trade"], params)
        return self._parse_xml_items(response.text)

    # === 아파트 전월세 실거래가 ===

    def fetch_apt_rent(self, lawd_cd: str, deal_ymd: str) -> list[dict[str, str]]:
        """아파트 전월세 실거래가 조회

        Args:
            lawd_cd: 법정동코드 앞 5자리
            deal_ymd: 계약년월

        Returns:
            전월세 거래 목록
        """
        params = {"LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd, "numOfRows": "100", "pageNo": "1"}
        logger.info("아파트 전월세 실거래가 조회: %s / %s", lawd_cd, deal_ymd)
        response = self._get(ENDPOINTS["apt_rent"], params)
        return self._parse_xml_items(response.text)

    # === 상업업무용 매매 실거래가 ===

    def fetch_commercial_trade(self, lawd_cd: str, deal_ymd: str) -> list[dict[str, str]]:
        """상업업무용 부동산 매매 실거래가 조회

        Args:
            lawd_cd: 법정동코드 앞 5자리
            deal_ymd: 계약년월

        Returns:
            상업용 거래 목록
        """
        params = {"LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd, "numOfRows": "100", "pageNo": "1"}
        logger.info("상업업무용 매매 실거래가 조회: %s / %s", lawd_cd, deal_ymd)
        response = self._get(ENDPOINTS["commercial_trade"], params)
        return self._parse_xml_items(response.text)

    # === 건축물대장 기본개요 ===

    def fetch_building_register(
        self, sigungu_cd: str, bjdong_cd: str, bun: str, ji: str
    ) -> list[dict[str, str]]:
        """건축물대장 기본개요 조회

        Args:
            sigungu_cd: 시군구코드 (5자리, 예: "11680")
            bjdong_cd: 법정동코드 (5자리, 예: "10300")
            bun: 본번 (4자리, 예: "0123")
            ji: 부번 (4자리, 예: "0004")

        Returns:
            건축물대장 목록
        """
        params = {
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "bun": bun,
            "ji": ji,
            "numOfRows": "10",
            "pageNo": "1",
        }
        logger.info("건축물대장 조회: %s-%s %s-%s", sigungu_cd, bjdong_cd, bun, ji)
        response = self._get(ENDPOINTS["building_register"], params)
        return self._parse_xml_items(response.text)

    # === 개별공시지가 ===

    def fetch_land_price(
        self, pnu: str, stdr_year: str = "2025"
    ) -> list[dict[str, str]]:
        """개별공시지가 조회

        Args:
            pnu: 필지고유번호 (19자리, 예: "1168010300101230004")
            stdr_year: 기준연도 (예: "2025")

        Returns:
            공시지가 목록
        """
        params = {
            "pnu": pnu,
            "stdrYear": stdr_year,
            "format": "json",
            "numOfRows": "10",
            "pageNo": "1",
        }
        logger.info("개별공시지가 조회: %s (기준연도: %s)", pnu, stdr_year)
        response = self._get(ENDPOINTS["land_price"], params)

        # 개별공시지가는 JSON 응답
        try:
            data = response.json()
            items = data.get("indvdLandPrices", {}).get("field", [])
            return items if isinstance(items, list) else [items]
        except Exception:
            logger.warning("개별공시지가 JSON 파싱 실패, XML 시도")
            return self._parse_xml_items(response.text)
