"""E2E 파이프라인 검증: Playwright 브라우저 검색 → 파서 → Pydantic DTO

Level 1: 브라우저 검색 → 목록 파싱
Level 2: 상세 API 호출 → 상세/물건객체/감정평가 파싱
Level 3: 같은 상세 응답 → 사건내역(이력)/문건 존재여부 파싱

실행: python scripts/test_pipeline_e2e.py
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from playwright.sync_api import sync_playwright

from app.services.crawler.court_auction_parser import CourtAuctionParser
from app.models.auction import AuctionCaseListItem, AuctionCaseDetail


BASE_URL = "https://www.courtauction.go.kr"
DETAIL_URL = f"{BASE_URL}/pgj/pgj15B/selectAuctnCsSrchRslt.on"


def separator(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main() -> None:
    print("=" * 60)
    print("  KYUNGSA — E2E 파이프라인 검증 (Level 1/2/3)")
    print("=" * 60)

    results: dict[str, bool] = {}
    captured_data = None
    items_raw = []
    detail_data = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # === 1. Level 1: 브라우저 검색 ===
        separator("1. Level 1: 브라우저 검색")
        try:
            page.goto(
                f"{BASE_URL}/pgj/index.on",
                wait_until="networkidle",
                timeout=30000,
            )
            time.sleep(2)

            page.locator("text=물건상세검색").first.click()
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)

            search_btn = page.locator("#mf_wfm_mainFrame_btn_gdsDtlSrch")
            if not search_btn.is_visible():
                search_btn = page.locator("input[value='검색']").first

            with page.expect_response(
                lambda r: "searchControllerMain" in r.url,
                timeout=30000,
            ) as response_info:
                search_btn.click()

            search_resp = response_info.value
            response_json = search_resp.json()

            if isinstance(response_json, dict) and "data" in response_json:
                captured_data = response_json["data"]
            else:
                captured_data = response_json

            items_raw = captured_data.get("dlt_srchResult", [])
            print(f"  HTTP {search_resp.status}, 검색 결과: {len(items_raw)}건")

            results["L1_브라우저검색"] = len(items_raw) > 0
        except Exception as e:
            print(f"  실패: {e}")
            results["L1_브라우저검색"] = False
            browser.close()
            _print_summary(results)
            return

        # === 2. Level 1: 목록 파싱 + DTO 검증 ===
        separator("2. Level 1: 목록 파싱 + DTO 검증")
        parser = CourtAuctionParser()
        parsed_items: list[AuctionCaseListItem] = []
        try:
            parsed_items = parser.parse_list_response(captured_data)
            print(f"  파싱 결과: {len(parsed_items)}건")

            for i, item in enumerate(parsed_items[:3]):
                addr = item.address[:35] + "..." if len(item.address) > 35 else item.address
                print(f"  [{i+1}] {item.case_number} | {item.court} | {addr}")
                print(f"       감정가: {item.appraised_value:,} | 최저가: {item.minimum_bid:,} | 상태: {item.status}")

            dto = parsed_items[0]
            checks = {
                "case_number": bool(dto.case_number),
                "court": bool(dto.court),
                "address": bool(dto.address),
                "appraised_value > 0": dto.appraised_value > 0,
                "minimum_bid > 0": dto.minimum_bid > 0,
            }
            results["L1_파싱DTO"] = all(checks.values())
        except Exception as e:
            print(f"  실패: {e}")
            results["L1_파싱DTO"] = False

        # === 3. Level 2: 상세 API 호출 ===
        separator("3. Level 2: 상세 API 호출")
        if items_raw:
            first = items_raw[0]
            sa_no = first.get("saNo", "")
            bo_cd = first.get("boCd", "")
            maemul_ser = first.get("maemulSer", "")
            srn_sa_no = first.get("srnSaNo", "")
            print(f"  대상: {srn_sa_no} (saNo={sa_no}, boCd={bo_cd}, ser={maemul_ser})")

            time.sleep(3)  # rate limit 준수

            try:
                payload = {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ151F01",
                        "srchInfo": "",
                    }
                }

                with page.expect_response(
                    lambda r: "selectAuctnCsSrchRslt" in r.url,
                    timeout=30000,
                ) as detail_resp_info:
                    page.evaluate(
                        """
                        ([url, payload]) => {
                            fetch(url, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json;charset=UTF-8',
                                    'Accept': 'application/json',
                                    'submissionid': 'mf_wfm_mainFrame_sbm_selectAuctnCsSrchRslt',
                                    'sc-userid': 'SYSTEM',
                                },
                                body: JSON.stringify(payload),
                            });
                        }
                        """,
                        [DETAIL_URL, payload],
                    )

                detail_resp = detail_resp_info.value
                detail_json = detail_resp.json()
                print(f"  HTTP {detail_resp.status}")

                # data 래퍼 언래핑
                if isinstance(detail_json, dict) and "data" in detail_json:
                    detail_data = detail_json["data"]
                else:
                    detail_data = detail_json

                dma_keys = list(detail_data.get("dma_result", {}).keys())
                print(f"  dma_result 키: {dma_keys}")

                results["L2_상세API"] = "dma_result" in detail_data
            except Exception as e:
                print(f"  실패: {e}")
                import traceback
                traceback.print_exc()
                results["L2_상세API"] = False
        else:
            results["L2_상세API"] = False

        browser.close()

    # === 4. Level 2: 상세 파싱 검증 ===
    separator("4. Level 2: 상세 파싱 검증")
    if detail_data:
        try:
            detail = parser.parse_detail_response(detail_data)
            print(f"  사건번호: {detail.case_number}")
            print(f"  법원: {detail.court}")
            print(f"  감정가: {detail.appraised_value:,}원")
            print(f"  최저가: {detail.minimum_bid:,}원")
            print(f"  유찰횟수: {detail.failed_count}")
            print(f"  개시결정일: {detail.case_start_date}")
            print(f"  배당요구종기: {detail.distribution_demand_deadline}")
            print(f"  매각장소: {detail.sale_place}")
            print(f"  물건 수: {len(detail.property_objects)}개")
            if detail.property_objects:
                obj = detail.property_objects[0]
                print(f"    [1] {obj.building_name} {obj.building_detail} | 면적: {obj.area_m2}㎡")
            print(f"  감정평가 요점: {len(detail.appraisal_notes)}건")
            print(f"  매각기일 이력: {len(detail.auction_rounds)}건")
            print(f"  사진: {len(detail.photo_urls)}장")

            checks = {
                "case_number": bool(detail.case_number),
                "감정가 > 0": detail.appraised_value > 0,
                "최저가 > 0": detail.minimum_bid > 0,
                "물건객체 존재": len(detail.property_objects) > 0,
                "매각기일이력 존재": len(detail.auction_rounds) > 0,
            }
            print(f"\n  --- Level 2 필수 필드 검증 ---")
            for check_name, passed in checks.items():
                print(f"    {'✅' if passed else '❌'} {check_name}")

            results["L2_상세파싱"] = all(checks.values())
        except Exception as e:
            print(f"  실패: {e}")
            import traceback
            traceback.print_exc()
            results["L2_상세파싱"] = False
    else:
        results["L2_상세파싱"] = False

    # === 5. Level 3a: 사건내역 파싱 검증 ===
    separator("5. Level 3a: 사건내역 파싱")
    if detail_data:
        try:
            history = parser.parse_history_response(detail_data)
            print(f"  사건번호: {history.case_number}")
            print(f"  개시결정일: {history.case_start_date}")
            print(f"  배당요구종기: {history.distribution_demand_deadline}")
            print(f"  매각기일 이력: {len(history.rounds)}건")

            for r in history.rounds[:5]:
                winning = f", 낙찰가: {r.winning_bid:,}" if r.winning_bid else ""
                print(f"    {r.round_number}회 | {r.round_date} | 최저가: {r.minimum_bid:,} | {r.result}{winning}")

            checks = {
                "case_number": bool(history.case_number),
                "매각기일이력": len(history.rounds) > 0,
                "회차별 최저가": all(r.minimum_bid > 0 for r in history.rounds),
                "회차별 결과": all(bool(r.result) for r in history.rounds),
            }
            print(f"\n  --- Level 3a 필수 필드 검증 ---")
            for check_name, passed in checks.items():
                print(f"    {'✅' if passed else '❌'} {check_name}")

            results["L3a_사건내역"] = all(checks.values())
        except Exception as e:
            print(f"  실패: {e}")
            results["L3a_사건내역"] = False
    else:
        results["L3a_사건내역"] = False

    # === 6. Level 3b: 문건 존재여부 검증 ===
    separator("6. Level 3b: 문건 존재여부 파싱")
    if detail_data:
        try:
            docs = parser.parse_documents_response(detail_data)
            print(f"  사건번호: {docs.case_number}")
            print(f"  매각물건명세서: {'있음' if docs.has_specification else '없음'}")
            print(f"  감정평가서: {'있음' if docs.has_appraisal else '없음'}")
            print(f"  현황조사서: {'있음' if docs.has_status_report else '없음'}")
            if docs.specification_date:
                print(f"  명세서 작성일: {docs.specification_date}")

            results["L3b_문건존재"] = True  # 파싱 자체가 성공하면 OK
        except Exception as e:
            print(f"  실패: {e}")
            results["L3b_문건존재"] = False
    else:
        results["L3b_문건존재"] = False

    # === 7. 캡처 데이터 저장 ===
    separator("7. 캡처 데이터 저장")
    try:
        os.makedirs("scripts/captured_responses", exist_ok=True)

        if captured_data:
            with open("scripts/captured_responses/latest_search.json", "w", encoding="utf-8") as f:
                json.dump(captured_data, f, ensure_ascii=False, indent=2)
            print("  → latest_search.json 저장")

        if detail_data:
            # base64 사진 데이터 제거하여 경량화 저장
            detail_light = json.loads(json.dumps(detail_data))
            if "dma_result" in detail_light:
                for pic in detail_light["dma_result"].get("csPicLst", []):
                    if "picFile" in pic:
                        pic["picFile"] = "(base64 제거)"
            with open("scripts/captured_responses/latest_detail.json", "w", encoding="utf-8") as f:
                json.dump(detail_light, f, ensure_ascii=False, indent=2)
            print("  → latest_detail.json 저장 (base64 제거)")

        results["데이터저장"] = True
    except Exception as e:
        print(f"  실패: {e}")
        results["데이터저장"] = False

    # === 최종 요약 ===
    _print_summary(results)


def _print_summary(results: dict[str, bool]) -> None:
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
