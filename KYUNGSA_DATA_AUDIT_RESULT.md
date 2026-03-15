# KYUNGSA 데이터 파이프라인 전면 감사 결과

> 작성일: 2026-03-13
> 대상: backend 소스코드 + 홈서버 PostgreSQL DB 실측
> SQL 실행 DB: kyungsa_db (PostgreSQL 16, homeserver)

---

## 목차

1. [DB 현황 요약](#1-db-현황-요약)
2. [외부 API 연동 현황 — 수집 vs 미수집](#2-외부-api-연동-현황)
3. [DB 저장 vs 버리는 데이터](#3-db-저장-vs-버리는-데이터)
4. [버그 및 데이터 품질 이슈](#4-버그-및-데이터-품질-이슈)
5. [예측 정확도 분석](#5-예측-정확도-분석)
6. [점수 산출 체계 분석](#6-점수-산출-체계-분석)
7. [개선 우선순위 제안](#7-개선-우선순위-제안)

---

## 1. DB 현황 요약

### 1-1. auctions 테이블 상태 분포

```sql
-- 결과 (2026-03-13 실측)
status      | count
------------|-------
매각         | 10,698  (76.1%)
진행         |  3,357  (23.9%)
'' (빈값)    |      1
```

**총 14,056건** 저장. 진행 물건 3,357건이 현재 운영 대상.

### 1-2. 좌표(coordinates) 현황

```sql
-- 조건별 분류
x/y 좌표 있음  :  4,068건  (28.9%)
b_code만 있음  :  8,388건  (59.7%)
기타/null      :  1,600건  (11.4%)
```

**핵심 발견**: 전체의 71%가 위경도 좌표 없음.
원인: 카카오 geocode가 `b_code`(법정동코드)만 반환하는 경우 x/y가 저장되지 않음.
진행 물건(3,357건)의 경우 층+호 포함 주소 99.4%가 좌표 수집 성공 → 신규 수집분은 양호.
8,388건의 b_code만 있는 레코드는 대부분 매각 완료된 구형 데이터.

### 1-3. 진행 물건 주소유형별 좌표 성공률

```sql
주소유형        | 건수  | 좌표성공 | 성공률
---------------|------|---------|------
층+호 포함      | 2,806 | 2,789   | 99.4%
도로명(계단식)   |    55 |    54   | 98.2%
기타            |   474 |   386   | 81.4%
도로명(단순)     |    22 |    17   | 77.3%
```

### 1-4. building_info 필드 커버리지

```
전체 building_info 보유: 14,056건 (100%)

필드명              | 존재 건수 | 비율
-------------------|----------|------
build_year          |  2,294   | 16.3%
ground_floors       |  2,284   | 16.2%
units_count         |  2,086   | 14.8%
total_area          |  2,306   | 16.4%
units (배열, 비어있음)|      0   |  0.0%
```

**핵심 발견**: `units` 배열이 **전체 0건** — `fetch_building_units()` API는 구현되어 있으나
기존 수집 데이터가 이 기능 추가 이전 것이므로 `--force-update` 재수집 필요.

또한 build_year 등 필드 커버리지 16%는 낮아 보이지만,
`regstrGbCd=1` (일반건물) 레코드와 `regstrGbCd=2` (집합건물)의 데이터 구조 차이 때문.
집합건물은 건물 단위 정보(build_year 등)가 표제부에만 있고 전유부에는 없음.

### 1-5. market_price_info 수집 현황

```sql
상태                        | 건수
---------------------------|------
avg_price_per_m2 있음 (정상) | 2,757  (19.6%)
avg_price_per_m2 없음 (부분) |10,744  (76.4%)
market_price_info 없음      |   555   (4.0%)
```

**핵심 발견**: 76.4%가 avg_price_per_m2 NULL → 시세 대비 점수 산출 불가.
원인: `_extract_lawd_cd()`가 서울 25개구만 지원 (`SIGUNGU_CODE_MAP`). 서울 외 지역은 lawd_cd 추출 불가 → API 미호출.

### 1-6. rent_price_info 수집률 (property_type별)

```sql
property_type | 전체 | 수집 | 미수집 | 수집률
-------------|------|------|--------|------
다세대         | 1,049 |  819 |   230 | 78.1%
빈값           |   663 |  503 |   160 | 75.9%  ← property_type 빈값 문제
오피스텔        |   329 |  188 |   141 | 57.1%
아파트         |   132 |   80 |    52 | 60.6%
기타 유형      |  ~900 | ~변동 |      |
```

### 1-7. occupancy(현황조사서) 분석 현황

```sql
occupancy_status | 건수
----------------|------
분석완료          |  406  (12.1%)
분석대기          | 2,951 (87.9%)
```

**진행 물건 3,357건 중 12.1%만 현황조사서 분석 완료.**
현황조사서 HTTP 550 오류 및 속도 제한이 주요 원인.

### 1-8. scores 테이블 현황

```sql
전체 점수 보유: 13,074건 (93.0%)
actual_winning_ratio 있음: 230건 (1.8%) ← 낙찰가율 백테스트 가능 데이터
predicted_winning_ratio 있음: 13,074건 (100%)
avg_abs_prediction_error: 0.2142 (21.4%)
```

### 1-9. 예측오차 물건유형별

```sql
property_category | 건수 | avg_abs_error
-----------------|------|-------------
꼬마빌딩           |  139 |    0.224
아파트             |   86 |    0.203
토지               |    5 |    0.144
```

### 1-10. property_type 빈값 현황

```sql
property_type 빈값: 663건 (4.7%)
```

이 레코드들의 detail JSONB에도 `auction_rounds[0].property_type = NULL`.
원인: 낙찰결과 수집 경로(`selectDspslSchdRsltSrch.on`)로 입력된 데이터로,
대법원 매각결과 API 응답에 물건용도(property_type) 필드가 없거나 매핑 누락.

### 1-11. detail JSONB 이중 스키마

```sql
총 54개 키 발견 (두 스키마 합산)

스키마 A (10,014건): maeGiil, maemulSer, dspslGdsCd, ... (낙찰결과/단순 포맷)
스키마 B  (4,042건): auction_rounds, specification_remarks, building_info_raw, ... (풀 포맷)
```

스키마 B가 `AuctionCaseDetail.model_dump()` 형식. `auction_orm_to_detail()`에서
스키마 A 레코드는 `ValidationError` → fallback(정규화 컬럼 최소 복원) 경로 진행.

### 1-12. building_info use_approve_date 연도 분포

```
2021년: 389건, 2020년: 344건 최다
2000년 이전: 상당수 존재
```

---

## 2. 외부 API 연동 현황

### 2-1. 수집하는 API (현재 파이프라인 연결)

| API | 클라이언트 | 수집 데이터 | 저장 필드 |
|-----|-----------|-----------|---------|
| 카카오 Geocode | `GeoClient.geocode()` | 주소 → {x, y, b_code, main_address_no, sub_address_no} | `coordinates` JSONB |
| 카카오 카테고리 | `GeoClient.search_nearby_category()` | SW8(지하철), SC4(학교), MT1(마트), CS2(편의점), HP8(병원) | **버림** (아래 3-2 참고) |
| Vworld LT_C_UQ111 | `GeoClient.fetch_land_use()` | 용도지역명 목록 | `land_use_info` JSONB |
| Vworld 주소검색 | `GeoClient.search_address()` | 지번 주소 검색 (geocode fallback) | 내부 처리 후 `coordinates` |
| data.go.kr 건축물대장 | `PublicDataClient.fetch_building_register()` | 주용도/구조/연면적/위반/세대수/사용승인일 | `building_info` JSONB |
| data.go.kr 전유부 | `PublicDataClient.fetch_building_units()` | 호실별 면적 (집합건물) | `building_info.units` (현재 빈 배열) |
| data.go.kr 아파트거래 | `PublicDataClient.fetch_apt_trade()` | 아파트 실거래가 | `market_price_info` JSONB |
| data.go.kr 연립거래 | `PublicDataClient.fetch_rh_rent()` | 다세대/연립 월세 | `rent_price_info` JSONB |
| data.go.kr 오피스텔거래 | `PublicDataClient.fetch_office_rent()` | 오피스텔 월세 | `rent_price_info` JSONB |
| data.go.kr 아파트전월세 | `PublicDataClient.fetch_apt_rent()` | 아파트 전월세 | `rent_price_info` JSONB |
| 대법원 경매정보 | `CourtAuctionClient` | 목록/상세/기일내역/현황조사서 | `detail` JSONB + 정규화 컬럼 |
| CODEF | `RegistryPipeline` | 등기부등본 분석 | `registry_events/analysis` |

### 2-2. API 있지만 미연결 (public_api.py 구현 완료, enricher.py 미호출)

| API 함수명 | 수집 가능 데이터 | 활용 가능성 |
|-----------|----------------|-----------|
| `fetch_commercial_trade()` | 상업업무용 실거래가 (오피스/상가/꼬마빌딩) | ★★★ 꼬마빌딩 시세 산출에 필수 |
| `fetch_land_price()` | 개별공시지가 (토지) | ★★ 토지 가격 매력도 점수 기반 |

### 2-3. 지역 제한 — 서울 외 시세 미수집

```python
# enricher.py _extract_lawd_cd()
SIGUNGU_CODE_MAP = {
    "강남구": "11680", "강동구": "11740", ... # 서울 25개구만
}
# 서울 외 → lawd_cd 추출 불가 → fetch_*_trade/rent 미호출 → market_price_info/rent_price_info null
```

전체 14,056건 중 서울 물건 비율 확인 필요. 서울 외(인천, 경기, 부산 등) 물건은
시세 데이터 없이 할인율 기반으로만 price_score 산출.

---

## 3. DB 저장 vs 버리는 데이터

### 3-1. save_enriched_case() 저장 매핑

```python
# converters.py save_enriched_case() — 저장하는 데이터
auction.coordinates       = enriched.coordinates       # x/y + b_code
auction.building_info     = enriched.building.model_dump()
auction.land_use_info     = enriched.land_use.model_dump()
auction.market_price_info = enriched.market_price.model_dump()
auction.rent_price_info   = enriched.rent_price.model_dump()
auction.detail            = enriched.case.model_dump(mode="json")  # 전체 대법원 DTO
```

### 3-2. 수집했지만 버리는 데이터 — location_data ★★★ 핵심 이슈

```python
# enricher.py enrich() — location_data 수집
enriched.location_data = self._fetch_location_data(x, y)
# → LocationData(nearest_station_m, station_count_1km, nearest_school_m, amenity_count_500m, ...)

# converters.py save_enriched_case() — location_data 저장 코드 없음!
# Auction ORM — location_data 컬럼 없음!
```

**결과:**
- `_fetch_location_data()` 호출 → 카카오 API 5회 호출 → LocationData 계산
- `save_enriched_case()` 에서 저장하지 않음 → **매 배치마다 재계산 후 버림**
- `--rescore-db` 모드에서는 DB에서 복원 → `location_data = None` → `LocationScorer.score()` returns `None`
- API 응답: `location_data: null`, `location_score: null` (항상)

**수정 방법**: Auction ORM에 `location_data: Mapped[dict | None]` 컬럼 추가 + `save_enriched_case()`에 저장 로직 추가 + Alembic migration

### 3-3. Score 테이블 저장 매핑 (_save_score)

```python
# batch_collector.py _save_score() — TotalScoreResult → Score ORM
score_orm = Score(
    legal_score     = ts.legal_score,    # 등기부 기반 (CODEF 완료건만)
    price_score     = ts.price_score,    # discount + market + appraisal
    location_score  = ts.location_score, # ← LocationData 기반 (현재 항상 None)
    occupancy_score = ts.occupancy_score,# 현황조사서 기반 (12.1% 커버)
    total_score     = ts.total_score,
    sub_scores      = ts.weights_used,   # 재정규화된 가중치 dict (세부 점수 아님)
    ...
)
```

---

## 4. 버그 및 데이터 품질 이슈

### BUG-01: exclusive_area_m2 필드명 오류 ★★★

**위치**: `backend/app/services/enricher.py:186`

```python
# 현재 (버그)
exclusive_area_m2=_safe_float(first.get("platArea", "")),
# platArea = 대지면적 (土地 면적), 전용면적이 아님!

# 올바른 필드 (건축물대장 API 응답 기준)
# 전용면적 = "exclusiveArea" 또는 "prvuseAr" (전용면적 항목)
```

**영향**:
- `PriceScorer._estimate_market_value()`: `area_m2 * avg_price_per_m2`로 추정 시세 계산
- 대지면적(platArea)이 전용면적보다 수 배 큰 경우 추정 시세 과대 → price_score 왜곡
- 아파트: platArea vs 전용면적 차이 극심 (예: 전용 84㎡ 아파트의 platArea는 전체 단지 대지 면적)

**수정 필요**: 건축물대장 API 실제 응답 필드명 확인 후 `exclusive_area_m2` → 실제 전용면적 필드로 교체.

### BUG-02: detail JSONB 이중 스키마로 인한 property_type 빈값 663건

**위치**: `backend/app/services/sale_result_collector.py` 또는 낙찰결과 수집 경로

**증상**:
- `auctions.property_type = ''` 663건
- `detail JSONB['auction_rounds'][0]['property_type'] = NULL`
- 스키마 A(10,014건): 낙찰결과 단순 포맷 — property_type 없음
- 스키마 B(4,042건): 풀 포맷 — property_type 있음

**영향**:
- `PriceScorer._is_residential()`: property_type 빈값 → False → 꼬마빌딩 곡선 적용
- `LocationScorer._classify_property()`: DEFAULT_CATEGORY(꼬마빌딩) 적용
- API 응답 `property_type: ""` → 프론트엔드 표시 오류

**수정 방법**: 낙찰결과 수집 후 `collect_full_case()`로 상세 재조회 또는 property_type 패치 스크립트.

### BUG-03: coordinates b_code 포맷 — x/y 없는 8,388건

**위치**: `backend/app/services/crawler/geo_client.py:geocode()`

**원인**: 카카오 API가 일부 주소에서 `x/y`를 반환하지 않고 `b_code`만 반환하는 경우가 있음.
또는 구버전 geocode 결과가 DB에 그대로 남아있는 경우.

**영향**:
- `_fetch_location_data()`: `x`, `y` 없으면 미호출 → location_data = None
- `fetch_land_use()`: x/y 없으면 미호출 → land_use_info = None
- Auction 카드/지도에서 좌표 미표시

**현황**: 대부분 매각 완료 데이터(10,698건) → 실운영 영향 제한적.
진행 물건(3,357건) 좌표 성공률 99.4%(층+호 포함) → 신규 수집 양호.

### BUG-04: rent_price_info 빈값 건 (property_type 빈값 → 잘못된 API 호출)

**위치**: `backend/app/services/enricher.py:_fetch_rent_price_info()`

```python
# 현재
if "아파트" in property_type:
    rent = fetch_apt_rent(...)
elif "오피스텔" in property_type:
    rent = fetch_office_rent(...)
elif any(x in property_type for x in ["다세대", "연립", "빌라"]):
    rent = fetch_rh_rent(...)
else:  # 빈값 또는 알 수 없는 유형
    rh + office 둘 다 호출 (fallback)
```

property_type 빈값(663건) → else 브랜치 → rh_rent + office_rent 호출.
이 중 lawd_cd가 있는 경우 수집 완료, 없으면 null → rent 수집률 75.9%.

---

## 5. 예측 정확도 분석

### 5-1. 현재 예측 방법 (rule_v1)

```python
# prediction_method: "rule_v1"
# 유찰 횟수 기반 통계적 낙찰가율 테이블
_PREDICTED_RATIO_TABLE = {
    0: 0.95,  # 신건 — 95%
    1: 0.85,  # 1회 유찰 — 85%
    2: 0.78,  # 2회 유찰 — 78%
    3: 0.72,  # 3회 이상 — 72%
}
```

### 5-2. 예측 오차 현황

| 구분 | 건수 | MAE |
|------|------|-----|
| 전체 | 230 | 21.4% |
| 꼬마빌딩 | 139 | 22.4% |
| 아파트 | 86 | 20.3% |
| 토지 | 5 | 14.4% |

**해석**: MAE 21.4%는 낙찰가율 예측 기준 매우 높음.
예) 최저가 5억 물건의 예측오차 범위: ±1.07억
rule_v1이 "유찰횟수만" 참조하므로 개별 물건 특성 미반영.

### 5-3. 실제 vs 예측 방향 편향 (백테스트 스크립트 결과 필요)

`scripts/backtest_scores.py` 실행으로 확인 가능:
- 낙관 편향 여부 (predicted > actual)
- 유찰횟수별 편향 방향
- 물건유형별 편향 패턴

---

## 6. 점수 산출 체계 분석

### 6-1. 4 Pillar 점수 현황

| Pillar | 산출기 | 데이터 소스 | 현재 커버리지 |
|--------|--------|-----------|------------|
| legal_score | `LegalScorer` | RegistryAnalysis (CODEF) | ~수십건 (CODEF 완료건만) |
| price_score | `PriceScorer` | AuctionCaseDetail + MarketPriceInfo | ~100% (데이터 품질 문제는 있음) |
| location_score | `LocationScorer` | LocationData (카카오 카테고리) | **0%** — DB 미저장으로 항상 null |
| occupancy_score | `OccupancyScorer` | OccupancyReport (현황조사서) | 12.1% |

### 6-2. location_score = 항상 null 상세 원인

```
enrich() 호출
  └─ _fetch_location_data(x, y) 호출
       └─ 카카오 카테고리 5종 API 호출 (SW8, SC4, MT1, CS2, HP8)
            └─ LocationData(nearest_station_m, amenity_count_500m, ...) 계산
                 └─ enriched.location_data = result  ← EnrichedCase에는 저장됨

save_enriched_case(db, enriched) 호출
  └─ coordinates, building, land_use, market_price, rent_price 저장
       └─ location_data 저장 없음 ← 컬럼/저장 로직 누락

이후 rescore_db() 또는 API 응답 생성 시:
  └─ auction_orm_to_enriched(orm)
       └─ location_data = None (DB에 없으므로)
            └─ LocationScorer.score(case, location_data=None) → None 반환
```

### 6-3. total_score 재정규화 메커니즘

```python
# TotalScorer
# 가용 pillar만 포함하여 가중치 재정규화
# 예: price + occupancy만 있을 때 → 0.20+0.25 = 0.45 → 각 0.44, 0.56으로 재정규화
# missing_pillars에 기록: ["legal", "location"]
```

**영향**: location_score null → 위치 pillar 제외 → total_score가 가격/명도 기반으로만 산출.
grade_provisional = True → "임시 등급" 표시.

### 6-4. sub_scores 오해 주의

```python
# Score.sub_scores = ts.weights_used (재정규화된 가중치 dict)
# 예: {"price": 0.444, "occupancy": 0.556}
# 이것은 세부 점수가 아님! 재정규화 후 실제 적용된 가중치임.
# 프론트엔드 근거 표시 시 "weights_used"로 레이블 명시 필요.
```

---

## 7. 개선 우선순위 제안

### P0 — 즉시 수정 (데이터 오염)

| # | 이슈 | 파일 | 수정 방법 |
|---|------|------|---------|
| 1 | `exclusive_area_m2 = platArea` 버그 | enricher.py:186 | 건축물대장 API 응답에서 올바른 전용면적 필드명 확인 후 교체 |
| 2 | location_data DB 미저장 | converters.py, auction.py(ORM) | Auction ORM에 `location_data` JSONB 컬럼 추가 + save/restore 로직 + migration |

### P1 — 데이터 완성도 향상

| # | 이슈 | 예상 효과 |
|---|------|---------|
| 3 | `commercial_trade` API 연결 | 꼬마빌딩/상가 시세 수집 → price_score 정확도 향상 |
| 4 | `land_price` API 연결 | 토지 공시지가 수집 → 토지 물건 price_score 개선 |
| 5 | `fetch_building_units` 재수집 | `--force-update`로 기존 집합건물 building_info.units 채우기 |
| 6 | SIGUNGU_CODE_MAP 서울 외 확장 | 수도권/5대 도시 lawd_cd 추가 → 서울 외 시세 수집 |

### P2 — 예측 정확도 개선

| # | 이슈 | 방법 |
|---|------|------|
| 7 | rule_v1 MAE 21.4% | `backtest_scores.py` 분석 후 `_PREDICTED_RATIO_TABLE` 유형별/지역별 세분화 |
| 8 | property_type 빈값 663건 | 낙찰결과 수집 후 상세 재조회 배치 스크립트 작성 |

### P3 — 데이터 신뢰성

| # | 이슈 | 방법 |
|---|------|------|
| 9 | occupancy 커버리지 12.1% | 현황조사서 수집 재시도 배치 개선 |
| 10 | detail JSONB 이중 스키마 | 스키마 A 레코드에 상세 재조회하여 스키마 B로 마이그레이션 |

---

## Appendix: 파일별 분석 요약

| 파일 | 역할 | 핵심 발견 |
|------|------|---------|
| `enricher.py` | API → EnrichedCase 5단 파이프라인 | location_data 계산하나 저장 안함; platArea 버그 |
| `public_api.py` | data.go.kr XML/JSON API 클라이언트 | commercial_trade, land_price 구현은 있으나 미연결 |
| `geo_client.py` | 카카오 + Vworld API 클라이언트 | geocode 반환 포맷 2종 (x/y vs b_code) |
| `court_auction.py` | 대법원 경매정보 크롤러 | 세션+rate limit 관리, 현황조사서 포함 |
| `batch_collector.py` | 크롤+보강+점수+DB 저장 오케스트레이션 | location_score는 신선 배치에서만 계산됨 |
| `models/db/auction.py` | Auction ORM | location_data 컬럼 없음 (추가 필요) |
| `models/db/score.py` | Score ORM | location_score 컬럼 있음 (단, 항상 null) |
| `models/db/converters.py` | ORM↔DTO 변환 | save_enriched_case에 location_data 저장 없음 |
| `models/enriched_case.py` | EnrichedCase DTO | LocationData 모델 정의됨 (DB와 단절) |
| `rules/location_scorer.py` | 입지 점수 산출기 | LocationData=None이면 None 반환 (정상 동작) |
| `rules/price_scorer.py` | 가격 매력도 산출기 | area_m2(=platArea) 기반 추정 시세로 BUG 영향 받음 |
