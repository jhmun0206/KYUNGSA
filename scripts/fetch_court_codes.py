"""법원코드 매핑 조회

selectCortOfcLst.on API를 호출하여 법원코드(B000210 등) ↔ 법원명 매핑 추출.

실행: python scripts/fetch_court_codes.py
"""

import json
import httpx

BASE_URL = "https://www.courtauction.go.kr"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

client = httpx.Client(timeout=30, follow_redirects=True)

# 세션 초기화
client.get(f"{BASE_URL}/pgj/index.on", headers={"User-Agent": UA})

# 부동산 법원목록
resp = client.post(
    f"{BASE_URL}/pgj/pgj002/selectCortOfcLst.on",
    json={"cortExecrOfcDvsCd": "00079B"},
    headers={
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
)
data = resp.json()

print("=== 부동산 경매 법원코드 ===")
print(f"JSON 키: {list(data.keys())}")

# 데이터 구조 파악 후 출력
if isinstance(data, dict) and "data" in data:
    courts = data["data"]
elif isinstance(data, list):
    courts = data
elif isinstance(data, dict):
    # 첫 번째 리스트 값 찾기
    for k, v in data.items():
        if isinstance(v, list):
            courts = v
            break
    else:
        courts = data

if isinstance(courts, list):
    print(f"법원 수: {len(courts)}")
    if courts:
        print(f"첫 번째 항목 키: {list(courts[0].keys()) if isinstance(courts[0], dict) else type(courts[0])}")
    for c in courts[:10]:
        if isinstance(c, dict):
            print(f"  {c}")
else:
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])

# 전체 저장
with open("scripts/captured_responses/court_codes.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("\n→ scripts/captured_responses/court_codes.json 저장")

client.close()
