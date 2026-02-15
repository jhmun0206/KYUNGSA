"""상세 API 전체 응답 캡처 (selectAuctnCsSrchRslt.on)

selectAuctnCsSrchRslt.on이 물건 상세 데이터를 JSON으로 반환함을 확인.
이 스크립트는 전체 응답을 캡처하여 구조를 분석한다.

실행: python scripts/capture_detail_full.py
"""

import json
import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.courtauction.go.kr"
OUTPUT_DIR = "scripts/captured_responses"


def save_json(filename: str, data) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = f"{OUTPUT_DIR}/{filename}"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size = len(json.dumps(data, ensure_ascii=False))
    print(f"  → {path} ({size:,} bytes)")


def main():
    print("=" * 60)
    print("  상세 API 전체 응답 캡처")
    print("=" * 60)

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

        # 1. 세션 확립 + 검색
        print("\n1. 세션 확립 + 검색...")
        page.goto(f"{BASE_URL}/pgj/index.on", wait_until="networkidle", timeout=30000)
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
        ) as resp_info:
            search_btn.click()

        search_json = resp_info.value.json()
        items = search_json.get("data", {}).get("dlt_srchResult", [])
        print(f"  검색 결과: {len(items)}건")

        if not items:
            browser.close()
            return

        first = items[0]
        sa_no = first.get("saNo", "")
        bo_cd = first.get("boCd", "")
        maemul_ser = first.get("maemulSer", "")
        print(f"  대상: {first.get('srnSaNo', '')} (saNo={sa_no}, boCd={bo_cd}, ser={maemul_ser})")
        time.sleep(3)

        # 2. page.expect_response로 상세 API 호출 (전체 응답 캡처)
        print("\n2. 상세 API 호출 (expect_response)...")
        detail_url = f"{BASE_URL}/pgj/pgj15B/selectAuctnCsSrchRslt.on"
        payload = {
            "dma_srchGdsDtlSrch": {
                "csNo": sa_no,
                "cortOfcCd": bo_cd,
                "dspslGdsSeq": maemul_ser,
                "pgmId": "PGJ151F01",
                "srchInfo": "",
            }
        }

        # page.evaluate + fetch로 요청 발생시키면서 expect_response로 전체 응답 캡처
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
                [detail_url, payload],
            )

        detail_resp = detail_resp_info.value
        print(f"  HTTP {detail_resp.status}")

        detail_json = detail_resp.json()
        print(f"  최상위 키: {list(detail_json.keys())}")
        save_json("detail_response_full.json", detail_json)

        # 구조 분석
        if "data" in detail_json:
            data = detail_json["data"]
            print(f"\n  data 키: {list(data.keys())}")

            if "dma_result" in data:
                dma = data["dma_result"]
                print(f"\n  dma_result 키: {list(dma.keys())}")

                # 각 서브 키의 구조
                for key in dma:
                    val = dma[key]
                    if isinstance(val, dict):
                        print(f"\n  === {key} (dict, {len(val)}개 필드) ===")
                        for k, v in list(val.items())[:15]:
                            v_str = str(v)[:60]
                            print(f"    {k}: {v_str}")
                        if len(val) > 15:
                            print(f"    ... (총 {len(val)}개)")
                    elif isinstance(val, list):
                        print(f"\n  === {key} (list, {len(val)}건) ===")
                        if val:
                            first_item = val[0]
                            if isinstance(first_item, dict):
                                for k, v in list(first_item.items())[:10]:
                                    v_str = str(v)[:60]
                                    print(f"    {k}: {v_str}")
                                if len(first_item) > 10:
                                    print(f"    ... (총 {len(first_item)}개 필드)")
                    else:
                        print(f"\n  === {key}: {str(val)[:60]} ===")

            # dma_result 외의 다른 키 확인
            for key in data:
                if key == "dma_result":
                    continue
                val = data[key]
                if isinstance(val, dict):
                    print(f"\n  === data.{key} (dict, {len(val)}키) ===")
                    for k, v in list(val.items())[:5]:
                        print(f"    {k}: {str(v)[:60]}")
                elif isinstance(val, list):
                    print(f"\n  === data.{key} (list, {len(val)}건) ===")
                    if val and isinstance(val[0], dict):
                        for k, v in list(val[0].items())[:5]:
                            print(f"    {k}: {str(v)[:60]}")
                else:
                    print(f"\n  === data.{key}: {str(val)[:60]} ===")

        # 3. 다른 물건도 캡처 (비교용)
        if len(items) >= 3:
            print(f"\n\n3. 두 번째 물건 캡처 (비교용)...")
            second = items[2]
            sa_no2 = second.get("saNo", "")
            bo_cd2 = second.get("boCd", "")
            maemul_ser2 = second.get("maemulSer", "")
            print(f"  대상: {second.get('srnSaNo', '')} (saNo={sa_no2}, ser={maemul_ser2})")
            time.sleep(3)

            payload2 = {
                "dma_srchGdsDtlSrch": {
                    "csNo": sa_no2,
                    "cortOfcCd": bo_cd2,
                    "dspslGdsSeq": maemul_ser2,
                    "pgmId": "PGJ151F01",
                    "srchInfo": "",
                }
            }

            with page.expect_response(
                lambda r: "selectAuctnCsSrchRslt" in r.url,
                timeout=30000,
            ) as resp2_info:
                page.evaluate(
                    """
                    ([url, payload]) => {
                        fetch(url, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json;charset=UTF-8',
                                'Accept': 'application/json',
                            },
                            body: JSON.stringify(payload),
                        });
                    }
                    """,
                    [detail_url, payload2],
                )

            resp2 = resp2_info.value
            detail2_json = resp2.json()
            save_json("detail_response_2.json", detail2_json)
            print(f"  HTTP {resp2.status}, 저장 완료")

        browser.close()

    print(f"\n{'='*60}")
    print("  캡처 완료!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
