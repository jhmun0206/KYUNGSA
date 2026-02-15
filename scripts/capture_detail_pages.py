"""Level 2/3 실제 데이터 캡처: 상세 + 사건내역 + 문건

Playwright로 courtauction.go.kr에서:
1. 물건 목록 검색
2. 첫 번째 물건 클릭 → 상세 페이지 응답 캡처
3. 사건내역/기일내역 탭 → 응답 캡처
4. 문건/송달 탭 → 응답 캡처
5. 모든 응답을 scripts/captured_responses/에 저장

실행: python scripts/capture_detail_pages.py
"""

import json
import os
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.courtauction.go.kr"
OUTPUT_DIR = "scripts/captured_responses"


def save_json(filename: str, data: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = f"{OUTPUT_DIR}/{filename}"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size = len(json.dumps(data, ensure_ascii=False))
    print(f"  → {path} 저장 ({size:,} bytes)")


def main():
    print("=" * 60)
    print("  Level 2/3 실제 데이터 캡처")
    print("=" * 60)

    # 캡처된 모든 POST 응답 저장
    all_posts: dict[str, list[dict]] = {}

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

        # 모든 POST 응답 인터셉트
        def on_response(response):
            if response.request.method == "POST" and ".on" in response.url:
                try:
                    body = response.text()
                    if body.strip():
                        data = json.loads(body)
                        url_key = response.url.replace(BASE_URL, "")
                        if url_key not in all_posts:
                            all_posts[url_key] = []

                        req_data = None
                        try:
                            req_data = json.loads(response.request.post_data)
                        except Exception:
                            req_data = response.request.post_data

                        all_posts[url_key].append({
                            "status": response.status,
                            "response": data,
                            "request": req_data,
                        })
                        print(f"    [POST] {url_key} → HTTP {response.status}")
                except Exception:
                    pass

        page.on("response", on_response)

        # === 1. 메인 페이지 로드 ===
        print("\n1. 메인 페이지 로드...")
        page.goto(
            f"{BASE_URL}/pgj/index.on",
            wait_until="networkidle",
            timeout=30000,
        )
        time.sleep(2)

        # === 2. 물건상세검색 메뉴 ===
        print("2. 물건상세검색 메뉴 클릭...")
        page.locator("text=물건상세검색").first.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)

        # === 3. 검색 실행 ===
        print("3. 검색 실행...")
        search_btn = page.locator("#mf_wfm_mainFrame_btn_gdsDtlSrch")
        if not search_btn.is_visible():
            search_btn = page.locator("input[value='검색']").first

        with page.expect_response(
            lambda r: "searchControllerMain" in r.url,
            timeout=30000,
        ) as resp_info:
            search_btn.click()

        search_resp = resp_info.value
        print(f"  검색 응답: HTTP {search_resp.status}")

        search_data = search_resp.json()
        if "data" in search_data:
            inner = search_data["data"]
            items = inner.get("dlt_srchResult", [])
            print(f"  결과: {len(items)}건")
        else:
            items = []
            print("  결과 없음")

        time.sleep(3)

        # === 4. 첫 번째 물건 상세 클릭 ===
        print("\n4. 첫 번째 물건 상세 페이지 진입...")

        # 기존 POST 카운트 기록 (상세 클릭 후 새로 발생하는 요청만 식별)
        pre_click_counts = {k: len(v) for k, v in all_posts.items()}

        # GridView 행 클릭 시도 (여러 방법)
        detail_clicked = False

        # 방법 1: WebSquare GridView 첫 번째 행 더블클릭
        try:
            # w2grid 행 찾기
            grid_selectors = [
                "[id*='grd_rletSrchResult'] tr.w2grid_data_row",
                "[id*='grd_srchResult'] tr",
                "table.w2grid tbody tr.w2grid_data_row",
                "div.w2grid_cell_text",
            ]
            for sel in grid_selectors:
                row = page.locator(sel).first
                if row.is_visible(timeout=2000):
                    print(f"  GridView 행 발견: {sel}")
                    row.dblclick()
                    detail_clicked = True
                    break
        except Exception as e:
            print(f"  GridView 방법 실패: {e}")

        # 방법 2: JavaScript로 직접 호출
        if not detail_clicked:
            print("  JS moveDtlPage 시도...")
            try:
                page.evaluate("""
                    () => {
                        try {
                            // WebSquare 메인 프레임에서 moveDtlPage 호출
                            var wf = WebSquare.util.getComponentById('wfm_mainFrame');
                            if (wf && wf.getWindow) {
                                var w = wf.getWindow();
                                if (w.moveDtlPage) {
                                    w.moveDtlPage(0);
                                    return 'OK_moveDtlPage';
                                }
                                // wfm_srchResult 서브프레임
                                var subWf = w.WebSquare.util.getComponentById('wfm_srchResult');
                                if (subWf && subWf.getWindow && subWf.getWindow().moveDtlPage) {
                                    subWf.getWindow().moveDtlPage(0);
                                    return 'OK_sub_moveDtlPage';
                                }
                            }
                            return 'FAIL_no_function';
                        } catch(e) {
                            return 'FAIL_' + e.message;
                        }
                    }
                """)
                detail_clicked = True
            except Exception as e:
                print(f"  JS 호출 실패: {e}")

        if detail_clicked:
            # 상세 페이지 응답 대기 (여러 POST 요청이 발생할 수 있음)
            print("  응답 대기 (8초)...")
            time.sleep(8)

            # 새로 발생한 POST 요청 확인
            new_posts = {}
            for url_key, entries in all_posts.items():
                prev = pre_click_counts.get(url_key, 0)
                if len(entries) > prev:
                    new_posts[url_key] = entries[prev:]

            print(f"\n  상세 진입 후 새 POST 요청: {len(new_posts)}개")
            for url_key, entries in new_posts.items():
                for entry in entries:
                    resp_data = entry["response"]
                    # 최상위 키 출력
                    if isinstance(resp_data, dict):
                        top_keys = list(resp_data.keys())
                        if "data" in resp_data and isinstance(resp_data["data"], dict):
                            inner_keys = list(resp_data["data"].keys())
                            print(f"    {url_key}: top={top_keys}, data={inner_keys}")
                        else:
                            print(f"    {url_key}: keys={top_keys}")

            # 상세 응답 저장
            for url_key, entries in new_posts.items():
                safe_name = url_key.replace("/", "_").strip("_")
                for i, entry in enumerate(entries):
                    suffix = f"_{i}" if len(entries) > 1 else ""
                    save_json(f"detail_{safe_name}{suffix}.json", entry)

        # === 5. 사건내역 / 기일내역 탭 시도 ===
        print("\n5. 사건내역/기일내역 탭 시도...")
        pre_tab_counts = {k: len(v) for k, v in all_posts.items()}

        tab_selectors = [
            "text=기일내역",
            "text=사건내역",
            "[id*='tab_giilNaeyuk']",
            "[id*='tab_sajunNaeyuk']",
            "text=기일",
        ]
        tab_clicked = False
        for sel in tab_selectors:
            try:
                tab = page.locator(sel).first
                if tab.is_visible(timeout=2000):
                    print(f"  탭 발견: {sel}")
                    tab.click()
                    tab_clicked = True
                    time.sleep(5)
                    break
            except Exception:
                continue

        if not tab_clicked:
            # JS로 탭 전환 시도
            print("  JS 탭 전환 시도...")
            try:
                result = page.evaluate("""
                    () => {
                        try {
                            var wf = WebSquare.util.getComponentById('wfm_mainFrame');
                            if (wf && wf.getWindow) {
                                var w = wf.getWindow();
                                // 탭 컴포넌트 찾기
                                var tabIds = ['tab_giilNaeyuk', 'tab_sajunNaeyuk',
                                              'tabGiilNaeyuk', 'tabSajunNaeyuk'];
                                for (var id of tabIds) {
                                    try {
                                        var tab = w.WebSquare.util.getComponentById(id);
                                        if (tab) {
                                            tab.click();
                                            return 'OK_' + id;
                                        }
                                    } catch(e) {}
                                }
                                return 'NO_TAB_FOUND';
                            }
                            return 'NO_FRAME';
                        } catch(e) {
                            return 'FAIL_' + e.message;
                        }
                    }
                """)
                print(f"  JS 결과: {result}")
                time.sleep(5)
            except Exception as e:
                print(f"  JS 탭 실패: {e}")

        # 사건내역 새 POST 확인
        new_tab_posts = {}
        for url_key, entries in all_posts.items():
            prev = pre_tab_counts.get(url_key, 0)
            if len(entries) > prev:
                new_tab_posts[url_key] = entries[prev:]

        if new_tab_posts:
            print(f"  탭 클릭 후 새 POST: {len(new_tab_posts)}개")
            for url_key, entries in new_tab_posts.items():
                safe_name = url_key.replace("/", "_").strip("_")
                for i, entry in enumerate(entries):
                    suffix = f"_{i}" if len(entries) > 1 else ""
                    save_json(f"history_{safe_name}{suffix}.json", entry)
        else:
            print("  탭 클릭 후 새 POST 없음")

        # === 6. 페이지 전체 HTML 덤프 (디버깅) ===
        print("\n6. 현재 페이지 HTML 덤프...")
        try:
            html_content = page.content()
            html_path = f"{OUTPUT_DIR}/detail_page_full.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"  → {html_path} ({len(html_content):,} bytes)")
        except Exception as e:
            print(f"  HTML 덤프 실패: {e}")

        # === 7. 팝업 확인 ===
        print("\n7. 팝업 페이지 확인...")
        all_pages = context.pages
        print(f"  열린 페이지: {len(all_pages)}개")
        for i, pg in enumerate(all_pages):
            print(f"    [{i}] {pg.url[:80]}...")
            if i > 0:
                # 팝업 페이지의 HTML 저장
                popup_html = pg.content()
                popup_path = f"{OUTPUT_DIR}/popup_page_{i}.html"
                with open(popup_path, "w", encoding="utf-8") as f:
                    f.write(popup_html)
                print(f"    → {popup_path} ({len(popup_html):,} bytes)")

        # === 8. 전체 캡처 요약 ===
        print(f"\n{'='*60}")
        print(f"  전체 캡처 요약 ({len(all_posts)}개 엔드포인트)")
        print(f"{'='*60}")
        for url_key, entries in sorted(all_posts.items()):
            for entry in entries:
                resp = entry["response"]
                size = len(json.dumps(resp, ensure_ascii=False))
                if isinstance(resp, dict) and "data" in resp:
                    inner = resp.get("data", {})
                    if isinstance(inner, dict):
                        keys = list(inner.keys())[:5]
                        print(f"  [{entry['status']}] {url_key} ({size:,}b) data_keys={keys}")
                    else:
                        print(f"  [{entry['status']}] {url_key} ({size:,}b)")
                else:
                    top = list(resp.keys())[:5] if isinstance(resp, dict) else type(resp).__name__
                    print(f"  [{entry['status']}] {url_key} ({size:,}b) keys={top}")

        browser.close()

    print("\n=== 완료 ===")


if __name__ == "__main__":
    main()
