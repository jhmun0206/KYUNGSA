"""공공 데이터 API 연결 테스트 (수동 실행용)

서울 강남구 역삼동 기준 각 API 1건씩 호출하여 결과 출력.
실행: python -m scripts.test_public_api (프로젝트 루트에서)
또는: cd backend && python -m scripts.test_public_api

※ .env에 PUBLIC_DATA_API_KEY가 설정되어 있어야 합니다.
"""

import sys
import os

# backend/app을 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.services.crawler.public_api import PublicDataClient


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_apt_trade(client: PublicDataClient) -> bool:
    """아파트 매매 실거래가 — 강남구 2026년 1월"""
    separator("1. 아파트 매매 실거래가 (강남구, 202601)")
    try:
        items = client.fetch_apt_trade("11680", "202601")
        print(f"  결과: {len(items)}건")
        if items:
            sample = items[0]
            print(f"  샘플: {sample}")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def test_apt_rent(client: PublicDataClient) -> bool:
    """아파트 전월세 실거래가 — 강남구 2026년 1월"""
    separator("2. 아파트 전월세 실거래가 (강남구, 202601)")
    try:
        items = client.fetch_apt_rent("11680", "202601")
        print(f"  결과: {len(items)}건")
        if items:
            print(f"  샘플: {items[0]}")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def test_commercial_trade(client: PublicDataClient) -> bool:
    """상업업무용 매매 실거래가 — 강남구 2026년 1월"""
    separator("3. 상업업무용 매매 실거래가 (강남구, 202601)")
    try:
        items = client.fetch_commercial_trade("11680", "202601")
        print(f"  결과: {len(items)}건")
        if items:
            print(f"  샘플: {items[0]}")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def test_building_register(client: PublicDataClient) -> bool:
    """건축물대장 — 강남구 역삼동"""
    separator("4. 건축물대장 (강남구 역삼동)")
    try:
        # 강남구(11680), 역삼동(10300), 본번 0123, 부번 0004 (예시)
        items = client.fetch_building_register("11680", "10300", "0123", "0004")
        print(f"  결과: {len(items)}건")
        if items:
            print(f"  샘플: {items[0]}")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def test_land_price(client: PublicDataClient) -> bool:
    """개별공시지가 — 강남구 역삼동"""
    separator("5. 개별공시지가 (강남구 역삼동)")
    try:
        # 강남구 역삼동 PNU 예시
        items = client.fetch_land_price("1168010300101230004", "2025")
        print(f"  결과: {len(items)}건")
        if items:
            print(f"  샘플: {items[0]}")
        return True
    except Exception as e:
        print(f"  실패: {e}")
        return False


def main() -> None:
    print("="*60)
    print("  KYUNGSA — 공공 데이터 API 연결 테스트")
    print(f"  API KEY: {settings.PUBLIC_DATA_API_KEY[:8]}..." if settings.PUBLIC_DATA_API_KEY else "  API KEY: 미설정!")
    print("="*60)

    if not settings.PUBLIC_DATA_API_KEY:
        print("\n⚠️  PUBLIC_DATA_API_KEY가 .env에 설정되지 않았습니다.")
        sys.exit(1)

    client = PublicDataClient()
    results = {}

    results["아파트 매매"] = test_apt_trade(client)
    results["아파트 전월세"] = test_apt_rent(client)
    results["상업업무용 매매"] = test_commercial_trade(client)
    results["건축물대장"] = test_building_register(client)
    results["개별공시지가"] = test_land_price(client)

    # 요약
    separator("결과 요약")
    for name, ok in results.items():
        status = "✅ 성공" if ok else "❌ 실패"
        print(f"  {name}: {status}")

    success = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  총 {total}개 중 {success}개 성공")


if __name__ == "__main__":
    main()
