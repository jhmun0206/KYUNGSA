"""지리/주소 API 클라이언트 (무료, 1단 수집)

카카오: 주소 → 좌표 변환 (geocode)
Vworld: 좌표 → 용도지역/지구 조회, 지번 주소 검색
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# API 엔드포인트
KAKAO_GEOCODE_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"


class GeoClient:
    """지리/주소 API 클라이언트

    카카오 + Vworld 연동으로 주소 → 좌표 → 용도지역 파이프라인 제공.
    """

    def __init__(self) -> None:
        self._kakao_key = settings.KAKAO_REST_API_KEY
        self._vworld_key = settings.VWORLD_API_KEY

    # === 카카오: 주소 → 좌표 변환 ===

    def geocode(self, address: str) -> dict[str, Any] | None:
        """주소를 좌표로 변환 (카카오 Geocoding)

        Args:
            address: 검색할 주소 (도로명/지번)

        Returns:
            {"address": ..., "x": 경도, "y": 위도, "address_type": ...}
            결과 없으면 None
        """
        with httpx.Client(timeout=10) as client:
            response = client.get(
                KAKAO_GEOCODE_URL,
                params={"query": address},
                headers={"Authorization": f"KakaoAK {self._kakao_key}"},
            )
        response.raise_for_status()

        data = response.json()
        documents = data.get("documents", [])
        if not documents:
            logger.warning("카카오 Geocode 결과 없음: %s", address)
            return None

        doc = documents[0]
        result = {
            "address": doc.get("address_name", ""),
            "x": doc.get("x", ""),
            "y": doc.get("y", ""),
            "address_type": doc.get("address_type", ""),
        }
        logger.info("Geocode 성공: %s → (%s, %s)", address, result["x"], result["y"])
        return result

    # === 카카오: 좌표 기준 카테고리 검색 ===

    def search_nearby_category(
        self,
        x: str,
        y: str,
        category_group_code: str,
        radius: int = 1000,
    ) -> list[dict[str, Any]]:
        """카카오 카테고리 검색 — 반경 내 시설 목록

        Args:
            x: 경도 (longitude)
            y: 위도 (latitude)
            category_group_code: 카테고리 코드
                SW8=지하철역, SC4=학교, MT1=대형마트, CS2=편의점, HP8=병원
            radius: 검색 반경 (m, 최대 20000)

        Returns:
            [{"place_name": str, "distance": str, ...}, ...]
            실패(HTTP 오류/타임아웃) 시 예외 전파 — 호출자가 fail-open 처리
        """
        with httpx.Client(timeout=10) as client:
            response = client.get(
                KAKAO_CATEGORY_URL,
                params={
                    "category_group_code": category_group_code,
                    "x": x,
                    "y": y,
                    "radius": radius,
                    "size": 15,
                    "sort": "distance",
                },
                headers={"Authorization": f"KakaoAK {self._kakao_key}"},
            )
        response.raise_for_status()

        docs = response.json().get("documents", [])
        logger.info(
            "카테고리 검색 (%s, r=%dm): %d건 (%.4s,%.4s)",
            category_group_code,
            radius,
            len(docs),
            x,
            y,
        )
        return docs

    # === Vworld: 좌표 → 용도지역/지구 조회 ===

    def fetch_land_use(self, x: str, y: str) -> list[dict[str, Any]]:
        """좌표 기준 용도지역 조회 (Vworld LT_C_UQ111)

        Args:
            x: 경도 (longitude)
            y: 위도 (latitude)

        Returns:
            용도지역 목록 [{"name": "일반상업지역", ...}, ...]
        """
        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LT_C_UQ111",
            "key": self._vworld_key,
            "domain": "localhost",
            "crs": "EPSG:4326",
            "geomFilter": f"POINT({x} {y})",
            "geometry": "false",
            "size": "10",
            "page": "1",
            "format": "json",
        }

        with httpx.Client(timeout=15) as client:
            response = client.get(VWORLD_DATA_URL, params=params)
        response.raise_for_status()

        data = response.json()
        response_obj = data.get("response", {})
        status = response_obj.get("status", "")

        if status != "OK":
            logger.warning("Vworld 용도지역 조회 실패: status=%s", status)
            return []

        features = (
            response_obj.get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        results = []
        for feat in features:
            props = feat.get("properties", {})
            # LT_C_UQ111 응답: uname=용도지역명
            if props.get("uname"):
                props["name"] = props["uname"]
            results.append(props)

        logger.info("용도지역 조회 성공: (%s, %s) → %d건", x, y, len(results))
        return results

    # === Vworld: 지번 주소 검색 ===

    def search_address(self, query: str) -> list[dict[str, Any]]:
        """지번 주소 검색 (Vworld)

        Args:
            query: 검색할 주소 문자열

        Returns:
            검색 결과 목록
        """
        params = {
            "service": "search",
            "request": "search",
            "query": query,
            "type": "address",
            "category": "parcel",
            "key": self._vworld_key,
            "size": "10",
            "page": "1",
            "format": "json",
        }

        with httpx.Client(timeout=10) as client:
            response = client.get(VWORLD_SEARCH_URL, params=params)
        response.raise_for_status()

        data = response.json()
        response_obj = data.get("response", {})
        status = response_obj.get("status", "")

        if status != "OK":
            logger.warning("Vworld 주소 검색 실패: status=%s, query=%s", status, query)
            return []

        items = response_obj.get("result", {}).get("items", [])
        logger.info("주소 검색 성공: '%s' → %d건", query, len(items))
        return items
