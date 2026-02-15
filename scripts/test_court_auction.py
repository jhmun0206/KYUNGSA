"""대법원 경매정보 크롤러 실제 사이트 테스트 (수동 실행용)

courtauction.go.kr에 실제 HTTP 요청을 보내 크롤러 동작을 검증.
실행: python scripts/test_court_auction.py (프로젝트 루트에서)

※ 요청 간격 3초 이상 유지. 캡차 감지 시 자동 중단.
"""

import json
import sys
import os

# backend/app을 import 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.crawler.court_auction import (
    CourtAuctionClient,
    CourtAuctionError,
    CaptchaDetectedError,
)


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main() -> None:
    print("=" * 60)
    print("  KYUNGSA — 대법원 경매정보 크롤러 실제 사이트 테스트")
    print("=" * 60)

    results: dict[str, bool] = {}
    client = CourtAuctionClient()

    # === 1. 세션 초기화 ===
    separator("1. 세션 초기화")
    try:
        client._init_session()
        cookies = client._cookies
        print(f"  쿠키 {len(cookies)}개 획득:")
        for key, value in cookies.items():
            print(f"    {key}: {value[:20]}...")
        results["세션초기화"] = len(cookies) > 0
    except Exception as e:
        print(f"  실패: {e}")
        results["세션초기화"] = False
        print("\n  ⚠️ 세션 초기화 실패 — 이후 테스트 불가")
        _print_summary(results)
        return

    # === 2. 물건 목록 검색 (서울중앙지방법원) ===
    separator("2. 물건 목록 검색 (서울중앙지방법원)")
    first_item = None
    raw_items = None
    try:
        items = client.search_cases(court_code="B000210", page_no=1, page_size=5)
        print(f"  결과: {len(items)}건")
        if items:
            first_item = items[0]
            print(f"  --- 첫 번째 물건 ---")
            print(f"    사건번호: {first_item.case_number}")
            print(f"    법원: {first_item.court}")
            print(f"    소재지: {first_item.address}")
            print(f"    용도: {first_item.property_type}")
            print(f"    감정가: {first_item.appraised_value:,}원")
            print(f"    최저가: {first_item.minimum_bid:,}원")
            print(f"    매각기일: {first_item.auction_date}")
            print(f"    상태: {first_item.status}")
            print(f"    회차: {first_item.bid_count}")

            if len(items) > 1:
                print(f"\n  --- 두 번째 물건 ---")
                print(f"    사건번호: {items[1].case_number}")
                print(f"    소재지: {items[1].address}")
                print(f"    감정가: {items[1].appraised_value:,}원")
                print(f"    최저가: {items[1].minimum_bid:,}원")

        results["물건목록검색"] = len(items) > 0
    except CaptchaDetectedError:
        print("  ❌ 캡차 감지 — 테스트 중단")
        results["물건목록검색"] = False
        _print_summary(results)
        return
    except CourtAuctionError as e:
        print(f"  실패: [{e.error_type}] {e}")
        results["물건목록검색"] = False
    except Exception as e:
        print(f"  실패: {e}")
        results["물건목록검색"] = False

    # === 3. RAW 응답 확인 (디버깅) ===
    separator("3. RAW JSON 응답 (디버깅)")
    try:
        from app.services.crawler.court_auction import SEARCH_URL
        payload = {
            "dma_pageInfo": {
                "pageNo": 1,
                "pageSize": 1,
                "bfPageNo": "",
                "startRowNo": "",
                "totalCnt": "",
                "totalYn": "Y",
                "groupTotalCount": "",
            },
            "dma_srchGdsDtlSrchInfo": {
                "cortOfcCd": "B000210",
                "bidDvsCd": "000331",
                "mvprpRletDvsCd": "00031R",
                "cortAuctnSrchCondCd": "0004601",
                "pgmId": "PGJ151F01",
                "cortStDvs": "1",
                "statNum": 1,
                "notifyLoc": "off",
                "rprsAdongSdCd": "",
                "rprsAdongSggCd": "",
                "rprsAdongEmdCd": "",
                "rdnmSdCd": "",
                "rdnmSggCd": "",
                "rdnmNo": "",
                "lclDspslGdsLstUsgCd": "",
                "mclDspslGdsLstUsgCd": "",
                "sclDspslGdsLstUsgCd": "",
                "cortAuctnMbrsId": "",
                "bidBgngYmd": "",
                "bidEndYmd": "",
                "aeeEvlAmtMin": "",
                "aeeEvlAmtMax": "",
                "lwsDspslPrcRateMin": "",
                "lwsDspslPrcRateMax": "",
                "flbdNcntMin": "",
                "flbdNcntMax": "",
                "objctArDtsMin": "",
                "objctArDtsMax": "",
                "lafjOrderBy": "",
                "csNo": "",
                "dspslDxdyYmd": "",
                "lwsDspslPrcMin": "",
                "lwsDspslPrcMax": "",
                "sideDvsCd": "",
                "jdbnCd": "",
                "rletDspslSpcCondCd": "",
            },
        }
        raw_data = client._post(SEARCH_URL, payload)
        raw_str = json.dumps(raw_data, ensure_ascii=False, indent=2)
        if len(raw_str) > 2000:
            print(f"  (전체 {len(raw_str)}자 중 2000자만 표시)")
            print(raw_str[:2000] + "\n  ...")
        else:
            print(raw_str)

        # RAW 데이터에서 첫 번째 물건의 키 출력
        items = raw_data.get("dlt_srchResult", [])
        if items:
            print(f"\n  첫 번째 물건 필드 ({len(items[0])}개):")
            for k in sorted(items[0].keys())[:20]:
                print(f"    {k}: {items[0][k]}")
        results["RAW응답확인"] = True
    except CaptchaDetectedError:
        print("  ❌ 캡차 감지 — 테스트 중단")
        results["RAW응답확인"] = False
        _print_summary(results)
        return
    except Exception as e:
        print(f"  실패: {e}")
        results["RAW응답확인"] = False

    # === 4. 전체 5건 수집 테스트 ===
    separator("4. 전체 5건 수집 (서울중앙)")
    try:
        all_items = client.search_cases(court_code="B000210", page_no=1, page_size=5)
        print(f"  수집 건수: {len(all_items)}")
        for i, item in enumerate(all_items):
            print(f"\n  [{i+1}] {item.case_number}")
            print(f"      법원: {item.court}")
            print(f"      소재지: {item.address[:40]}...")
            print(f"      용도: {item.property_type}")
            print(f"      감정가: {item.appraised_value:,}원")
            print(f"      최저가: {item.minimum_bid:,}원")
            print(f"      매각기일: {item.auction_date}")
            print(f"      회차: {item.bid_count}")
        results["5건수집"] = len(all_items) >= 5
    except CaptchaDetectedError:
        print("  ❌ 캡차 감지")
        results["5건수집"] = False
    except Exception as e:
        print(f"  실패: {e}")
        results["5건수집"] = False

    # === 최종 요약 ===
    _print_summary(results)


def _print_summary(results: dict[str, bool]) -> None:
    """최종 결과 출력"""
    separator("최종 결과 요약")
    if not results:
        print("  테스트된 항목이 없습니다.")
        return

    for name, ok in results.items():
        status = "✅ 성공" if ok else "❌ 실패"
        print(f"  {name}: {status}")

    success = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  총 {total}개 중 {success}개 성공, {total - success}개 실패")


if __name__ == "__main__":
    main()
