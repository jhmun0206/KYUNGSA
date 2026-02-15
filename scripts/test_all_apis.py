"""전체 API 연결 테스트 (수동 실행용)

모든 외부 API (공공데이터, CODEF, 카카오, Vworld)를 실제 키로 1건씩 호출.
실행: python scripts/test_all_apis.py (프로젝트 루트에서)

※ .env에 모든 API 키가 설정되어 있어야 합니다.
"""

import sys
import os

# backend/app을 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.services.crawler.public_api import PublicDataClient
from app.services.crawler.codef_client import CodefClient, CodefApiError
from app.services.crawler.geo_client import GeoClient


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check_key(name: str, value: str) -> bool:
    """API 키 존재 여부 확인"""
    if value:
        print(f"  {name}: {value[:8]}...")
        return True
    else:
        print(f"  {name}: ❌ 미설정")
        return False


def test_public_apis() -> dict[str, bool]:
    """공공데이터 API 테스트"""
    results = {}
    if not settings.PUBLIC_DATA_API_KEY:
        print("  ⚠️  PUBLIC_DATA_API_KEY 미설정 — 건너뜀")
        return results

    client = PublicDataClient()

    # 아파트 매매 실거래가
    separator("공공 API: 아파트 매매 실거래가")
    try:
        items = client.fetch_apt_trade("11680", "202601")
        print(f"  결과: {len(items)}건")
        results["공공-아파트매매"] = len(items) >= 0  # 0건이어도 연결 성공
    except Exception as e:
        print(f"  실패: {e}")
        results["공공-아파트매매"] = False

    # 건축물대장
    separator("공공 API: 건축물대장")
    try:
        items = client.fetch_building_register("11680", "10300", "0123", "0004")
        print(f"  결과: {len(items)}건")
        results["공공-건축물대장"] = True
    except Exception as e:
        print(f"  실패: {e}")
        results["공공-건축물대장"] = False

    return results


def test_codef_apis() -> dict[str, bool]:
    """CODEF API 테스트"""
    results = {}
    svc_type = settings.CODEF_SERVICE_TYPE
    # 서비스 타입에 따라 키 확인
    if svc_type == "production":
        has_key = settings.CODEF_CLIENT_ID and settings.CODEF_CLIENT_SECRET
    elif svc_type == "demo":
        has_key = settings.CODEF_DEMO_CLIENT_ID and settings.CODEF_DEMO_CLIENT_SECRET
    else:  # sandbox
        has_key = settings.CODEF_SANDBOX_CLIENT_ID and settings.CODEF_SANDBOX_CLIENT_SECRET
    if not has_key:
        print(f"  ⚠️  CODEF {svc_type} 키 미설정 — 건너뜀")
        return results

    client = CodefClient()  # CODEF_SERVICE_TYPE에 따라 자동 결정

    # 토큰 발급
    separator("CODEF: 토큰 발급")
    try:
        token = client._get_access_token()
        print(f"  토큰: {token[:20]}...")
        results["CODEF-토큰발급"] = True
    except Exception as e:
        print(f"  실패: {e}")
        results["CODEF-토큰발급"] = False
        return results  # 토큰 실패면 이후 테스트 불가

    # 등기부등본 (샌드박스)
    separator("CODEF: 등기부등본 (샌드박스)")
    try:
        data = client.fetch_registry("1234567890123")
        print(f"  결과: {data}")
        results["CODEF-등기부등본"] = True
    except CodefApiError as e:
        print(f"  API 오류: {e}")
        results["CODEF-등기부등본"] = False
    except Exception as e:
        print(f"  실패: {e}")
        results["CODEF-등기부등본"] = False

    return results


def test_geo_apis() -> dict[str, bool]:
    """카카오 + Vworld 테스트"""
    results = {}
    client = GeoClient()

    # 카카오 Geocode
    if settings.KAKAO_REST_API_KEY:
        separator("카카오: Geocode")
        try:
            result = client.geocode("서울특별시 강남구 테헤란로 152")
            if result:
                print(f"  결과: {result['address']} → ({result['x']}, {result['y']})")
                results["카카오-Geocode"] = True
            else:
                print("  결과: 없음 (주소를 찾을 수 없음)")
                results["카카오-Geocode"] = False
        except Exception as e:
            print(f"  실패: {e}")
            results["카카오-Geocode"] = False
    else:
        print("  ⚠️  KAKAO_REST_API_KEY 미설정 — 건너뜀")

    # Vworld 주소 검색
    if settings.VWORLD_API_KEY:
        separator("Vworld: 주소 검색")
        try:
            items = client.search_address("서울 강남구 역삼동")
            print(f"  결과: {len(items)}건")
            if items:
                print(f"  샘플: {items[0]}")
            results["Vworld-주소검색"] = len(items) > 0
        except Exception as e:
            print(f"  실패: {e}")
            results["Vworld-주소검색"] = False

        # Vworld 용도지역
        separator("Vworld: 용도지역 조회")
        try:
            land_use = client.fetch_land_use("127.0365", "37.4994")
            print(f"  결과: {len(land_use)}건")
            if land_use:
                print(f"  샘플: {land_use[0]}")
            results["Vworld-용도지역"] = True
        except Exception as e:
            print(f"  실패: {e}")
            results["Vworld-용도지역"] = False
    else:
        print("  ⚠️  VWORLD_API_KEY 미설정 — 건너뜀")

    return results


def main() -> None:
    print("="*60)
    print("  KYUNGSA — 전체 API 연결 테스트")
    print("="*60)

    separator("API 키 상태 확인")
    check_key("PUBLIC_DATA_API_KEY", settings.PUBLIC_DATA_API_KEY)
    print(f"  CODEF_SERVICE_TYPE: {settings.CODEF_SERVICE_TYPE}")
    check_key("CODEF_SANDBOX_CLIENT_ID", settings.CODEF_SANDBOX_CLIENT_ID)
    check_key("CODEF_DEMO_CLIENT_ID", settings.CODEF_DEMO_CLIENT_ID)
    check_key("CODEF_CLIENT_ID", settings.CODEF_CLIENT_ID)
    check_key("CODEF_PUBLIC_KEY", settings.CODEF_PUBLIC_KEY)
    check_key("KAKAO_REST_API_KEY", settings.KAKAO_REST_API_KEY)
    check_key("VWORLD_API_KEY", settings.VWORLD_API_KEY)

    all_results: dict[str, bool] = {}

    # 공공 데이터 API
    all_results.update(test_public_apis())

    # CODEF API
    all_results.update(test_codef_apis())

    # 카카오 + Vworld
    all_results.update(test_geo_apis())

    # 최종 요약
    separator("최종 결과 요약")
    if not all_results:
        print("  테스트된 API가 없습니다. .env 키를 확인하세요.")
        return

    for name, ok in all_results.items():
        status = "✅ 성공" if ok else "❌ 실패"
        print(f"  {name}: {status}")

    success = sum(1 for v in all_results.values() if v)
    total = len(all_results)
    print(f"\n  총 {total}개 중 {success}개 성공, {total - success}개 실패")


if __name__ == "__main__":
    main()
