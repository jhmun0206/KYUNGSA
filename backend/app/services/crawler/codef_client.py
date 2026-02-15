"""CODEF API 클라이언트 (유료, 2단 수집)

등기부등본·공시가격·토지공시지가·시세 조회.
OAuth 2.0 Bearer Token 방식 (7일 유효, 메모리 캐싱).
CostGate 통과 물건만 실행한다.
"""

import base64
import json
import logging
import time
import urllib.parse
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# CODEF 엔드포인트
CODEF_TOKEN_URL = "https://oauth.codef.io/oauth/token"
CODEF_SANDBOX_BASE = "https://development.codef.io"
CODEF_PRODUCTION_BASE = "https://api.codef.io"


class CodefClient:
    """CODEF API 클라이언트

    - 토큰 발급/갱신은 메모리 캐싱 (DB 없이 동작)
    - 토큰 7일 유효, 만료 1일(86400초) 전에 자동 갱신
    - 401 응답 시 토큰 재발급 후 1회 재시도
    """

    def __init__(self, service_type: str | None = None) -> None:
        # service_type 미지정 시 CODEF_SERVICE_TYPE 환경변수로 결정
        if service_type is None:
            service_type = settings.CODEF_SERVICE_TYPE

        if service_type == "production":
            self._client_id = settings.CODEF_CLIENT_ID
            self._client_secret = settings.CODEF_CLIENT_SECRET
            self._base_url = CODEF_PRODUCTION_BASE
        elif service_type == "demo":
            self._client_id = settings.CODEF_DEMO_CLIENT_ID
            self._client_secret = settings.CODEF_DEMO_CLIENT_SECRET
            self._base_url = CODEF_SANDBOX_BASE
        else:  # sandbox (기본값)
            self._client_id = settings.CODEF_SANDBOX_CLIENT_ID
            self._client_secret = settings.CODEF_SANDBOX_CLIENT_SECRET
            self._base_url = CODEF_SANDBOX_BASE

        self._service_type = service_type
        logger.info("CODEF 클라이언트 초기화: service_type=%s, base_url=%s", service_type, self._base_url)

        # 메모리 토큰 캐시
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    # === 토큰 관리 ===

    def _get_access_token(self) -> str:
        """OAuth 2.0 토큰 발급

        POST https://oauth.codef.io/oauth/token
        grant_type=client_credentials
        Authorization: Basic base64(client_id:client_secret)
        """
        credentials = f"{self._client_id}:{self._client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        with httpx.Client(timeout=30) as client:
            response = client.post(
                CODEF_TOKEN_URL,
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()

        data = response.json()
        token = data["access_token"]
        # CODEF 토큰 유효기간: 7일 (604800초)
        expires_in = data.get("expires_in", 604800)
        self._access_token = token
        self._token_expires_at = time.time() + expires_in
        logger.info("CODEF 토큰 발급 완료 (만료: %d초 후)", expires_in)
        return token

    def _ensure_token(self) -> str:
        """유효한 토큰 반환. 만료 1일 전이면 갱신."""
        buffer = 86400  # 1일 전 갱신
        if self._access_token and time.time() < (self._token_expires_at - buffer):
            return self._access_token
        return self._get_access_token()

    # === 공통 요청 ===

    def _request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """CODEF API 요청. 401시 토큰 재발급 후 1회 재시도."""
        url = f"{self._base_url}{endpoint}"
        token = self._ensure_token()

        for attempt in range(2):
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if response.status_code == 401 and attempt == 0:
                logger.warning("CODEF 401 응답 — 토큰 재발급 시도")
                token = self._get_access_token()
                continue

            response.raise_for_status()

            # CODEF 응답은 URL-encoded 텍스트로 반환됨 (Content-Type: text/plain)
            raw_text = response.text
            if raw_text.startswith("%7B") or raw_text.startswith("%7b"):
                raw_text = urllib.parse.unquote_plus(raw_text)
            data = json.loads(raw_text)

            # CODEF 응답 구조: {"result": {"code": "CF-...", "message": "..."}, "data": ...}
            result_code = data.get("result", {}).get("code", "")
            if result_code != "CF-00000":
                msg = data.get("result", {}).get("message", "알 수 없는 오류")
                logger.error("CODEF API 오류: [%s] %s", result_code, msg)
                raise CodefApiError(result_code, msg)

            # data 필드도 URL-encoded 문자열일 수 있음
            data_field = data.get("data", {})
            if isinstance(data_field, str):
                decoded = urllib.parse.unquote_plus(data_field)
                data_field = json.loads(decoded) if decoded else {}

            return data_field

        raise CodefApiError("AUTH_FAILED", "토큰 재발급 후에도 인증 실패")

    # === 등기부등본 열람 ===

    def fetch_registry(self, unique_no: str) -> dict[str, Any]:
        """등기부등본 열람

        Args:
            unique_no: 부동산 고유번호 (14자리)

        Returns:
            등기부등본 데이터 (CODEF 응답 data 필드)
        """
        payload = {
            "connectedId": "",
            "organization": "0002",
            "uniqueNo": unique_no,
            "type": "0",  # 0: 전체, 1: 갑구, 2: 을구
        }
        logger.info("등기부등본 열람 요청: %s", unique_no)
        return self._request("/v1/kr/public/ck/real-estate/registration", payload)

    # === 토지 개별공시지가 ===

    def fetch_land_price(self, address: str) -> dict[str, Any]:
        """토지 개별공시지가 조회

        Args:
            address: 지번 주소

        Returns:
            공시지가 데이터
        """
        payload = {
            "connectedId": "",
            "organization": "0002",
            "address": address,
        }
        logger.info("토지 개별공시지가 조회: %s", address)
        return self._request("/v1/kr/public/ck/land-price/individual", payload)

    # === 개별주택 가격 ===

    def fetch_housing_price(self, address: str) -> dict[str, Any]:
        """개별주택 공시가격 조회

        Args:
            address: 주택 소재지 주소

        Returns:
            공시가격 데이터
        """
        payload = {
            "connectedId": "",
            "organization": "0002",
            "address": address,
        }
        logger.info("개별주택 공시가격 조회: %s", address)
        return self._request("/v1/kr/public/ck/housing-price/individual", payload)

    # === 공동주택 공시가격 ===

    def fetch_apartment_price(self, address: str) -> dict[str, Any]:
        """공동주택 공시가격 조회

        Args:
            address: 아파트 소재지 주소

        Returns:
            공동주택 공시가격 데이터
        """
        payload = {
            "connectedId": "",
            "organization": "0002",
            "address": address,
        }
        logger.info("공동주택 공시가격 조회: %s", address)
        return self._request("/v1/kr/public/ck/housing-price/apartment", payload)

    # === 시세정보 ===

    def fetch_market_price(self, complex_code: str) -> dict[str, Any]:
        """시세정보 조회

        Args:
            complex_code: 단지코드

        Returns:
            시세 데이터
        """
        payload = {
            "connectedId": "",
            "organization": "0002",
            "complexCode": complex_code,
        }
        logger.info("시세정보 조회: %s", complex_code)
        return self._request("/v1/kr/public/ck/real-estate/market-price", payload)


class CodefApiError(Exception):
    """CODEF API 오류"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
