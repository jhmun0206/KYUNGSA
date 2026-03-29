"""틸코블렛 API v2.0 등기부등본 제공자.

단계별 API 흐름:
  1. search_address()    — 주소 → 고유번호 목록 (20pt)
  2. fetch_registry_xml() — 고유번호 → 등기부 XML (100pt)
  3. fetch_by_address()  — 주소 → 등기부 XML 일괄 (120pt)

HEADER:
  API-KEY: 32자리 API 키
  ENC-KEY: AES 키를 RSA-2048(PKCS1_v1_5)로 암호화 후 Base64

BODY (모든 [암호화] 항목은 AES-CBC-128 암호화 후 Base64):
  Auth.UserId       [암호화] 인터넷등기소 ID (IROS_PHONE_NO)
  Auth.UserPassword [암호화] 인터넷등기소 PW (IROS_PASSWORD)

암호화 방식:
  - AES-CBC-128, IV = b'\\x00' * 16, PKCS7 패딩
  - AES 키(16바이트 random) → RSA(PKCS1_v1_5) 암호화 → Base64 → ENC-KEY 헤더
"""

import base64
import logging
import os

import httpx
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA

from app.config import settings

logger = logging.getLogger(__name__)

TILKO_DEV_HOST = "https://dev.tilko.net"
TILKO_PROD_HOST = "https://api.tilko.net"
ADDRESS_SEARCH_PATH = "/api/v2.0/Iros2/RetrieveSmplSrchList"
REGISTRY_PATH = "/api/v2.0/Iros2IdLogin/RealtyRegistry"


class TilkoRegistryProvider:
    """틸코블렛 API를 통한 등기부등본 조회.

    주소 기반 조회 흐름:
        fetch_by_address(address) = search_address(address) + fetch_registry_xml(pin)

    환경변수:
        TILKO_SERVICE_TYPE: "dev" | "prod" (기본값: dev)
        TILKO_API_KEY: 틸코 일반용 API KEY
        TILKO_RSA_PUBLIC_KEY: RSA 서버용 공개키 Base64
        IROS_PHONE_NO: 인터넷등기소 로그인 ID
        IROS_PASSWORD: 인터넷등기소 비밀번호
        IROS_EPREPAY_NO: 전자민원캐시 번호 (하이픈 없이 12자리)
        IROS_EPREPAY_PASS: 전자민원캐시 비밀번호
    """

    def __init__(self) -> None:
        self._api_key = settings.TILKO_API_KEY
        self._rsa_public_key = settings.TILKO_RSA_PUBLIC_KEY
        self._host = (
            TILKO_PROD_HOST
            if settings.TILKO_SERVICE_TYPE == "prod"
            else TILKO_DEV_HOST
        )

    # ── 암호화 헬퍼 ──────────────────────────────────────────────────

    @staticmethod
    def _aes_encrypt(aes_key: bytes, plain: str) -> str:
        """AES-CBC-128으로 암호화 후 Base64 반환.

        IV: b'\\x00' * 16 (고정)
        패딩: PKCS7
        """
        iv = b"\x00" * 16
        data = plain.encode("utf-8")
        pad = AES.block_size - (len(data) % AES.block_size)
        data += bytes([pad] * pad)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        return base64.b64encode(cipher.encrypt(data)).decode("utf-8")

    def _enc_key(self, aes_key: bytes) -> str:
        """AES 키를 RSA 공개키로 암호화 → Base64 (ENC-KEY 헤더용).

        Args:
            aes_key: 16바이트 랜덤 AES 키

        Returns:
            RSA(PKCS1_v1_5) 암호화된 AES 키의 Base64 문자열

        Raises:
            RuntimeError: TILKO_RSA_PUBLIC_KEY 미설정 시
        """
        if not self._rsa_public_key:
            raise RuntimeError(
                "TILKO_RSA_PUBLIC_KEY가 설정되지 않았습니다. "
                "tilko.net → 내정보 → API KEY → 상세보기 Base64에서 복사하세요."
            )
        rsa_key = RSA.import_key(base64.b64decode(self._rsa_public_key))
        cipher = PKCS1_v1_5.new(rsa_key.publickey())
        return base64.b64encode(cipher.encrypt(aes_key)).decode("utf-8")

    def _headers(self, aes_key: bytes) -> dict:
        """API 요청 헤더 생성 (Content-Type + API-KEY + ENC-KEY)."""
        return {
            "Content-Type": "application/json",
            "API-KEY": self._api_key,
            "ENC-KEY": self._enc_key(aes_key),
        }

    # ── 주소 검색 ─────────────────────────────────────────────────────

    def search_address(self, address: str) -> list[dict]:
        """주소로 부동산 고유번호 후보 목록 조회 (20pt).

        Args:
            address: 검색할 부동산 주소

        Returns:
            [{"pin": str, "gubun": str, "address": str, "sangtae": str}, ...]

        Raises:
            RuntimeError: API 키 미설정 또는 검색 실패
        """
        if not self._api_key:
            raise RuntimeError("TILKO_API_KEY가 설정되지 않았습니다.")

        aes_key = os.urandom(16)
        body = {
            "Address":     self._aes_encrypt(aes_key, address),
            "Sangtae":     self._aes_encrypt(aes_key, ""),
            "KindClsFlag": self._aes_encrypt(aes_key, ""),
            "Region":      self._aes_encrypt(aes_key, ""),
            "Page":        self._aes_encrypt(aes_key, "1"),
        }

        logger.info("틸코 주소 검색 요청: address=%s... host=%s", address[:20], self._host)
        resp = httpx.post(
            self._host + ADDRESS_SEARCH_PATH,
            headers=self._headers(aes_key),
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("틸코 주소검색: status=%s", data.get("Status"))

        if data.get("Status") != "OK":
            msg = data.get("Message", "알 수 없는 오류")
            raise RuntimeError(f"틸코 주소 검색 실패: {msg}")

        # 응답 구조: Result.DataList
        result_obj = data.get("Result") or {}
        data_list = result_obj.get("DataList") or []

        candidates = []
        for item in data_list:
            pin = (item.get("pin") or "").replace("-", "").strip()
            if not pin:
                continue
            addr = item.get("rd_addr_detail") or item.get("rd_addr") or ""
            candidates.append({
                "pin":     pin,
                "gubun":   item.get("real_cls_cd", ""),
                "address": addr,
                "sangtae": item.get("addItem", ""),
            })
        logger.info("틸코 주소 검색 결과: %d건", len(candidates))
        return candidates

    def _best_match(self, address: str, candidates: list[dict]) -> str | None:
        """토큰 중복도 기반으로 최적 고유번호 선택.

        Args:
            address: 원본 주소 (공백 분리 토큰화)
            candidates: search_address() 결과 목록

        Returns:
            최적 고유번호 문자열, 후보 없으면 None
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]["pin"]

        tokens = set(address.split())
        best_pin: str | None = None
        best_score = -1
        for c in candidates:
            c_tokens = set(c.get("address", "").split())
            score = len(tokens & c_tokens)
            if score > best_score:
                best_score = score
                best_pin = c["pin"]
        return best_pin

    # ── 등기부 조회 ───────────────────────────────────────────────────

    def fetch_registry_xml(self, realty_pin: str) -> str:
        """부동산 고유번호(Pin)로 등기부등본 XML 조회 (100pt).

        Args:
            realty_pin: 부동산 고유번호 14자리 (하이픈 자동 제거)

        Returns:
            등기부등본 XML 문자열

        Raises:
            RuntimeError: TILKO API 키 미설정 또는 조회 실패
        """
        if not self._api_key:
            raise RuntimeError(
                "TILKO_API_KEY가 설정되지 않았습니다. "
                "tilko.net → 내정보 → API KEY → 일반용에서 복사하세요."
            )

        pin = realty_pin.replace("-", "")
        if len(pin) != 14:
            raise ValueError(f"고유번호는 14자리여야 합니다 (입력: {len(pin)}자리)")

        # 전자민원캐시 번호: 하이픈 제거 후 앞 8자리 / 뒤 4자리 분리
        emoney = settings.IROS_EPREPAY_NO.replace("-", "")
        emoney_no1 = emoney[:8]
        emoney_no2 = emoney[8:12]

        aes_key = os.urandom(16)
        body = {
            "Auth": {
                "UserId": self._aes_encrypt(aes_key, settings.IROS_PHONE_NO),
                "UserPassword": self._aes_encrypt(aes_key, settings.IROS_PASSWORD),
            },
            "Pin": self._aes_encrypt(aes_key, pin),
            "EmoneyNo1": self._aes_encrypt(aes_key, emoney_no1),
            "EmoneyNo2": self._aes_encrypt(aes_key, emoney_no2),
            "EmoneyPwd": self._aes_encrypt(aes_key, settings.IROS_EPREPAY_PASS),
            "CmortFlag": "",
            "TradeSeqFlag": "",
            "AbsCls": "",
            "RgsMttrSmry": "",
        }

        logger.info("틸코 등기부 조회 요청: pin=%s*** host=%s", pin[:4], self._host)
        resp = httpx.post(
            self._host + REGISTRY_PATH,
            headers=self._headers(aes_key),
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("Status") != "OK":
            seq = data.get("StatusSeq", "")
            msg = data.get("Message", "알 수 없는 오류")
            raise RuntimeError(f"틸코 등기부 조회 실패 (seq={seq}): {msg}")

        xml_str: str = data.get("Message", "")
        logger.info("틸코 등기부 조회 성공: pin=%s*** xml_len=%d", pin[:4], len(xml_str))
        return xml_str

    def fetch_by_address(self, address: str) -> tuple[str, str]:
        """주소로 등기부등본 조회 (120pt = 주소검색 20pt + 등기부열람 100pt).

        주소검색으로 고유번호를 찾은 후 등기부를 조회한다.
        후보가 여럿이면 토큰 중복도로 최적 후보를 선택한다.

        Args:
            address: 부동산 주소

        Returns:
            (pin, xml_str): 고유번호 14자리, 등기부등본 XML

        Raises:
            RuntimeError: 주소로 고유번호를 찾을 수 없는 경우
        """
        candidates = self.search_address(address)
        pin = self._best_match(address, candidates)
        if not pin:
            raise RuntimeError(f"주소로 고유번호를 찾을 수 없습니다: {address}")
        xml_str = self.fetch_registry_xml(pin)
        return pin, xml_str
