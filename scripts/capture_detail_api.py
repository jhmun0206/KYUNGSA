"""Level 2/3 실제 API 응답 캡처: 브라우저 fetch()로 직접 호출

Playwright 브라우저 세션 내에서 fetch()를 실행하여
상세/기일내역 등의 API 응답을 캡처한다.
(브라우저 세션이므로 WAF 쿠키 자동 포함)

실행: python scripts/capture_detail_api.py
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
    print("  Level 2/3 API 직접 호출 캡처")
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

        # 1. 메인 페이지 로드 (세션 확립)
        print("\n1. 메인 페이지 로드...")
        page.goto(
            f"{BASE_URL}/pgj/index.on",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(2)

        # 2. 물건상세검색 메뉴 클릭 + 검색
        print("2. 검색 실행...")
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

        search_resp = resp_info.value
        search_json = search_resp.json()
        items = search_json.get("data", {}).get("dlt_srchResult", [])
        print(f"  검색 결과: {len(items)}건")

        if not items:
            print("  결과 없음 — 종료")
            browser.close()
            return

        # 첫 번째 물건의 핵심 정보 추출
        first = items[0]
        sa_no = first.get("saNo", "")
        bo_cd = first.get("boCd", "")
        maemul_ser = first.get("maemulSer", "")
        srn_sa_no = first.get("srnSaNo", "")

        print(f"\n  대상 물건:")
        print(f"    사건번호: {srn_sa_no}")
        print(f"    saNo: {sa_no}")
        print(f"    법원코드: {bo_cd}")
        print(f"    물건순서: {maemul_ser}")

        # 검색 결과 목록 항목 전체 저장 (참조용)
        save_json("first_item_raw.json", first)

        time.sleep(3)

        # 3. 브라우저 fetch()로 상세 API 직접 호출
        # 테스트할 엔드포인트 목록
        endpoints = [
            {
                "name": "detail_case_info",
                "desc": "물건 상세 (selectAuctnCsSrchRslt)",
                "url": f"{BASE_URL}/pgj/pgj15B/selectAuctnCsSrchRslt.on",
                "payload": {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ151F01",
                        "srchInfo": "",
                    }
                },
            },
            {
                "name": "detail_tong_info",
                "desc": "물건 통합상세 (selectAuctnTongSrchRslt)",
                "url": f"{BASE_URL}/pgj/pgj15B/selectAuctnTongSrchRslt.on",
                "payload": {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ151F01",
                        "srchInfo": "",
                    }
                },
            },
            {
                "name": "detail_giil_naeyuk",
                "desc": "기일내역 (selectGiilNaeyuk)",
                "url": f"{BASE_URL}/pgj/pgj15B/selectGiilNaeyuk.on",
                "payload": {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ151F01",
                        "srchInfo": "",
                    }
                },
            },
            {
                "name": "detail_munggun",
                "desc": "문건/송달 (selectMungunSongdal)",
                "url": f"{BASE_URL}/pgj/pgj15B/selectMungunSongdal.on",
                "payload": {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ151F01",
                        "srchInfo": "",
                    }
                },
            },
            {
                "name": "detail_imchain",
                "desc": "임차인현황 (selectImchainHyunhwang)",
                "url": f"{BASE_URL}/pgj/pgj15B/selectImchainHyunhwang.on",
                "payload": {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ151F01",
                        "srchInfo": "",
                    }
                },
            },
        ]

        # 실제 WebSquare 페이지에서 사용하는 엔드포인트 탐색
        # (정확한 URL은 모르므로 여러 패턴 시도)
        alt_endpoints = [
            {
                "name": "detail_maemul_detail",
                "desc": "매물상세 (selectMaemulDtl)",
                "url": f"{BASE_URL}/pgj/pgj153/selectMaemulDtl.on",
                "payload": {
                    "dma_srchGdsDtlSrch": {
                        "csNo": sa_no,
                        "cortOfcCd": bo_cd,
                        "dspslGdsSeq": maemul_ser,
                        "pgmId": "PGJ153F01",
                        "srchInfo": "",
                    }
                },
            },
            {
                "name": "detail_case_dtl",
                "desc": "사건상세 (selectCsDtl)",
                "url": f"{BASE_URL}/pgj/pgj153/selectCsDtl.on",
                "payload": {
                    "dma_csInfo": {
                        "saNo": sa_no,
                        "boCd": bo_cd,
                        "maemulSer": maemul_ser,
                    }
                },
            },
            {
                "name": "detail_giil_list",
                "desc": "기일목록 (selectGiilList)",
                "url": f"{BASE_URL}/pgj/pgj153/selectGiilList.on",
                "payload": {
                    "dma_csInfo": {
                        "saNo": sa_no,
                        "boCd": bo_cd,
                        "maemulSer": maemul_ser,
                    }
                },
            },
        ]

        all_endpoints = endpoints + alt_endpoints

        print(f"\n3. API 직접 호출 ({len(all_endpoints)}개 엔드포인트)...")

        for ep in all_endpoints:
            print(f"\n  --- {ep['desc']} ---")
            print(f"  URL: {ep['url']}")
            time.sleep(2)

            try:
                result = page.evaluate(
                    """
                    async ([url, payload]) => {
                        try {
                            const resp = await fetch(url, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json;charset=UTF-8',
                                    'Accept': 'application/json',
                                },
                                body: JSON.stringify(payload),
                            });
                            const text = await resp.text();
                            return {
                                status: resp.status,
                                body: text.substring(0, 50000),
                            };
                        } catch(e) {
                            return {status: -1, body: e.message};
                        }
                    }
                    """,
                    [ep["url"], ep["payload"]],
                )

                status = result["status"]
                body = result["body"]
                print(f"  HTTP {status}, 본문: {len(body)} bytes")

                if status == 200 and body.strip():
                    try:
                        resp_json = json.loads(body)
                        # 구조 분석
                        if isinstance(resp_json, dict):
                            top_keys = list(resp_json.keys())
                            print(f"  최상위 키: {top_keys}")

                            if "data" in resp_json and isinstance(resp_json["data"], dict):
                                inner_keys = list(resp_json["data"].keys())
                                print(f"  data 키: {inner_keys}")
                                # data 내부의 각 키 타입/크기
                                for k in inner_keys:
                                    v = resp_json["data"][k]
                                    if isinstance(v, list):
                                        print(f"    {k}: list ({len(v)}건)")
                                    elif isinstance(v, dict):
                                        print(f"    {k}: dict ({len(v)}키)")
                                    else:
                                        val_str = str(v)
                                        if len(val_str) > 50:
                                            val_str = val_str[:50] + "..."
                                        print(f"    {k}: {val_str}")

                        save_json(f"{ep['name']}.json", resp_json)
                    except json.JSONDecodeError:
                        print(f"  JSON 파싱 실패, 시작: {body[:200]}")
                elif status >= 400:
                    print(f"  에러: {body[:300]}")
                elif status == -1:
                    print(f"  네트워크 오류: {body}")

            except Exception as e:
                print(f"  실패: {e}")

        browser.close()

    print(f"\n{'='*60}")
    print("  캡처 완료")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
