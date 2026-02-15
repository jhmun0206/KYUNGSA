"""CODEF 클라이언트 단위 테스트 (mock 기반)"""

import json
import time
import urllib.parse
from unittest.mock import MagicMock, patch

import pytest

from app.services.crawler.codef_client import CodefApiError, CodefClient


@pytest.fixture
def client():
    """테스트용 CODEF 클라이언트 (sandbox)"""
    with patch("app.services.crawler.codef_client.settings") as mock_settings:
        mock_settings.CODEF_SERVICE_TYPE = "sandbox"
        mock_settings.CODEF_SANDBOX_CLIENT_ID = "test_sandbox_id"
        mock_settings.CODEF_SANDBOX_CLIENT_SECRET = "test_sandbox_secret"
        mock_settings.CODEF_DEMO_CLIENT_ID = ""
        mock_settings.CODEF_DEMO_CLIENT_SECRET = ""
        mock_settings.CODEF_CLIENT_ID = ""
        mock_settings.CODEF_CLIENT_SECRET = ""
        yield CodefClient(service_type="sandbox")


class TestTokenManagement:
    """토큰 발급/갱신 테스트"""

    @patch("app.services.crawler.codef_client.httpx.Client")
    def test_get_access_token_성공(self, mock_client_cls, client):
        """토큰 발급 성공 시 access_token과 만료시간을 저장한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token_123",
            "expires_in": 604800,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        token = client._get_access_token()

        assert token == "test_token_123"
        assert client._access_token == "test_token_123"
        assert client._token_expires_at > time.time()

    @patch("app.services.crawler.codef_client.httpx.Client")
    def test_ensure_token_캐시_유효(self, mock_client_cls, client):
        """캐시된 토큰이 유효하면 재발급하지 않는다"""
        client._access_token = "cached_token"
        client._token_expires_at = time.time() + 604800  # 7일 후

        token = client._ensure_token()

        assert token == "cached_token"
        mock_client_cls.return_value.__enter__.return_value.post.assert_not_called()

    @patch("app.services.crawler.codef_client.httpx.Client")
    def test_ensure_token_만료_임박시_갱신(self, mock_client_cls, client):
        """만료 1일 이내면 토큰을 갱신한다"""
        client._access_token = "old_token"
        client._token_expires_at = time.time() + 3600  # 1시간 후 (1일 미만)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 604800,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        token = client._ensure_token()

        assert token == "new_token"


class TestApiMethods:
    """API 메서드 테스트"""

    @patch.object(CodefClient, "_request")
    def test_fetch_registry(self, mock_request, client):
        """등기부등본 열람 요청이 올바른 엔드포인트와 payload로 호출된다"""
        mock_request.return_value = {"registryData": "test"}

        result = client.fetch_registry("12345678901234")

        mock_request.assert_called_once_with(
            "/v1/kr/public/ck/real-estate/registration",
            {
                "connectedId": "",
                "organization": "0002",
                "uniqueNo": "12345678901234",
                "type": "0",
            },
        )
        assert result == {"registryData": "test"}

    @patch.object(CodefClient, "_request")
    def test_fetch_land_price(self, mock_request, client):
        """토지 개별공시지가 조회"""
        mock_request.return_value = {"price": "500000"}

        result = client.fetch_land_price("서울시 강남구 역삼동 123-4")

        mock_request.assert_called_once()
        assert result == {"price": "500000"}

    @patch.object(CodefClient, "_request")
    def test_fetch_market_price(self, mock_request, client):
        """시세정보 조회"""
        mock_request.return_value = {"marketPrice": "1000000000"}

        result = client.fetch_market_price("COMPLEX001")

        mock_request.assert_called_once_with(
            "/v1/kr/public/ck/real-estate/market-price",
            {
                "connectedId": "",
                "organization": "0002",
                "complexCode": "COMPLEX001",
            },
        )


class TestErrorHandling:
    """오류 처리 테스트"""

    @patch("app.services.crawler.codef_client.httpx.Client")
    def test_api_오류_코드_처리(self, mock_client_cls, client):
        """CODEF 응답 코드가 CF-00000이 아니면 CodefApiError를 발생시킨다"""
        client._access_token = "valid_token"
        client._token_expires_at = time.time() + 604800

        resp_body = {"result": {"code": "CF-09999", "message": "잘못된 요청"}, "data": {}}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = json.dumps(resp_body, ensure_ascii=False)
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        with pytest.raises(CodefApiError) as exc_info:
            client._request("/test", {})

        assert exc_info.value.code == "CF-09999"
        assert "잘못된 요청" in str(exc_info.value)

    @patch("app.services.crawler.codef_client.httpx.Client")
    def test_url_encoded_응답_처리(self, mock_client_cls, client):
        """CODEF 응답이 URL-encoded 텍스트인 경우 정상 파싱한다"""
        client._access_token = "valid_token"
        client._token_expires_at = time.time() + 604800

        resp_body = {"result": {"code": "CF-00000", "message": "성공"}, "data": {"key": "값"}}
        encoded_text = urllib.parse.quote_plus(json.dumps(resp_body, ensure_ascii=False))
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = encoded_text
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        result = client._request("/test", {})
        assert result == {"key": "값"}

    @patch("app.services.crawler.codef_client.httpx.Client")
    def test_json_응답도_처리(self, mock_client_cls, client):
        """CODEF 응답이 일반 JSON인 경우에도 정상 파싱한다"""
        client._access_token = "valid_token"
        client._token_expires_at = time.time() + 604800

        resp_body = {"result": {"code": "CF-00000", "message": "성공"}, "data": {"test": 123}}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = json.dumps(resp_body)
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response

        result = client._request("/test", {})
        assert result == {"test": 123}
