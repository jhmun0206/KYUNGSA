"""Geo 클라이언트 단위 테스트 (mock 기반)"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.crawler.geo_client import GeoClient


@pytest.fixture
def client():
    """테스트용 Geo 클라이언트"""
    with patch("app.services.crawler.geo_client.settings") as mock_settings:
        mock_settings.KAKAO_REST_API_KEY = "test_kakao_key"
        mock_settings.VWORLD_API_KEY = "test_vworld_key"
        yield GeoClient()


class TestKakaoGeocode:
    """카카오 Geocode 테스트"""

    @patch("app.services.crawler.geo_client.httpx.Client")
    def test_geocode_성공(self, mock_client_cls, client):
        """주소를 좌표로 변환한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "documents": [
                {
                    "address_name": "서울 강남구 역삼동 123-4",
                    "x": "127.0365",
                    "y": "37.4994",
                    "address_type": "REGION_ADDR",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        result = client.geocode("서울 강남구 역삼동 123-4")

        assert result is not None
        assert result["x"] == "127.0365"
        assert result["y"] == "37.4994"
        assert "역삼동" in result["address"]

    @patch("app.services.crawler.geo_client.httpx.Client")
    def test_geocode_결과없음(self, mock_client_cls, client):
        """검색 결과가 없으면 None을 반환한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"documents": []}
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        result = client.geocode("존재하지않는주소")

        assert result is None


class TestVworldLandUse:
    """Vworld 용도지역 조회 테스트"""

    @patch("app.services.crawler.geo_client.httpx.Client")
    def test_fetch_land_use_성공(self, mock_client_cls, client):
        """좌표 기준 용도지역을 조회한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {
                "status": "OK",
                "result": {
                    "featureCollection": {
                        "features": [
                            {"properties": {"name": "제2종일반주거지역", "code": "UQA120"}}
                        ]
                    }
                },
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        result = client.fetch_land_use("127.0365", "37.4994")

        assert len(result) == 1
        assert result[0]["name"] == "제2종일반주거지역"

    @patch("app.services.crawler.geo_client.httpx.Client")
    def test_fetch_land_use_실패(self, mock_client_cls, client):
        """Vworld 응답 실패 시 빈 리스트를 반환한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": {"status": "NOT_FOUND"}}
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        result = client.fetch_land_use("0", "0")

        assert result == []


class TestVworldSearch:
    """Vworld 주소 검색 테스트"""

    @patch("app.services.crawler.geo_client.httpx.Client")
    def test_search_address_성공(self, mock_client_cls, client):
        """지번 주소를 검색한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {
                "status": "OK",
                "result": {
                    "items": [
                        {"title": "서울특별시 강남구 역삼동 123-4", "point": {"x": "127.0365", "y": "37.4994"}}
                    ]
                },
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        result = client.search_address("역삼동 123-4")

        assert len(result) == 1
        assert "역삼동" in result[0]["title"]

    @patch("app.services.crawler.geo_client.httpx.Client")
    def test_search_address_결과없음(self, mock_client_cls, client):
        """검색 결과 없으면 빈 리스트"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": {"status": "NOT_FOUND"}}
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        result = client.search_address("없는주소")

        assert result == []
