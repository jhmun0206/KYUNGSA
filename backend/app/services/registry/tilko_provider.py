"""틸코블렛 API v2.0 등기부등본 제공자.

API 스펙:
  POST /api/v2.0/Iros2IdLogin/RealtyRegistry
  비용: 100포인트/건

HEADER:
  API-KEY: 32자리 API 키
  ENC-KEY: AES 키를 RSA-2048(PKCS1_v1_5)로 암호화 후 Base64

BODY (모든 [암호화] 항목은 AES-CBC-128 암호화 후 Base64):
  Auth.UserId       [암호화] 인터넷등기소 ID (IROS_PHONE_NO)
  Auth.UserPassword [암호화] 인터넷등기소 PW (IROS_PASSWORD)
  Pin               [암호화] 부동산 고유번호 14자리 ('-' 제외)
  EmoneyNo1         [암호화] 전자민원캐시 앞 8자리 (IROS_EPREPAY_NO 앞 8자리)
  EmoneyNo2         [암호화] 전자민원캐시 뒤 4자리 (IROS_EPREPAY_NO 뒤 4자리)
  EmoneyPwd         [암호화] 전자민원캐시 비밀번호 (IROS_EPREPAY_PASS)
  CmortFlag                  공동담보/전세목록 (Y/N)
  TradeSeqFlag               매매목록 (Y/N)
  AbsCls                     등기기록유형
  RgsMttrSmry                등기사항요약 (1: 포함)

RESPONSE:
  Status:    OK / ERROR
  StatusSeq: 오류 일련번호
  Message:   등기부등본 XML 데이터

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
REGISTRY_PATH = "/api/v2.0/Iros2IdLogin/RealtyRegistry"


class TilkoRegistryProvider:
    """틸코블렛 API를 통한 등기부등본 조회.

    IROS 로그인 인증 방식을 사용하며, 인터넷등기소 계정과
    전자민원캐시로 100포인트/건 과금된다.

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

    def _enc_key_header(self, aes_key: bytes) -> str:
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

    # ── 등기부 조회 ───────────────────────────────────────────────────

    def fetch_registry_xml(self, realty_pin: str) -> str:
        """부동산 고유번호(Pin)로 등기부등본 XML 조회.

        100포인트 소모. 실 운영 환경에서만 호출할 것.

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

        headers = {
            "Content-Type": "application/json",
            "API-KEY": self._api_key,
            "ENC-KEY": self._enc_key_header(aes_key),
        }
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
            headers=headers,
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
