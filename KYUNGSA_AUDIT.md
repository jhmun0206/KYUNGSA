# KYUNGSA 현황 감사 보고서

> 작성일: 2026-03-13
> 목적: 새 채팅에서 프론트 와이어프레임 · 데이터 스키마 · 서버 구조 재설계를 위한 현황 파악

---

## 1. DB 현황

### 1-1. 테이블 목록 + 레코드 수 (2026-03-13 기준)

| 테이블 | 컬럼 수 | 레코드 수 | 설명 |
|--------|---------|----------|------|
| auctions | 26 | **13,923** | 경매 물건 (진행 3,367 / 매각 10,555 / 기타 1) |
| scores | 23 | **13,074** | 종합 점수 + 등급 (auctions 대비 849건 미채점) |
| occupancy_properties | 10 | 517 | 현황조사서 물건 |
| occupancy_reports | 9 | 411 | 현황조사서 원본 |
| occupancy_tenants | 22 | 437 | 현황조사서 임차인 |
| pipeline_runs | 15 | 134 | 배치 실행 이력 |
| filter_results | 6 | 4,042 | 1단 RED/YELLOW/GREEN 필터 결과 (v0 파이프라인) |
| registry_analyses | 14 | **0** | CODEF 등기부 분석 결과 (미수집) |
| registry_events | 13 | **0** | 등기부 개별 이벤트 (미수집) |
| users | 7 | 1 | 사용자 (Google OAuth) |
| user_favorites | 4 | 0 | 즐겨찾기 |
| user_saved_searches | 6 | 0 | 저장 검색 |

### 1-2. 진행 중 물건 현황

**법원별 (진행 3,367건)**
| court_office_code | 건수 |
|-------------------|------|
| B000212 (서울남부) | 1,537 |
| B000214 (서울동부) | 589 |
| B000213 (서울북부) | 574 |
| B000210 (서울중앙) | 431 |
| B000211 (서울서부) | 236 |

**등급 분포 (scores 13,074건)**
| 등급 | 건수 |
|------|------|
| A | 12 |
| B | 1,360 |
| C | 4,776 |
| D | 6,926 |

**물건 유형 (진행 Top 10)**
| property_type | 건수 |
|--------------|------|
| 다세대 | 801 |
| (빈 값) | 663 |
| 오피스텔 | 458 |
| 연립주택,다세대,빌라 | 424 |
| 상가,오피스텔,근린시설 | 221 |
| 아파트 | 214 |

---

### 1-3. auctions 테이블 컬럼 목록

```
id                     VARCHAR   PK
case_number            VARCHAR   UNIQUE  (예: 2026타경12345)
court                  VARCHAR           (법원명)
court_office_code      VARCHAR           (예: B000212)
address                TEXT              (소재지)
property_type          VARCHAR           (물건 유형)
appraised_value        BIGINT    NULL    (감정가, 원)
minimum_bid            BIGINT    NULL    (최저입찰가, 원)
auction_date           DATE      NULL    (매각기일)
status                 VARCHAR           (진행/매각/취하/변경)
bid_count              INTEGER           (회차, 유찰횟수+1)
coordinates            JSONB     NULL    ← 별도 설명
building_info          JSONB     NULL    ← 별도 설명
land_use_info          JSONB     NULL    (용도지역 — 현재 미사용)
market_price_info      JSONB     NULL    ← 별도 설명
detail                 JSONB     NULL    (auction_rounds, specification_remarks 등 포함)
rent_price_info        JSON      NULL    ← 별도 설명
winning_bid            BIGINT    NULL    (낙찰가)
winning_date           DATE      NULL    (낙찰일)
winning_ratio          FLOAT     NULL    (낙찰가율)
winning_source         VARCHAR   NULL
occupancy_tenant_count INTEGER   NULL
occupancy_status       VARCHAR           (기본: '미수집')
occupancy_risk_level   VARCHAR   NULL
created_at             TIMESTAMPTZ
updated_at             TIMESTAMPTZ
```

### 1-4. JSONB 컬럼 실제 구조 샘플

#### coordinates
```json
{
  "b_code": "1141011000",
  "sub_address_no": "",
  "main_address_no": "1009"
}
```
> 주의: lat/lng 좌표가 아닌 카카오 코드 구조. 실제로는 {"x": "127.xxx", "y": "37.xxx"} 형식이어야 하는데 일부 데이터가 b_code 구조로 저장됨. 좌표 데이터 신뢰도 낮음.

#### building_info (건축물대장 기본개요 API 결과)
```json
{
  "raw_items": [...],
  "structure": "철근콘크리트구조",
  "violation": false,
  "build_year": 2004,
  "total_area": 10965.02,
  "units_count": 229,
  "main_purpose": "업무시설",
  "ground_floors": 13,
  "use_approve_date": "20040212",
  "exclusive_area_m2": 1100.3,
  "underground_floors": 2,
  "units": []
}
```

#### market_price_info (실거래가 API 결과)
```json
{
  "lawd_cd": "11410",
  "trade_count": 9,
  "recent_trades": [
    {
      "aptNm": "북가좌삼호",
      "floor": "12",
      "dealAmount": "89,500",
      "excluUseAr": "84.57",
      "dealYear": "2026",
      "dealMonth": "3",
      "buildYear": "1996"
    }
  ],
  "avg_price_per_m2": 10811649.9,
  "reference_period": "202603"
}
```

#### rent_price_info (임대시세 계산 결과)
```json
{
  "source": "연립다세대+오피스텔",
  "lawd_cd": "28237",
  "sample_count": 321,
  "by_area_range": [
    {
      "range": "20~40㎡",
      "min_m2": 20.0,
      "max_m2": 40.0,
      "avg_rent": 47.2,
      "avg_deposit": 894.0,
      "count": 140
    }
  ],
  "queried_months": ["202603", "202601", "202512"],
  "overall_avg_rent": 57.2,
  "overall_avg_deposit": 1423.0
}
```

#### detail JSONB (주요 키)
```json
{
  "auction_rounds": [
    {
      "round_number": 1,
      "round_date": "2025-12-10",
      "minimum_bid": 350000000,
      "result": "유찰"
    }
  ],
  "specification_remarks": "...",
  "location_data": null
}
```

---

### 1-5. scores 테이블 컬럼 목록

```
id                      VARCHAR   PK
auction_id              VARCHAR   FK -> auctions.id
property_category       VARCHAR           (아파트/다세대/오피스텔/단독/상가 등)
legal_score             FLOAT     NULL    (법률 리스크 0~100)
price_score             FLOAT     NULL    (수익성 0~100)
location_score          FLOAT     NULL    (입지 0~100)
occupancy_score         FLOAT     NULL    (명도 0~100)
total_score             FLOAT             (가중 합산)
score_coverage          FLOAT             (0~1, 채워진 pillars 비율)
missing_pillars         JSONB             (예: ["legal", "location"])
grade                   VARCHAR   NULL    (A/B/C/D)
grade_provisional       BOOLEAN           (True=잠정 등급)
sub_scores              JSONB     NULL    (가중치 dict)
warnings                JSONB     NULL    (경고 문자열 배열)
needs_expert_review     BOOLEAN
scorer_version          VARCHAR           (현재 "v1.0" 전체)
scored_at               TIMESTAMPTZ NULL
pipeline_run_id         TEXT      NULL
predicted_winning_ratio FLOAT     NULL    (예측 낙찰가율)
prediction_method       VARCHAR           (ml_v1 / rule_v1)
actual_winning_bid      BIGINT    NULL    (실제 낙찰가 — 사후 추적)
actual_winning_ratio    FLOAT     NULL    (실제 낙찰가율)
prediction_error        FLOAT     NULL    (예측 오차)
```

sub_scores 샘플: {"price": 0.4, "occupancy": 0.6}
→ weights_used (재정규화된 가중치 dict)이지 세부 계산 데이터가 아님.

---

## 2. API 엔드포인트 현황

### 2-1. 실제 동작하는 FastAPI 엔드포인트 전체

**[v1] DB 기반 대시보드 API** (prefix=/api/v1) — 현재 프론트가 사용하는 것

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | /api/v1/auctions | 목록 조회 (필터/정렬/페이지) |
| GET | /api/v1/auctions/map | 지도용 좌표 목록 (최대 2000건) |
| GET | /api/v1/auctions/{case_number} | 상세 조회 |
| POST | /api/v1/auth/upsert | OAuth 사용자 upsert + JWT 발급 |
| GET | /api/v1/users/me/favorites | 즐겨찾기 목록 |
| GET | /api/v1/users/me/favorites/{case_number} | 즐겨찾기 여부 |
| PUT | /api/v1/users/me/favorites/{case_number} | 즐겨찾기 추가 |
| DELETE | /api/v1/users/me/favorites/{case_number} | 즐겨찾기 제거 |
| POST | /api/v1/users/me/favorites/bulk | localStorage->DB 일괄 이전 |
| GET | /api/v1/users/me/saved-searches | 저장 검색 목록 |
| POST | /api/v1/users/me/saved-searches | 저장 검색 생성 |
| DELETE | /api/v1/users/me/saved-searches/{id} | 저장 검색 삭제 |
| GET | /health | 헬스 체크 |

**[v0] 크롤러 직접 실행 API** (prefix=/api) — 프론트 미사용, 레거시

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | /api/auctions | 대법원 크롤러 직접 실행 후 목록 반환 |
| GET | /api/auctions/{case_number} | 크롤러 + 등기부 분석 직접 실행 |
| POST | /api/auctions/analyze | 주소로 즉시 분석 |
| GET | /api/registry/{unique_no} | 등기부 단독 조회 |

---

### 2-2. v1 API 응답 스키마 요약

**AuctionListResponse**
```
total, page, size, items: AuctionListItem[]

AuctionListItem:
  case_number, address, property_type, court, court_office_code
  appraised_value, minimum_bid, auction_date, bid_count, status
  grade (A/B/C/D), total_score, score_coverage, grade_provisional
  predicted_winning_ratio, price_score, location_score, occupancy_score
  is_past_due (기일 지남), lat, lng
```

**AuctionDetailResponse**
```
기본 정보 + 낙찰 결과(winning_bid/ratio/date) + 좌표
score: ScoreDetail (4 pillar 점수 + 예측 + warnings)
ml_prediction: MLPrediction (predicted_ratio, predicted_price, confidence, top_factors)
rounds: RoundItem[] (기일 내역)
specification_remarks: str (물건명세서 특이사항)
building_info, market_price_info, rent_price_info: dict | None
location_data: dict | None  ← 현재 항상 null
default_loan_rate: float
```

**GET /api/v1/auctions 쿼리 파라미터**
```
court_office_code   법원 코드 (B000210~B000214)
grade               등급 (콤마 구분: A,B,C,D)
property_type       카테고리 (아파트/오피스텔/다세대빌라/단독다가구/상가근생/토지)
district            행정구 (예: 강남구)
q                   주소 키워드
sort                grade|appraised_value|auction_date|minimum_bid|bid_count|discount_rate|predicted_winning_ratio
status              없음=진행+예정, 전체=all, 매각
page, size (max 100)
```

---

### 2-3. 프론트엔드에서 실제 호출하는 엔드포인트 (frontend/lib/api.ts)

| 함수 | 엔드포인트 | 용도 |
|------|-----------|------|
| fetchAuctions() | GET /api/v1/auctions | 홈/검색 목록 |
| fetchAuctionDetail() | GET /api/v1/auctions/{case_number} | 상세 페이지 |
| fetchMapItems() | GET /api/v1/auctions/map | 지도 페이지 |

즐겨찾기/인증 API는 api.ts 미등록 → 각 컴포넌트에서 직접 fetch

### 2-4. 정의됐지만 프론트 미사용 엔드포인트
- v0 전체 (/api/auctions, /api/auctions/analyze, /api/registry/*)
- v1 중 users API — 즐겨찾기/저장검색 컴포넌트에서 직접 fetch로 사용 중이긴 함

---

## 3. 외부 API 연결 현황

### 3-1. 서버 .env 키 목록

| 환경변수 | 설명 | 사용 여부 |
|----------|------|----------|
| DATABASE_URL | PostgreSQL 연결 | 핵심 |
| PUBLIC_DATA_API_KEY | data.go.kr (실거래가, 건축물대장, 전유부) | 매일 사용 |
| VWORLD_API_KEY | 국토정보플랫폼 (용도지역, 주소) | 매일 사용 |
| KAKAO_REST_API_KEY | 카카오 Geocode (주소->좌표) | 매일 사용 |
| NEXT_PUBLIC_KAKAO_MAP_KEY | 카카오맵 JS SDK | 프론트 지도 |
| CODEF_SERVICE_TYPE | demo (일 100회, 3개월) | 데모 한도 주의 |
| CODEF_DEMO_CLIENT_ID/SECRET | CODEF 등기부 API (데모) | 등기부 미수집 중 (registry_analyses=0) |
| CODEF_SANDBOX_CLIENT_ID/SECRET | CODEF 샌드박스 | 테스트용, 프로덕션 미사용 |
| CODEF_CLIENT_ID/SECRET | CODEF 정식키 | 빈 값 (미신청) |
| CODEF_PUBLIC_KEY | CODEF RSA 암호화 | CODEF 연동 시 사용 |
| IROS_PHONE_NO/PASSWORD | 인터넷등기소 비회원 로그인 | CODEF 통해 간접 |
| IROS_EPREPAY_NO/PASS | 전자민원캐시 (건당 700원) | CODEF 통해 간접 |
| OPENAI_API_KEY | OpenAI GPT-4o | 현재 미사용 (LLM 미구현) |
| TELEGRAM_BOT_TOKEN/CHAT_ID | 텔레그램 알림 | 미구현 |
| JWT_SECRET | Phase I 인증 JWT | 사용 중 |
| REDIS_URL, MONGODB_URL | (향후) | 미사용 |

### 3-2. API 호출 한도 현황

| API | 한도 | 현재 사용량 |
|-----|------|-----------|
| data.go.kr (공공데이터) | 일 100,000회 | ~1,500회/일, 여유 충분 |
| Vworld | 일 30,000회 | ~500회/일, 여유 충분 |
| 카카오 Geocode | 일 300,000회 | ~500회/일, 여유 충분 |
| CODEF 등기부 (데모) | 일 100회, 3개월 기한 | 현재 0회 (미수집) |
| CODEF 등기부 (정식) | 건당 유료 | 미신청 |

---

## 4. 인프라 현황

### 4-1. systemd 서비스 목록

| 서비스 | 상태 | 스케줄 |
|--------|------|--------|
| kyungsa.service | active (running) | 상시 (uvicorn :8000) |
| cloudflared.service | 실행 중 | 상시 |
| kyungsa-batch.timer | 활성 | 매일 03:00 KST |
| kyungsa-occupancy.timer | 활성 | 매일 04:00 KST |
| kyungsa-sale-results.timer | 활성 | 매일 06:00 KST |
| kyungsa-winning-bids.timer | 활성 | 매주 일 07:00 KST |

### 4-2. 네트워크 + 도메인

| 항목 | 값 |
|------|-----|
| 공개 API | https://api.kyungsa.com |
| 프론트엔드 | https://kyungsa.com |
| Cloudflare Tunnel ID | 290b0e5a-4b86-4fdb-91c3-5d0c932c6ca9 |
| 터널 -> 로컬 | localhost:8000 |
| 홈서버 내부 IP | 192.168.45.59 |
| Tailscale | 100.71.156.101 |

### 4-3. Vercel 배포

| 항목 | 값 |
|------|-----|
| 프레임워크 | Next.js 14 App Router |
| 배포 폴더 | /frontend |
| 도메인 | kyungsa.com |
| 환경변수 | NEXT_PUBLIC_API_BASE_URL=https://api.kyungsa.com, NEXTAUTH_URL, AUTH_SECRET, AUTH_GOOGLE_ID/SECRET, JWT_SECRET |

### 4-4. 프론트엔드 폴더 구조 (2레벨)

```
frontend/
├── app/
│   ├── api/auth/[...nextauth]/    NextAuth.js 라우터
│   ├── auction/[caseNumber]/      상세 페이지
│   ├── compare/                   비교 페이지
│   ├── favorites/                 즐겨찾기 페이지
│   ├── map/                       지도 페이지
│   ├── search/                    검색 페이지
│   ├── layout.tsx                 루트 레이아웃
│   └── page.tsx                   홈 (3섹션: 이번주기일/높은평가/통계)
├── components/
│   ├── auction/                   레거시 (미사용, 정리 필요)
│   ├── common/                    레거시 (정리 필요)
│   ├── detail/                    상세 페이지 전용
│   ├── domain/                    공통 도메인 컴포넌트
│   ├── landing/                   레거시 TopPicksGrid (미사용)
│   ├── layout/                    Header, Footer, MobileNav
│   ├── map/                       KakaoMap
│   ├── search/                    검색 관련
│   └── ui/                        shadcn/ui 기본 컴포넌트
├── lib/
│   ├── api.ts                     API 클라이언트 (서버 컴포넌트용)
│   ├── compare.ts                 비교 기능 (localStorage, 최대 3건)
│   ├── constants.ts               법원 코드, 필터 상수
│   ├── favorites.ts               즐겨찾기 (localStorage + DB 분기)
│   ├── investment.ts              투자 계산 유틸
│   ├── types.ts                   TypeScript 타입 정의
│   └── utils.ts                   포맷, D-day, 할인율, 점수해석 유틸
├── auth.ts                        NextAuth.js v5 설정
└── package.json
```

---

## 5. 데이터 수집 파이프라인 현황

### 5-1. 배치 수집 흐름 (매일 03:00)

```
BatchCollector.collect()
    │
    ├─ CourtAuctionClient.collect_list()    대법원 목록 (법원별)
    │      └─ collect_full_case()           상세 + 기일 + 문서
    │
    ├─ CaseEnricher.enrich()               데이터 보강
    │      ├─ GeoClient.geocode()           카카오 주소→좌표
    │      ├─ GeoClient.get_land_use()      Vworld 용도지역
    │      ├─ PublicApiClient.fetch_building_info()   건축물대장 기본개요
    │      ├─ PublicApiClient.fetch_building_units()  전유부 호실별 면적
    │      ├─ PublicApiClient.fetch_rent_data()       임대시세
    │      └─ PublicApiClient.fetch_market_price()    실거래가
    │
    ├─ ScoreEngine.score()                  점수 산출 (v1.0)
    │      ├─ legal_score    (등기부 없음 → None)
    │      ├─ price_score    (할인율 + 유찰횟수 + 예측낙찰가율)
    │      ├─ location_score (location_data 미수집 → None)
    │      └─ occupancy_score (현황조사서 여부 + 임차인 분석)
    │
    └─ DB upsert (auctions + scores)
```

### 5-2. enricher.py API별 대략적 성공률

| API | 성공률 추정 | 비고 |
|-----|-----------|------|
| 카카오 Geocode | ~80% | 지번주소 실패 많음 |
| Vworld 용도지역 | ~70% | |
| 건축물대장 기본개요 | ~60% | 집합건물만 수집 가능 |
| 전유부 (getBrExposPubuseAreaInfo) | 낮음 | 최근 추가, 커버리지 미확인 |
| 임대시세 | ~50% | |
| 실거래가 | ~60% | 아파트 위주 |

### 5-3. 기타 수집 스케줄

| 시간 | 작업 |
|------|------|
| 매일 03:00 | 배치 수집 + 점수 산출 |
| 매일 04:00 | 현황조사서 수집 (occupancy) |
| 매일 06:00 | 전국 낙찰 완료 건 수집 |
| 매주 일 07:00 | 기수집 물건 낙찰가 사후 추적 |

---

## 6. 프론트엔드 컴포넌트 현황

### 6-1. 페이지 → 주요 컴포넌트 매핑

| 페이지 | 경로 | 주요 컴포넌트 |
|--------|------|-------------|
| 홈 | / | AuctionListRow × 2섹션, 통계 위젯 |
| 검색 | /search | SearchFilters, ClientFilteredResults, SearchResultsList, GradeLegend |
| 상세 | /auction/[caseNumber] | DecisionSection, PillarBreakdown, BasicInfo, LocationButtons, DetailSidePanel → InvestmentCalculator |
| 지도 | /map | KakaoMap (마커 클러스터, 등급별 SVG 마커) |
| 비교 | /compare | AuctionListRow 기반, localStorage 최대 3건 |
| 즐겨찾기 | /favorites | AuctionListRow, Skeleton |

### 6-2. components/ 전체 파일 목록

**detail/ (상세 페이지)**
- BasicInfo.tsx — 기일내역(RoundTimeline) + 기본 정보 테이블
- DecisionSection.tsx — 등급 + 가격 + D-day + 면책
- DetailSidePanel.tsx — 데스크탑 sticky 사이드패널 + 모바일 액션바 + 드로어
- InvestmentCalculator.tsx — 투자 분석 시뮬레이터 (슬라이더 + 수익률 + 호실별 임대)
- LocationButtons.tsx — 로드뷰/카카오맵/네이버 외부 링크
- MobileActionBar.tsx — 구버전 (DetailSidePanel로 대체, 미사용)
- PillarBreakdown.tsx — 4대 점수 Radar + BarChart + Accordion 근거

**domain/ (공통)**
- AuctionCard.tsx — 카드 뷰 (레거시, 미사용)
- AuctionListRow.tsx — 리스트 행 (홈/검색/비교/즐겨찾기에서 사용)
- CompareBar.tsx, CompareButton.tsx
- CoveragePill.tsx, DisclaimerBanner.tsx
- FavoriteButton.tsx (로그인/비로그인 분기), GradeBadge.tsx, PredictionPill.tsx

**layout/**
- AuthSessionProvider.tsx, Footer.tsx, Header.tsx, MobileNav.tsx (4탭)
- ThemeProvider.tsx, ThemeToggle.tsx (다크모드 class 방식)

**search/**
- ClientFilteredResults.tsx, GradeLegend.tsx, SearchFilters.tsx
- SearchResultsGrid.tsx (구버전, 미사용), SearchResultsList.tsx (현재 사용)

**landing/** — TopPicksGrid.tsx (레거시, 미사용)
**auction/** — 전체 레거시 (미사용)
**map/** — KakaoMap.tsx
**ui/** — accordion, badge, button, card, skeleton, tabs, tooltip (shadcn/ui)

---

## 7. 알려진 이슈 + 재설계 포인트

### 7-1. 데이터 품질 이슈
1. **coordinates 형식 불일치**: 일부 데이터가 {"b_code":..., "main_address_no":...} 구조 → 지도 좌표 파싱 실패, 마커 누락
2. **property_type 빈 값 663건**: 진행 물건 중 유형 불명 다수 → 필터 시 제외
3. **location_data 항상 null**: DB 미저장 → location_score 항상 None → 모든 물건 missing_pillars에 "location" 포함
4. **legal_score 항상 None**: CODEF 등기부 미수집 (registry_analyses=0) → 모든 물건 missing_pillars에 "legal" 포함
5. **scores 미채점 849건**: auctions 13,923 - scores 13,074 = 849건 격차
6. **score_coverage 낮음**: legal + location 미수집으로 대부분 50% 이하 → grade_provisional=True

### 7-2. API 설계 이슈
- v0 (크롤러 직접) 라우터가 main.py에 여전히 등록됨 → 충돌 위험
- AuctionDetailResponse가 v0 schemas.py와 v1/schemas.py에 동명 클래스로 공존

### 7-3. 프론트 정리 필요 파일
- components/auction/ 전체 (레거시, 미사용)
- components/common/ (레거시)
- components/landing/TopPicksGrid.tsx
- components/detail/MobileActionBar.tsx
- components/search/SearchResultsGrid.tsx

---

*작성일: 2026-03-13 | 홈서버 DB 직접 조회 기반 실측 데이터*
