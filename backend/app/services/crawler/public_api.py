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
    "rh_rent": "https://apis.data.go.kr/1613000/RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "office_rent": "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
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

    # === 연립다세대 전월세 실거래가 ===

    def fetch_rh_rent(self, lawd_cd: str, deal_ymd: str) -> list[dict[str, str]]:
        """연립다세대 전월세 실거래가 조회

        Args:
            lawd_cd: 법정동코드 앞 5자리
            deal_ymd: 계약년월

        Returns:
            연립다세대 전월세 거래 목록
        """
        params = {"LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd, "numOfRows": "100", "pageNo": "1"}
        logger.info("연립다세대 전월세 조회: %s / %s", lawd_cd, deal_ymd)
        response = self._get(ENDPOINTS["rh_rent"], params)
        return self._parse_xml_items(response.text)

    # === 오피스텔 전월세 실거래가 ===

    def fetch_office_rent(self, lawd_cd: str, deal_ymd: str) -> list[dict[str, str]]:
        """오피스텔 전월세 실거래가 조회

        Args:
            lawd_cd: 법정동코드 앞 5자리
            deal_ymd: 계약년월

        Returns:
            오피스텔 전월세 거래 목록
        """
        params = {"LAWD_CD": lawd_cd, "DEAL_YMD": deal_ymd, "numOfRows": "100", "pageNo": "1"}
        logger.info("오피스텔 전월세 조회: %s / %s", lawd_cd, deal_ymd)
        response = self._get(ENDPOINTS["office_rent"], params)
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

    # === 건축물대장 전유공용면적 (호실별) ===

    def fetch_building_units(
        self, sigungu_cd: str, bjdong_cd: str, bun: str, ji: str
    ) -> list[dict]:
        """건축물대장 전유공용면적 조회 (getBrExposPubuseAreaInfo)

        호실별 전용면적 반환. 없거나 실패하면 빈 리스트.

        Args:
            sigungu_cd: 시군구코드 (5자리)
            bjdong_cd: 법정동코드 (5자리)
            bun: 본번 (4자리)
            ji: 부번 (4자리)

        Returns:
            호실 목록 [{"ho": "101호", "floor": 1, "area_m2": 33.5}, ...]
        """
        url = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrExposPubuseAreaInfo"
        params = {
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "bun": bun.zfill(4),
            "ji": ji.zfill(4),
            "numOfRows": "200",
            "pageNo": "1",
            "_type": "json",
        }
        try:
            response = self._get(url, params)
            data = response.json()
            raw_items = (
                data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
            )
            # 단건 응답은 dict로 오는 경우 있음
            if isinstance(raw_items, dict):
                raw_items = [raw_items]
            if not isinstance(raw_items, list):
                return []

            # 호실별 중복 제거: API가 전유/공용 두 행씩 반환
            # → ho_nm 기준으로 면적 큰 쪽 유지 (층 정보 포함된 행이 면적 큼)
            seen: dict[str, dict] = {}
            for item in raw_items:
                ho_nm = str(item.get("hoNm") or "").strip()
                flr_no_nm = str(item.get("flrNoNm") or "").strip()
                area_raw = item.get("area") or item.get("expoArea") or ""
                area = _safe_float_val(area_raw)

                if ho_nm and area and area > 0:
                    # 층 번호: 숫자만 추출
                    digits = "".join(c for c in flr_no_nm if c.isdigit())
                    floor = int(digits) if digits else 0
                    existing = seen.get(ho_nm)
                    if existing is None or area > existing["area_m2"]:
                        seen[ho_nm] = {"ho": ho_nm, "floor": floor, "area_m2": round(area, 2)}

            units = list(seen.values())
            units.sort(key=lambda x: (x["floor"], x["ho"]))
            logger.info("전유부 %d호실 수신 (sigungu=%s bun=%s)", len(units), sigungu_cd, bun)
            return units
        except Exception as e:
            logger.warning("전유부 조회 실패 [sigungu=%s bun=%s]: %s", sigungu_cd, bun, e)
            return []

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


# ── 모듈 수준 유틸리티 ──────────────────────────────────────────


def _safe_float_val(value: object) -> float | None:
    """임의 타입 → float 변환 (실패 시 None)"""
    if value is None or value == "":
        return None
    try:
        v = float(str(value).replace(",", "").strip())
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None
