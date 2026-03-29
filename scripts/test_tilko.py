"""틸코블렛 API 연결 테스트.

실행 방법:
  # 암호화 테스트만 (포인트 소모 없음, 기본)
  PYTHONPATH=backend backend/.venv/bin/python scripts/test_tilko.py

  # 실제 등기부 조회 (100포인트 소모!)
  PYTHONPATH=backend backend/.venv/bin/python scripts/test_tilko.py [14자리고유번호]
  예) PYTHONPATH=backend backend/.venv/bin/python scripts/test_tilko.py 11460000000000
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.services.registry.tilko_provider import TilkoRegistryProvider  # noqa: E402


def test_crypto() -> None:
    """암호화 로직 테스트 (포인트 소모 없음)"""
    provider = TilkoRegistryProvider()
    print(f"HOST     : {provider._host}")
    print(f"API-KEY  : {provider._api_key[:8]}..." if provider._api_key else "API-KEY  : (미설정)")
    print(
        f"RSA-KEY  : {provider._rsa_public_key[:30]}..."
        if provider._rsa_public_key
        else "RSA-KEY  : (미설정)"
    )

    if not provider._api_key or not provider._rsa_public_key:
        print("⚠️  TILKO_API_KEY 또는 TILKO_RSA_PUBLIC_KEY 미설정 — 암호화 테스트 건너뜀")
        return

    aes_key = os.urandom(16)
    encrypted = provider._aes_encrypt(aes_key, "test_value_1234")
    enc_key = provider._enc_key_header(aes_key)
    print(f"AES 암호화 : {encrypted[:30]}...")
    print(f"RSA 암호화 : {enc_key[:30]}...")
    print("✅ 암호화 테스트 성공")


def test_registry(pin: str) -> None:
    """실제 등기부 조회 (100포인트 소모!)

    Args:
        pin: 부동산 고유번호 14자리 (하이픈 포함/미포함 모두 허용)
    """
    provider = TilkoRegistryProvider()
    clean_pin = pin.replace("-", "")
    print(f"조회 시작: pin={clean_pin[:4]}*** (host={provider._host})")
    print("⚠️  100포인트 소모됩니다.")

    xml_str = provider.fetch_registry_xml(clean_pin)
    print(f"✅ 조회 성공: XML {len(xml_str)}자")
    print("--- XML 미리보기 (300자) ---")
    print(xml_str[:300])

    out_path = "/tmp/tilko_result.xml"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"결과 저장: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_registry(sys.argv[1])
    else:
        test_crypto()
