# 🏠 KYUNGSA — 부동산 경매 큐레이션 서비스

> **경매 물건의 리스크를 자동으로 구조화해서, 볼 가치가 없는 70%를 먼저 걸러주는 서비스**

## 📌 프로젝트 상태

| 항목 | 상태 |
|------|------|
| 프로젝트명 | KYUNGSA |
| 현재 단계 | `Phase 10 완료` (ML 재학습 + property_sequence 다물건 + 경기 법원 코드 수정) |
| 최종 업데이트 | 2026-03-27 |
| 테스트 | 763개 통과 |
| 배포 | https://kyungsa.com (Vercel) / https://api.kyungsa.com (Cloudflare Tunnel) |
| 개발 도구 | Claude Code |
| 개발자 | 경희대학교 컴퓨터공학과 4학년 |

---

## 1. 프로젝트 개요

### 1.1 무엇을 만드는가

경매 물건의 등기, 권리관계, 입지, 가격을 자동으로 분석하여 리스크를 구조화하고, 검토할 가치가 없는 물건을 자동으로 걸러주는 시스템.

### 1.2 핵심 원칙

- **엔진 통합**: 분석 엔진은 하나, 출력만 Public/Private 분리
- **판단 분리**: LLM은 자연어 설명만, 판단과 점수는 룰/수식 기반
- **선별 중심**: 추천이 아닌 필터링(Filter)이 핵심
- **검증 내장**: 데이터 정확성 검증을 파이프라인 전 단계에 내장

### 1.3 서비스 구분

| 구분 | Public (공개용) | Private (개인용) |
|------|----------------|-----------------|
| 목적 | 물건 선별 + 리스크 구조화 | 입찰 추천 + 가격 제안 |
| 출력 | 리스크 리포트, 필터링 목록 | 종합 점수, 적정가, 시뮬레이션 |
| 공개 | ✅ 가능 | ❌ **절대 비공개** |

### 1.4 사용자 페르소나 & 시나리오

**페르소나 A: 김경매 (본인 — 1차 타겟)**
- 경희대 컴공 4학년, 경매 초중급, 꼬마빌딩 투자 관심
- 고충: 물건이 수백 건인데 등기부 하나하나 열어보기엔 시간/비용 부족
- 시나리오: "이번 주 서울 경매 예정 꼬마빌딩 중 Hard Stop에 안 걸리는 물건만 보여줘" → 필터링 목록 확인 → 관심 물건 리포트 열람 → Private 대시보드에서 적정가 확인

**페르소나 B: 박초보 (Public 서비스 대상)**
- 30대 직장인, 경매 입문자, 아파트/빌라 관심
- 고충: 권리분석이 뭔지도 모르겠고, 위험한 물건을 잘못 입찰할까 두렵다
- 시나리오: "서울 강남 아파트 경매 물건 검색" → 리스크 신호등으로 위험도 한눈에 확인 → "왜 위험한지" 자연어 설명 읽기

**페르소나 C: 이중급 (확장 타겟)**
- 40대, 경매 5건 이상 경험, 효율화 니즈
- 시나리오: "조건 저장해두면 신규 물건 나올 때 알림" → 알림 수신 → 리포트 빠르게 확인 → 입찰 결정

---

## 2. 기술 스택

```
Backend:    Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0 / Alembic / PyJWT
DB:         PostgreSQL 16 (홈서버 확정)
Cache:      인메모리 (dict/lru_cache) → Redis (필요 시)
Scheduler:  systemd timer (cron 대체)
Crawling:   httpx + Playwright (대법원 E2E)
Registry:   CODEF API (등기부등본 자동 조회) + PyMuPDF (PDF 백업)
ML:         CatBoost (낙찰가율 예측) + pandas + numpy
Crypto:     pycryptodome (CODEF RSA 암호화)
Geo/API:    카카오 Geocode+카테고리, Vworld, data.go.kr (실거래가, 건축물대장)
LLM:        OpenAI API (리스크 설명 생성, 미착수)
Server:     Ubuntu Server 24.04 LTS + systemd + Nginx — MSI GP75 홈서버
Infra:      Cloudflare Tunnel (api.kyungsa.com) + Vercel (kyungsa.com)
Frontend:   Next.js 14 (App Router) + TypeScript + shadcn/ui + Framer Motion + NextAuth.js v5
Auth:       Google OAuth (NextAuth.js v5) + 백엔드 JWT (HS256)
Dev Tool:   Claude Code
```

---

## 3. 프로젝트 구조

```
KYUNGSA/
├── CLAUDE.md                    # Claude Code 지시 파일
├── README.md                    # 이 파일 (살아있는 문서)
├── docs/                        # 도메인 지식 + 룰 명세
├── backend/
│   ├── app/
│   │   ├── main.py              # ⭐ FastAPI 엔트리 (uvicorn app.main:app)
│   │   ├── config.py            # 환경변수 설정 (JWT_SECRET, DEFAULT_LOAN_RATE 등)
│   │   ├── database.py          # ⭐ SQLAlchemy engine + SessionLocal
│   │   ├── api/
│   │   │   ├── auctions.py      # v0 크롤러 직접 실행 API (4 엔드포인트)
│   │   │   ├── v1/
│   │   │   │   ├── auctions.py  # ⭐ v1 DB 기반 대시보드 API (3 엔드포인트)
│   │   │   │   ├── auth.py      # ⭐ Phase I: OAuth upsert + JWT 발급
│   │   │   │   ├── users.py     # ⭐ Phase I: 즐겨찾기 + 저장 검색 CRUD
│   │   │   └── telegram.py  # ⭐ Phase J: 텔레그램 Webhook + /start 연동
│   │   │   │   └── schemas.py   # v1 응답 스키마
│   │   │   ├── schemas.py       # v0 응답/요청 스키마
│   │   │   └── dependencies.py  # 의존성 주입
│   │   ├── models/
│   │   │   ├── auction.py       # 대법원 경매 DTO (8개)
│   │   │   ├── enriched_case.py # ⭐ 1단+2단 통합 모델 + RentPriceInfo (면적구간별)
│   │   │   ├── registry.py      # 등기부 모델 (EventType 19종)
│   │   │   ├── scores.py        # ⭐ 점수 모델 (Legal/Price/Location/Occupancy/Total)
│   │   │   ├── occupancy_dto.py # 현황조사서 DTO
│   │   │   └── db/
│   │   │       ├── base.py      # Base + JSONBOrJSON + Mixin
│   │   │       ├── auction.py   # Auction ORM
│   │   │       ├── score.py     # ⭐ Score ORM (낙찰가율 포함)
│   │   │       ├── filter_result.py
│   │   │       ├── registry.py  # RegistryEventORM + RegistryAnalysisORM
│   │   │       ├── occupancy.py # OccupancyReport + OccupancyTenant + OccupancyProperty ORM
│   │   │       ├── user.py      # ⭐ Phase I: User + UserFavorite + UserSavedSearch ORM
│   │   │       ├── pipeline_run.py
│   │   │       └── converters.py # ⭐ Pydantic↔ORM 변환 + upsert
│   │   └── services/
│   │       ├── crawler/
│   │       │   ├── court_auction.py         # ⭐ 대법원 HTTP 클라이언트 (✅)
│   │       │   ├── court_auction_parser.py  # 대법원 JSON 파서
│   │       │   ├── codef_client.py          # CODEF OAuth2 클라이언트 (✅)
│   │       │   ├── geo_client.py            # 카카오 Geocode+카테고리 + Vworld (✅)
│   │       │   └── public_api.py            # data.go.kr 실거래가/건축물대장 (✅)
│   │       ├── parser/
│   │       │   ├── registry_parser.py       # PDF/텍스트 → RegistryDocument (✅)
│   │       │   └── registry_analyzer.py     # 말소기준 + 인수/소멸 + HardStop (✅)
│   │       ├── registry/
│   │       │   ├── provider.py              # RegistryProvider ABC
│   │       │   ├── codef_provider.py        # CODEF API 호출 (✅)
│   │       │   ├── codef_mapper.py          # CODEF JSON → RegistryDocument (✅)
│   │       │   ├── matcher.py               # CODEF 검색결과 매칭
│   │       │   └── pipeline.py              # 주소→등기부→분석 파이프라인 (✅)
│   │       ├── occupancy/                   # ⭐ 명도 데이터 수집/파싱
│   │       │   ├── parser.py                # 현황조사서 JSON 파서 (대법원 API)
│   │       │   └── service.py               # 수집→파싱→DB 저장 오케스트레이터
│   │       ├── prediction/                  # ⭐ ML 낙찰가율 예측 (Private)
│   │       │   ├── config.py                # 하이퍼파라미터, 피처, 병합 매핑
│   │       │   ├── data_pipeline.py         # DB → DataFrame 추출
│   │       │   ├── feature_engineer.py      # 파생 피처 생성 (21개)
│   │       │   ├── trainer.py               # CatBoost 학습 (5-fold CV)
│   │       │   ├── predictor.py             # ⭐ WinningBidPredictor 싱글톤 (추론)
│   │       │   └── rolling_helper.py        # Rolling 통계 DB 조회 헬퍼
│   │       ├── rules/                       # ⭐ 점수 엔진 (핵심 자산)
│   │       │   ├── legal_scorer.py          # 법률 점수 (근저당/가압류/인수권리)
│   │       │   ├── price_scorer.py          # 가격 매력도 점수 (할인율/시세/유찰)
│   │       │   ├── location_scorer.py       # 입지 점수 (역/상권/학교/용도지역)
│   │       │   ├── occupancy_scorer.py      # 명도 점수 (임차인/보증금/대항력)
│   │       │   ├── total_scorer.py          # 종합 점수 + 등급 A/B/C/D
│   │       │   └── engine.py                # RuleEngineV2 (통합 평가 오케스트레이터)
│   │       ├── address_parser.py            # 주소 파싱 (경매주소→CODEF 파라미터)
│   │       ├── enricher.py                  # 1단 데이터 보강 (geocode→용도→건물→시세→임대료)
│   │       ├── filter_engine.py             # FilterEngine + CostGate
│   │       ├── filter_rules.py              # RED(R001~R003) + YELLOW(Y001~Y003)
│   │       ├── pipeline.py                  # 1단+2단 통합 AuctionPipeline
│   │       ├── batch_collector.py           # ⭐ 일일 배치 수집기 (크롤→보강→필터→DB)
│   │       ├── winning_bid_collector.py     # ⭐ 낙찰가 사후 추적기
│   │       ├── sale_result_collector.py     # ⭐ 전국 낙찰 완료 건 수집기
│   │       └── registry_rules.py            # HardStop 룰 정의 (HS001~HS008)
│   ├── alembic/versions/        # DB 마이그레이션 이력
│   │   ├── a0c347536398_initial_5a_schema.py
│   │   ├── b1d458637499_5e_scores_table.py
│   │   ├── c3e891a47f20_5_5_scores_add_predicted_winning_ratio.py
│   │   ├── d4f721839b6c_phase6_scores_add_grade_provisional.py
│   │   ├── e5a2c947f310_phase65_winning_columns.py
│   │   ├── f7a1b2c3d4e5_phase7_occupancy_tables.py
│   │   ├── a8f3c2d1e9b7_phase_h2_rent_price_info.py
│   │   ├── b1c2d3e4f5a6_fix_pipeline_run_id_text.py
│   │   ├── d2e3f4a5b6c7_phase_i_users.py   # ⭐ Phase I: users 3개 테이블
│   │   ├── 4d0e491c6f8f_merge_b1c2_and_d2e3.py  # merge head
│   │   ├── 5e6f7a8b9c0d_db_rebuild_normalize_columns.py  # ⭐ DB-REBUILD: 정규화 11컬럼 + auction_rounds
│   │   ├── e3f4a5b6c7d8_phase_j_telegram.py  # ⭐ Phase J: telegram_verifications 테이블
│   │   └── f8a9b0c1d2e3_add_property_sequence.py  # ⭐ 다물건: property_sequence + UNIQUE(case_number, seq)
│   └── tests/                   # 763개 테스트 전체 통과
├── scripts/
│   ├── run_batch.py             # 배치 수집기 CLI (--rescore-db 포함)
│   ├── collect_winning_bids.py  # 낙찰가 추적 CLI
│   ├── collect_sale_results.py  # 낙찰 완료 건 수집 CLI
│   ├── backtest_scores.py       # ⭐ 백테스트 + 캘리브레이션 (stdlib만)
│   ├── train_model.py           # ⭐ CatBoost 모델 학습 + 교차검증
│   ├── evaluate_model.py        # 모델 평가 + rule_v1 비교
│   ├── retrain_model.py         # 월간 자동 재학습 (개선 시만 교체)
│   ├── eda_prediction.py        # ML 학습 데이터 EDA
│   ├── collect_occupancy.py     # 현황조사서 수집 CLI (단건/backfill)
│   ├── fix_past_due.py          # ⭐ 기일경과 물건 상태 복원 (매일 04:30)
│   ├── backfill_bcode.py        # b_code 역채움 CLI (geocode 기반)
│   ├── run_pipeline.py          # 1단 파이프라인 실행
│   ├── parse_registry.py        # 등기부 파싱 CLI
│   ├── test_codef_registry.py   # CODEF 등기부 실 API 테스트
│   ├── test_all_apis.py         # 전체 API 연결 테스트
│   └── test_pipeline_e2e.py     # E2E 테스트 (Playwright)
├── deploy/                      # 서버 배포 설정
│   ├── kyungsa-batch.service/.timer        # 매일 03:00 수집
│   ├── kyungsa-sale-results.service/.timer # 매일 06:00 전국 낙찰 건
│   ├── kyungsa-winning-bids.service/.timer # 매주 일 07:00 낙찰가 추적
│   └── DEPLOY.md                # 서버 배포 명령어
└── frontend/                    # Next.js 14 (App Router)
    ├── auth.ts                  # ⭐ Phase I: NextAuth.js v5 설정 (Google OAuth)
    ├── app/
    │   ├── page.tsx             # ⭐ 랜딩 (Hero + 이번주 기일 + 높은 평가 + 통계)
    │   ├── search/page.tsx      # ⭐ 검색 전용 (스티키 필터 + 리스트 뷰)
    │   ├── auction/[caseNumber]/page.tsx  # 물건 상세 (4단 앵커)
    │   ├── map/page.tsx         # 지도 뷰 (카카오맵 + 등급 마커)
    │   ├── favorites/page.tsx   # 관심 목록 (정렬 + 애니메이션)
    │   ├── compare/page.tsx     # 비교 페이지 (최대 3건)
    │   └── api/auth/[...nextauth]/route.ts  # ⭐ Phase I: NextAuth 핸들러
    ├── components/
    │   ├── layout/              # Header (로그인/아바타/텔레그램), Footer, MobileNav, ThemeProvider,
    │   │                        #   ThemeToggle, AuthSessionProvider, TelegramModal
    │   ├── domain/              # AuctionListRow, AuctionCard, GradeBadge, CoveragePill,
    │   │                        #   PredictionPill, DisclaimerBanner, FavoriteButton(DB동기화),
    │   │                        #   CompareButton, CompareBar
    │   ├── detail/              # DecisionSection, PillarBreakdown(Accordion 근거),
    │   │                        #   BasicInfo, InvestmentCalculator(룸테이블+임대료참고),
    │   │                        #   MobileActionBar
    │   ├── landing/             # (레거시, TopPicksGrid)
    │   └── search/              # ⭐ Phase K-2 전면 재설계
    │       ├── SearchSidebar.tsx        # 항상 펼쳐진 사이드바 (8섹션: 물건종류/건물형태/지역/감정가/유찰/역거리/승인연도/리스크)
    │       ├── AuctionTable.tsx         # 고정폭 컬럼 테이블 (신호등+완성도+관심/비교)
    │       ├── SearchResults.tsx        # 클라이언트 필터 래퍼 (역거리/건축년도/건물형태/신호등)
    │       ├── SearchToolbar.tsx        # 상단 검색바 + 정렬 + 건수
    │       ├── MobileFilterDrawer.tsx   # 모바일 하단 드로어 (SearchSidebar 재사용)
    │       ├── GradeLegend.tsx          # 리스크 신호등 범례 (🟢🟡🔴⚫)
    │       ├── SearchFilters.tsx        # (레거시, 보존)
    │       ├── SearchResultsList.tsx    # (레거시, 보존)
    │       └── ClientFilteredResults.tsx # (레거시, 보존)
    ├── lib/
    │   ├── api.ts               # fetchAuctions, fetchAuctionDetail
    │   ├── auth-api.ts          # ⭐ Phase I: Bearer 토큰 인증 API (favorites + saved-searches)
    │   ├── types.ts             # TypeScript 타입 정의 (+ station_distance_m, build_year, building_type 등)
    │   ├── constants.ts         # 등급 색상, 법원 코드, PRICE_RANGES, SORT_OPTIONS
    │   ├── utils.ts             # formatPrice, calcDiscount, calcDday, getDdayColor
    │   ├── investment.ts        # 투자 계산 유틸 (IRR, 수익률 등)
    │   ├── favorites.ts         # ⭐ localStorage + DB 하이브리드 즐겨찾기
    │   ├── compare.ts           # localStorage 비교 (최대 3건)
    │   ├── property-category.ts # ⭐ Phase K-2: 물건유형 정규화 맵 + LTV_BY_CATEGORY
    │   └── risk-signals.ts      # ⭐ Phase K-2: 신호등 타입 + calcListSignal()
    └── types/
        └── next-auth.d.ts       # ⭐ Phase I: Session 타입 확장 (backendToken, userId)
```

---

## 4. 로드맵 & 체크리스트

### 0단계: 사전 검증 ✅ 완료

- [x] 대법원 경매정보 크롤러 구현 + E2E 검증 ✅
- [x] 공공 API 호출 테스트 ✅ (실거래가, 건축물대장, Vworld, 카카오)
- [x] CODEF API 토큰 + 등기부등본 실 API 호출 성공 ✅
- [x] 1단 필터링 데이터 소스 5개 확정
- [ ] 법적 지위 확인 (변호사 자문, 투자자문업 해당 여부) — **미완료**

### 1단계: 1단 필터링 파이프라인 ✅ 완료

- [x] CaseEnricher (geocode → land_use → building → market_price)
- [x] FilterEngine (RED > YELLOW > GREEN + CostGate)
- [x] RED 룰 3종: R001 그린벨트, R002 위반건축물, R003 토지단독
- [x] YELLOW 룰 3종: Y001 유찰3회, Y002 시세괴리30%, Y003 건축물대장미확인

### 2단계: 등기부 분석 파이프라인 ✅ 완료

- [x] RegistryParser (PDF/텍스트 → RegistryDocument, EventType 19종)
- [x] RegistryAnalyzer (말소기준 판별 + 인수/소멸 분류 + HardStop 탐지)
- [x] HardStop 8종: HS001~005 기존 + HS006(가등기)/HS007(지상권)/HS008(지역권)
- [x] CODEF 등기부 연동 (CodefProvider + CodefMapper + RegistryPipeline)

### 3단계: 1단+2단 통합 + API ✅ 완료

- [x] address_parser.py (주소 파싱, 29개 테스트)
- [x] matcher.py (CODEF 검색결과 매칭, 4단계 신뢰도)
- [x] AuctionPipeline 2단 통합 (fail-open, RED 건 스킵)
- [x] FastAPI 엔드포인트 4개: GET `/api/auctions`, `/api/auctions/{id}`, POST `/api/auctions/analyze`, GET `/api/registry/{unique_no}`

### 4단계: 실전 E2E 검증 ✅ 완료

- [x] 실제 경매 물건 10건 E2E 검증 (registry_full 86%)
- [x] 버그 수정: Vworld 데이터셋, CODEF inquiryType=0, CF-12826/12411/13328 해소

### 5단계: 서버 세팅 + DB + 배치 + 점수 엔진 ✅ 완료

- [x] **5-0: 홈서버 세팅** — Ubuntu 24.04 LTS + PostgreSQL 16 + pyenv + systemd + Tailscale
- [x] **5A: DB 스키마 + ORM** — SQLAlchemy ORM 5개 테이블 + Alembic + converter
- [x] **5B: 배치 수집기** — BatchCollector + CLI + systemd 03:00 timer
- [x] **5C: 법률 점수 엔진** — LegalScorer (근저당/가압류 곡선, Hard Stop 연동)
- [x] **5D: 가격 매력도 점수 엔진** — PriceScorer (할인율/시세대비/감정가신뢰도 곡선)
- [x] **5E: RuleEngine v2 통합** — TotalScorer (유형별 가중치, 등급 A/B/C/D)
- [x] **5.5: Hard Stop 확장 + 낙찰가율 예측** — HS006~008 + 유찰횟수 기반 통계 낙찰가율
- [x] **5F: 백테스트 + 캘리브레이션** — 서울 7,134건 실측, 예측 오차 교정 (아파트 0.975→0.80 등)

### 6단계: 입지 데이터 + 낙찰 추적 ✅ 완료

- [x] 카카오 카테고리 검색 연동 (SW8/SC4/MT1/CS2/HP8)
- [x] LocationScorer (역거리/상권/학교/용도지역 곡선 분리)
- [x] **6.5a: WinningBidCollector** — 기수집 물건 낙찰가 사후 추적 (매주 일 07:00)
- [x] **6.5b: SaleResultCollector** — 전국 낙찰 완료 건 자동 수집 (매일 06:00, 12,906건 대상)

### 7단계: 명도 데이터 ✅ 완료

- [x] **7-1: DB 스키마** — OccupancyReport + OccupancyTenant + OccupancyProperty ORM (3개 테이블)
- [x] **7-2: 현황조사서 수집/파싱** — 대법원 JSON API(selectCurstExmndc.on) fetcher + parser + DB 저장 서비스
- [x] **7-3: 명도 점수 엔진** — OccupancyScorer (임차인복잡도/보증금부담도/대항력위험도, 유형별 가중합, 신뢰도 감쇠)
- [x] **7-4: RuleEngineV2 통합** — 4 pillar 완전 가동 (Legal + Price + Location + Occupancy)
- [ ] Hard Stop 확장: HS-F01 유치권, HS-F02 점유 분쟁 — **미구현** (매각물건명세서 파싱 필요)

### 8단계: 대시보드 + ML 예측 ✅ 완료

- [x] FastAPI v1 API (DB 기반, GET `/api/v1/auctions`, `/api/v1/auctions/{id}`, `/api/v1/auctions/map`)
- [x] Next.js 14 — 물건 목록 + 상세 + 즐겨찾기 + 지도 (카카오맵 + 등급 마커)
- [x] 디자인 시스템: shadcn/ui + Pretendard CDN + next-themes (다크모드) + CSS 토큰
- [x] 배포: kyungsa.com (Vercel) + api.kyungsa.com (Cloudflare Tunnel)
- [x] **8-1: ML 데이터 파이프라인** — PredictionDataPipeline (DB→DataFrame) + FeatureEngineer (21개 피처, 시간 누수 방지 rolling)
- [x] **8-2: CatBoost 학습** — ModelTrainer (5-fold CV, early stopping, 모델 저장/로드) + train_model.py + evaluate_model.py
- [x] **8-3: ML 추론 API** — WinningBidPredictor 싱글톤 (모델 메모리 유지, rule_v1 fallback) + retrain_model.py (월간 자동 재학습)
- [x] **8-4: 프론트엔드 ML 통합** — MLPrediction 타입 + PredictionPill 신뢰도 뱃지 + top_factors 영향 요인 표시

### 9단계: UX 재설계 ✅ 완료

- [x] 랜딩 페이지 (`/`): Hero + 통계 스트립 + Top Picks 4건 + CTA
- [x] 검색 전용 페이지 (`/search`): 스티키 필터바 + 필터 칩 + AnimatePresence 그리드
- [x] 모바일 하단 탭바 (MobileNav, sm:hidden)
- [x] Header: 아이콘 + 활성 상태 + 모바일 숨김
- [x] 관심목록 개선: 요약 스트립 + 정렬 + 퇴장 애니메이션 + Empty State
- [x] framer-motion 패키지 추가

### Phase D~F: 프론트엔드 UX 개선 ✅ 완료

- [x] **Phase D: 리스트 뷰 + 네비게이션 정리** — AuctionListRow + SearchResultsList + 할인율순 정렬 + 모바일 4탭
- [x] **Phase E: 홈 3섹션 개편 + 점수 근거 Accordion** — 이번 주 기일 / 높은 평가 / 통계 + pillar 근거 토글
- [x] **Phase F: 권리분석 잠금 UI + 등급 근거 Tooltip** — 등기부 열람 CTA + 등급/ML 근거 Tooltip + 검색 등급 범례

### Phase G: 투자 분석 시뮬레이터 ✅ 완료

- [x] InvestmentCalculator (낙찰 희망가 슬라이더 + 취등록세/대출/수익률 3칸 그리드)
- [x] MobileActionBar (모바일 하단 관심/비교/공유 액션바)
- [x] 상세 페이지 앵커 네비게이션 (#analysis, #investment, #raw-data)
- [x] 키워드 검색 (`q` 파라미터, 백엔드 ILIKE 필터)

### Phase H: 투자 분석 자동 채움 ✅ 완료

- [x] **H-1: 건축물대장 저장 수정** — BuildingInfo 모델 확장 (전용면적/층수/세대수/건축년도) + converter 보존 + API building_info 응답 + InvestmentCalculator 건물 정보 자동 표시
- [x] **H-2: 월세 실거래가 API** — `rent_price_info` 컬럼 추가 + Enricher 면적구간별 임대료 집계 (6 bins: 10미만~85초과, count<2 bucket 제외) + b_code 기반 읍면동 단위 조회
- [x] **H-3: 대출 금리 자동 채움** — `DEFAULT_LOAN_RATE` 환경변수 → API 응답 `default_loan_rate` → InvestmentCalculator 초기값 자동 주입
- [x] **H-4: InvestmentCalculator 전면 개편** — 룸 테이블 (building_info有) / 단일 입력 (無) 분기, 면적구간별 참고 임대료 표시, 다방/네이버 부동산 외부 링크

### Phase I: 사용자 로그인/인증 시스템 ✅ 완료

- [x] **Alembic migration** — `users`, `user_favorites`, `user_saved_searches` 3개 테이블 (d2e3f4a5b6c7)
- [x] **Backend JWT** — PyJWT HS256, `JWT_SECRET` 환경변수, 30일 만료
- [x] **`POST /api/v1/auth/upsert`** — Google OAuth 사용자 email 기준 upsert + backend JWT 발급
- [x] **`/api/v1/users/me/favorites`** — GET(목록) / PUT(추가) / DELETE(제거) / POST bulk(마이그레이션)
- [x] **`/api/v1/users/me/saved-searches`** — GET(목록) / POST(저장, 최대20개) / DELETE(삭제)
- [x] **NextAuth.js v5** — `auth.ts` + `app/api/auth/[...nextauth]/route.ts` + Google provider auto env-binding
- [x] **`jwt()` 콜백** — 최초 로그인 시 백엔드 upsert 호출 → `session.backendToken` 저장
- [x] **Header 로그인 UI** — LogIn 버튼 / 아바타 드롭다운 (이름/이메일/관심목록/로그아웃)
- [x] **FavoriteButton DB 동기화** — 로그인 시 DB 낙관적 업데이트, 비로그인 시 localStorage
- [x] **localStorage → DB 마이그레이션** — 로그인 시 1회 자동 bulk-sync
- [x] **SearchFilters 조건 저장** — "저장" 버튼, 비로그인 시 Google 로그인 유도

### Phase K: 프론트엔드 재설계

- [x] **Phase K-1: 상세 페이지** — 2컬럼 레이아웃 + 로드뷰 + 전유부 호실 자동채움
- [x] **Phase K-2: 검색 페이지** — 사이드바 필터 + 고정폭 테이블 + 리스크 신호등 (🟢🟡🔴⚫)
  - SearchSidebar: 8섹션 항상 펼쳐진 사이드바 (물건종류 멀티셀렉, 지역 25구 그리드, 감정가 프리셋 등)
  - AuctionTable: 고정폭 컬럼 테이블 (유형/주소/감정가/최저가/기일/유찰/신호등/완성도/관심비교)
  - SearchResults: 클라이언트 필터 (역거리·건물형태·건축년도·신호등 등 6종)
  - MobileFilterDrawer: 하단 드로어 (SearchSidebar 재사용)
  - `lib/property-category.ts`: 물건유형 정규화 맵 + LTV_BY_CATEGORY
  - `lib/risk-signals.ts`: 신호등 타입 + `calcListSignal()` + `getSignalLabel()`
  - `AuctionListItem` 신규 필드: `station_distance_m`, `build_year`, `building_type`, `property_category`

### Phase K: 프론트엔드 재설계 + 현금흐름 분석 (진행 중)

- [x] **Phase K-1**: 상세 페이지 2컬럼 레이아웃 + 로드뷰 + 전유부 호실 자동채움
- [x] **Phase K-2**: 검색 페이지 전면 재설계 (사이드바 8섹션 + AuctionTable 고정폭 + 리스크 신호등)
- [x] **현금흐름 분석 페이지** (`app/cashflow/[caseNumber]/`)
  - `lib/cashflow.ts`: 캐시플로우 계산 엔진 (취등록세, 대출, 임대수익률, 에퀴티수익률, 매도수익)
  - `BidSlider`: 낙찰가 슬라이더 + 직접 입력 + ML 참고 범위 표시
  - `CostSection`: 취등록세 + 법무비용 + 기타비용
  - `LoanSection`: LTV + 대출금리 + 월 이자
  - `UnitsTable`: 호실별 면적/월세/보증금 입력 (건축물대장 자동 채움)
  - `SaleSection`: 매도 희망가 → 매도차익/수익률
  - `ResultCard`: 낙찰가 요약 + 총 매입가 + 필요자금 + 임대수익률 + 에퀴티수익률
  - 버그 수정: 면적 소수점 `formatArea()` + `"use client"` + 임대 수익률 섹션 항상 표시

### Phase H-5: 상가 임대료 레퍼런스 ✅ 완료

- [x] **한국부동산원 R-ONE API** — 소규모상가 ㎡당 임대료 (자치구 단위, `rent_price_info` 연동)
- [x] **InvestmentCalculator 임대료 참고 표시** — 면적구간별 시장 임대료 밴드 표시

### Phase DB-REBUILD: DB 정규화 ✅ 완료

- [x] **11개 정규화 컬럼 추출** — `auctions` 테이블에 `property_category`, `building_type`, `build_year`, `station_distance_m`, `exclusive_area_m2_real`, `floor_count`, `units_count_real`, `current_round` 등 정규화 컬럼 추가
- [x] **`auction_rounds` 테이블 신설** — 기일 히스토리 별도 테이블 (round_no, bid_date, minimum_bid, result)
- [x] **마이그레이션** — `5e6f7a8b9c0d_db_rebuild_normalize_columns.py`

### Phase J: 텔레그램 알림 (인프라 완료, 발송 로직 미구현)

- [x] **DB**: `telegram_verifications` 테이블 (code 6자리, 10분 만료), `users` 테이블에 `telegram_chat_id`, `telegram_verified_at` 컬럼 추가
- [x] **API**: `POST /api/v1/users/me/telegram/code` (코드 발급), `GET/DELETE /api/v1/users/me/telegram` (상태/해제)
- [x] **Webhook**: `POST /api/v1/telegram/webhook` — `/start <code>` 수신 → chat_id 연동
- [x] **프론트엔드**: `TelegramModal.tsx` — Header 드롭다운에서 열기, 코드 발급/복사 UI
- [ ] **알림 발송 로직** — 저장된 검색 조건 매칭 → 텔레그램 메시지 발송 (cron job, 미구현)

### 미착수 / 백로그
- [ ] **비교 페이지 고도화** — 현재 기본 UI만, 데이터 시각화 없음
- [ ] **LLM 연동** — 자연어 리스크 설명 생성 (OpenAI GPT-4o, `services/llm/` 플레이스홀더)
- [ ] **Validator 레이어** — ParseValidator, RuleValidator (`services/validator/` 플레이스홀더)
- [ ] **Report 모듈** — 구조화 리포트 출력 (`services/report/` 플레이스홀더)
- [ ] **Private 대시보드** — 입찰 제안 + 수익률 시뮬레이션 (비공개)
- [ ] **Nginx 리버스프록시** — 현재 uvicorn 직접 노출 중 (Cloudflare Tunnel 경유)
- [ ] **Hard Stop 확장** — HS-F01 유치권, HS-F02 점유 분쟁 (매각물건명세서 파싱 필요)
- [ ] **ML 모델 고도화** — 피처 확장 (시계열, 지역 이벤트), 앙상블, A/B 테스트

---

## 5. API 엔드포인트

> 실행: `cd backend && uvicorn app.main:app --reload`
> Swagger UI: http://localhost:8000/docs

### v1 — DB 기반 대시보드 API (현재 사용)

| 메서드 | 엔드포인트 | 설명 | 상태 |
|--------|-----------|------|------|
| GET | `/api/v1/auctions` | 물건 목록 (DB, 필터/정렬/페이지네이션) | ✅ |
| GET | `/api/v1/auctions/map` | 지도용 좌표 목록 (좌표 있는 물건만, 최대 2000건) | ✅ |
| GET | `/api/v1/auctions/{case_number}` | 물건 상세 (DB 기반, 등급/점수/낙찰/임대료/default_loan_rate 포함) | ✅ |
| POST | `/api/v1/auth/upsert` | OAuth 사용자 upsert + JWT 발급 | ✅ Phase I |
| GET | `/api/v1/users/me` | 현재 사용자 정보 | ✅ Phase I |
| GET | `/api/v1/users/me/favorites` | 즐겨찾기 목록 | ✅ Phase I |
| PUT | `/api/v1/users/me/favorites/{case_number}` | 즐겨찾기 추가 | ✅ Phase I |
| DELETE | `/api/v1/users/me/favorites/{case_number}` | 즐겨찾기 제거 | ✅ Phase I |
| POST | `/api/v1/users/me/favorites/bulk` | localStorage→DB 일괄 동기화 | ✅ Phase I |
| GET | `/api/v1/users/me/saved-searches` | 저장된 검색 조건 목록 | ✅ Phase I |
| POST | `/api/v1/users/me/saved-searches` | 검색 조건 저장 (최대 20개) | ✅ Phase I |
| DELETE | `/api/v1/users/me/saved-searches/{id}` | 저장 검색 삭제 | ✅ Phase I |
| GET | `/api/v1/users/me/telegram` | 텔레그램 연동 상태 조회 | ✅ Phase J |
| POST | `/api/v1/users/me/telegram/code` | 텔레그램 연동 코드 발급 (6자리, 10분 만료) | ✅ Phase J |
| DELETE | `/api/v1/users/me/telegram` | 텔레그램 연동 해제 | ✅ Phase J |
| POST | `/api/v1/telegram/webhook` | 텔레그램 Bot Webhook 수신 (`/start <code>`) | ✅ Phase J |
| GET | `/health` | 헬스 체크 | ✅ |

**주요 쿼리 파라미터 (GET `/api/v1/auctions`)**

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `grade` | 등급 필터 (콤마 구분) | `A,B` |
| `court_office_code` | 법원 코드 | `B000210` |
| `property_type` | 물건 유형 | `아파트` |
| `q` | 주소 키워드 검색 | `강남` |
| `sort` | 정렬 기준 | `grade` / `appraised_value` / `auction_date` / `minimum_bid` / `bid_count` / `discount_rate` / `predicted_winning_ratio` |
| `page` / `size` | 페이지네이션 | `page=1&size=20` |

### v0 — 크롤러 직접 실행 API (레거시)

| 메서드 | 엔드포인트 | 설명 | 상태 |
|--------|-----------|------|------|
| GET | `/api/auctions?court_code=B000210` | 법원별 목록 (매 요청마다 크롤링) | ✅ |
| GET | `/api/auctions/{case_number}` | 개별 물건 상세 | ✅ |
| POST | `/api/auctions/analyze` | 단일 물건 즉시 분석 (주소 입력) | ✅ |
| GET | `/api/registry/{unique_no}` | 등기부 분석 단독 조회 | ✅ |

---

## 6. 룰 엔진 개요

### Hard Stop (자동 제외) — ✅ 구현 완료

> `registry_rules.py` + `registry_analyzer.py`. 말소되지 않은(canceled=False) 이벤트만 매칭.

| 코드 | 조건 | 탐지 기준 |
|------|------|----------|
| HS001 | 예고등기 존재 | 갑구에 예고등기 (말소 안 된 것) |
| HS002 | 신탁등기 존재 | 갑구에 신탁 (말소 안 된 것) |
| HS003 | 가처분등기 존재 | 갑구에 가처분 (말소 안 된 것) |
| HS004 | 환매특약등기 존재 | 갑구에 환매특약 (말소 안 된 것) |
| HS005 | 법정지상권 성립 요건 | 토지/건물 소유자 상이 + 저당권 설정 시 동일소유 |
| HS006 | 담보 외 가등기 | 갑구에 가등기, "담보" 키워드 제외 |
| HS007 | 말소기준 이전 지상권 | 기준권리 이전 설정 지상권 (인수 위험) |
| HS008 | 말소기준 이전 지역권 | 기준권리 이전 설정 지역권 (인수 위험) |

**Hard Stop 확장 예정 (미구현):**

| 코드 | 조건 | 필요 데이터 |
|------|------|-----------|
| HS-F01 | 유치권 신고/정황 | 매각물건명세서 + 현황조사서 파싱 |
| HS-F02 | 점유/임대차 분쟁 정황 | 현황조사서 + 임차인 데이터 |

### 점수 체계 — ✅ 구현 완료

| 항목 | 가중치 (아파트) | 가중치 (꼬마빌딩) | 가중치 (토지) | 구현 상태 |
|------|--------------|----------------|------------|---------|
| 법률 리스크 | 20% | 35% | 25% | ✅ LegalScorer |
| 가격 매력도 | 25% | 20% | 15% | ✅ PriceScorer |
| 입지 점수 | 30% | 15% | 50% | ✅ LocationScorer |
| 명도 리스크 | 25% | 30% | 10% | ✅ OccupancyScorer |

> 4개 pillar 모두 가동. 현황조사서 미수집 물건은 재정규화 후 잠정 등급 표시 (`grade_provisional=True`).

### 등급 기준

| 등급 | 점수 | 의미 |
|------|------|------|
| A | 80점 이상 | 검토 권장 |
| B | 60~80점 | 주의 후 검토 |
| C | 40~60점 | 신중 검토 |
| D | 40점 미만 | 리스크 높음 |

### Public 금지 용어

| 금지 | 대체 표현 |
|------|----------|
| 예측 | "유사 사례 참고 데이터" |
| 적정가 | 사용 금지 |
| 입찰가 | "최저매각가격" (법원 공식 용어) |
| 추천 | "체크 결과" 또는 "필터링 결과" |

---

## 7. 데이터 수집 파이프라인 (2단 구조 + 낙찰 추적)

```
[1단 수집: 무료] ✅                    [2단 수집: CODEF API] ✅
대법원 경매정보 (httpx)                CODEF 주소검색 → 고유번호
건축물대장 (data.go.kr)          →    CODEF 등기부열람 → JSON
Vworld (용도지역/주소)                 CodefMapper → RegistryDocument
실거래가/임대료 (data.go.kr)           RegistryAnalyzer → 리스크 분석
카카오 Geocode+카테고리 (좌표/입지)         │
     │                                   ▼
     ▼                            RegistryAnalysisResult
enricher → filter_engine           (말소기준, 인수/소멸, HardStop 8종)
  RED → 제외 (CostGate 차단)              │
  YELLOW/GREEN → 2단 진행 ──────────────┘
     │
     ▼
  RuleEngineV2 → EvaluationResult
  (Legal + Price + Location + Occupancy + Total → 등급 A/B/C/D)
     │
     ▼
  WinningBidPredictor (CatBoost ml_v1, fallback rule_v1)
  → predicted_ratio + predicted_price + confidence + top_factors
     │
     ▼
  DB 저장 (Auction + Score + FilterResultORM + OccupancyReport)

[낙찰 추적: 사후 수집] ✅
SaleResultCollector (매일 06:00) → 전국 낙찰 완료 건 수집 (statNum="5")
WinningBidCollector (매주 일 07:00) → 기수집 물건 낙찰가 사후 추적
→ actual_winning_bid/ratio/prediction_error → Score 업데이트 (백테스트 재료)
```

**1단 필터링 룰:**
- RED: R001 그린벨트, R002 위반건축물, R003 토지단독
- YELLOW: Y001 유찰3회, Y002 시세괴리30%, Y003 건축물대장미확인
- CostGate: RED → 2단 차단, YELLOW/GREEN → 2단 진행

**예측 낙찰가율 (5F 캘리브레이션, 서울 7,134건 기준):**

| 유찰 횟수 | 아파트 | 꼬마빌딩 | 토지 |
|---------|--------|---------|------|
| 0회 | 0.80 (실측 중앙값) | 0.63 (실측) | 0.54 (실측) |
| 1회 | 0.90 | 0.80 | 0.75 |
| 2회 | 0.80 | 0.70 | 0.65 |
| 3회+ | 0.70 이하 | 0.60 이하 | 0.55 이하 |

**ML 낙찰가율 예측 (Phase 8-1~8-4):**

| 항목 | 내용 |
|------|------|
| 모델 | CatBoost Regressor (`ml_v1`) |
| 피처 | 21개 (할인율, 유찰횟수, 4개 점수, 입지, 임차인, rolling 통계 등) |
| 학습 데이터 | 서버 DB 낙찰 완료 건 (auctions + scores + occupancy_tenants JOIN) |
| 추론 | WinningBidPredictor 싱글톤 (서버 메모리 상주, 모델 없으면 rule_v1 fallback) |
| 신뢰도 | high (학습 표본 충분) / medium / low (외삽 구간) |
| 재학습 | `retrain_model.py` (월 1회 권장, 개선 시에만 모델 교체) |
| 프론트엔드 | PredictionPill 신뢰도 뱃지 + 주요 영향 요인 top 3 표시 |

> "모델 추정 범위 (참고)" — Public API/UI에서 사용하는 표현. "예측"/"AI 예측" 등 금지.

---

## 8. 인프라 구성

| 용도 | URL | 호스팅 |
|------|-----|--------|
| 프론트엔드 | `https://kyungsa.com` | Vercel (`kyungsa-frontend` 프로젝트) |
| 백엔드 API | `https://api.kyungsa.com` | Cloudflare Tunnel → 홈서버:8000 |

### 홈서버 (MSI GP75 Leopard 9SD)

- **OS**: Ubuntu Server 24.04.4 LTS (headless), 호스트명 `kyungsa-server`
- **스펙**: i7-9750H, 16GB RAM, 238GB NVMe
- **네트워크**: WiFi (wlo1), 내부 192.168.45.59, Tailscale 100.71.156.101
- **SSH**: `ssh homeserver` (내부) / `ssh homeserver-remote` (Tailscale 외부)

### systemd 서비스

| 서비스 | 역할 | 실행 시각 |
|--------|------|---------|
| `kyungsa.service` | FastAPI 백엔드 (port 8000) | 상시 |
| `cloudflared.service` | Cloudflare Tunnel | 상시 |
| `kyungsa-batch.timer` | 일일 배치 수집 (`--all-courts`, 서울+경기 전체) + 알림 발송 | 매일 03:00 |
| `kyungsa-occupancy.timer` | 진행 물건 현황조사서 수집 | 매일 04:00 |
| `kyungsa-fix-past-due.timer` | 기일경과 물건 상태 복원 | 매일 04:30 |
| `kyungsa-sale-results.timer` | 전국 낙찰 완료 건 수집 | 매일 06:00 |
| `kyungsa-winning-bids.timer` | 낙찰가 사후 추적 | 매주 일 07:00 |

### 환경변수

**백엔드 `.env`:**
```
DATABASE_URL, PUBLIC_DATA_API_KEY, KAKAO_REST_API_KEY, VWORLD_API_KEY
CODEF_CLIENT_ID, CODEF_CLIENT_SECRET, CODEF_PUBLIC_KEY
CODEF_SERVICE_TYPE=sandbox|demo|production   # 기본값: sandbox
CODEF_SANDBOX_CLIENT_ID, CODEF_SANDBOX_CLIENT_SECRET
CODEF_DEMO_CLIENT_ID, CODEF_DEMO_CLIENT_SECRET
IROS_PHONE_NO, IROS_PASSWORD                 # 인터넷등기소 비회원 로그인
IROS_EPREPAY_NO, IROS_EPREPAY_PASS           # 전자민원캐시 (700원/건)
OPENAI_API_KEY
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID        # 배치 알림
TELEGRAM_WEBHOOK_SECRET                      # ⭐ Phase J: Webhook 검증
DEFAULT_LOAN_RATE=0.045
JWT_SECRET          # Phase I: 임의 랜덤 문자열 (프론트 AUTH_SECRET과 무관)
```

**프론트엔드 Vercel 환경변수:**
```
NEXT_PUBLIC_API_BASE_URL=https://api.kyungsa.com
NEXT_PUBLIC_KAKAO_MAP_KEY=<JS 앱 키>
NEXTAUTH_URL=https://kyungsa.com          # Phase I
AUTH_SECRET=<랜덤>                         # Phase I
AUTH_GOOGLE_ID=<Google Cloud Console>     # Phase I
AUTH_GOOGLE_SECRET=<Google Cloud Console> # Phase I
NEXT_PUBLIC_TELEGRAM_BOT=<봇 username>    # ⭐ Phase J: TelegramModal 봇 링크용
```

### 배포 흐름

```
Mac (개발) → git push → GitHub
                            ↓
               Vercel 자동 빌드 → kyungsa.com
                            ↓
               서버: git pull → pip install -r requirements.txt
                             → alembic upgrade head
                             → systemctl restart kyungsa
```

---

## 9. 검증 체계

```
[수집] → [검증①: 파싱 신뢰도] → [정규화] → [룰 적용] → [검증②: 이상치] → [리포트] → [검증③: 기준일/면책]
```

| 검증 위치 | 내용 | 구현 상태 |
|-----------|------|---------|
| 수집 직후 | 파싱 신뢰도 점수, 권리 유형 분류 확신도 | ❌ 플레이스홀더 |
| 룰 적용 후 | 감정가 vs 최저가 괴리 등 이상치 | ❌ 플레이스홀더 |
| 리포트 출력 전 | 데이터 기준일, 금지 표현 재작성 | ❌ 플레이스홀더 |
| 등급 커버리지 | score_coverage < 0.70 → grade_provisional=True | ✅ |
| E2E 검증 | 실제 물건 10건 파이프라인 통과 | ✅ |

---

## 10. 개발 규칙

### 커밋 컨벤션

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정
rule: 룰 엔진 변경 (반드시 백테스트 동반)
test: 테스트 추가/수정
refactor: 리팩토링
chore: 빌드, 설정 변경
```

### 룰 엔진 변경 프로토콜

```
1. docs/rules/*.md 에 변경 내용 먼저 기록
2. backtest_scores.py 실행하여 영향도 확인
3. 코드 반영
4. 테스트 통과 확인
5. README.md 체크리스트 업데이트
```

---

## 11. 변경 이력

| 날짜 | 변경 내용 | 비고 |
|------|----------|------|
| 2026-02-07 | v1.0 초기 계획 수립 | 0단계 시작 |
| 2026-02-07 | v1.1~1.2 교차검증 반영 | 룰셋 분리, Public 금지어 정의 |
| 2026-02-08 | API 클라이언트 구현 + 연결 테스트 | Mock 19개, 실 API 4/7 성공 |
| 2026-02-08 | 대법원 경매정보 크롤러 구현 | DTO 8개, 테스트 38개 |
| 2026-02-09 | 대법원 크롤러 E2E 검증 완료 | mock 40개 통과 |
| 2026-02-09 | 1단 필터링 파이프라인 구현 | Enricher + FilterEngine + CostGate, 95개 |
| 2026-02-10 | RegistryParser + RegistryAnalyzer 구현 | HardStop 5종, 75개 |
| 2026-02-10 | CODEF 등기부등본 연동 구현 | 실제 응답 구조 확인 + mapper 재작성 |
| 2026-02-13 | 3A 파이프라인 통합 + 3B API 완료 | **총 374개 통과** |
| 2026-02-14 | 4E CODEF 전면 교정 | CF-12826/12411/13328 해소, **391개 통과** |
| 2026-02-15 | 5-0 홈서버 세팅 + 5A DB ORM | **421개 통과** |
| 2026-02-16 | 5B 배치 수집기 완료 | **434개 통과** |
| 2026-02-16 | 5C 법률 점수 엔진 완료 | LegalScorer (근저당/가압류 곡선) |
| 2026-02-16 | 5D 가격 매력도 점수 엔진 완료 | PriceScorer (할인율/시세대비 곡선) |
| 2026-02-16 | 5E RuleEngine v2 통합 완료 | TotalScorer + 등급 A/B/C/D |
| 2026-02-17 | 5.5 HardStop 확장 + 낙찰가율 예측 | HS006~008 + _PREDICTED_RATIO_TABLE |
| 2026-02-17 | 6.5a WinningBidCollector 완료 | 낙찰가 사후 추적 (매주 일 07:00) |
| 2026-02-17 | Phase 6 입지 점수 엔진 완료 | LocationScorer (역/상권/학교 곡선) |
| 2026-02-18 | 5F 백테스트 + 캘리브레이션 완료 | 7,134건 실측, 예측 오차 교정 |
| 2026-02-18 | 6.5b SaleResultCollector + 전국 확장 | 매일 06:00 전국 낙찰 완료 건 수집 |
| 2026-02-18 | cron 자동화 3종 systemd timer 추가 | **588개 통과** |
| 2026-02-19 | Phase 8 프론트엔드 완료 | kyungsa.com + api.kyungsa.com 배포 |
| 2026-02-20 | Phase 7-1~7-4 명도 데이터 완료 | 현황조사서 파서 + OccupancyScorer + 4 pillar, **668개 통과** |
| 2026-02-21 | Phase 8-1 ML 데이터 파이프라인 | FeatureEngineer (21개 피처) + PredictionDataPipeline |
| 2026-02-21 | Phase 8-2 CatBoost 학습 | ModelTrainer (5-fold CV) + train/evaluate 스크립트 |
| 2026-02-22 | Phase 8-3 ML 추론 API | WinningBidPredictor 싱글톤 + retrain_model.py + 서버 배포 |
| 2026-02-22 | Phase 9 UX 재설계 완료 | 랜딩/검색 분리, MobileNav, Framer Motion |
| 2026-02-23 | Phase 8-4 프론트엔드 ML 통합 | MLPrediction 타입 + PredictionPill + top_factors, **734개 통과** |
| 2026-03-04 | Phase B-1 + C UX 개선 | CoveragePill variant + 클라이언트 필터 + 비교 탭 |
| 2026-03-05 | Phase D 리스트 뷰 + 네비게이션 | AuctionListRow + SearchResultsList + 할인율순 + 모바일 4탭 |
| 2026-03-05 | Phase E 홈 3섹션 + 점수 근거 | 이번 주 기일/높은 평가 + pillar Accordion + 기일 0원 필터링 |
| 2026-03-05 | Phase F 권리분석 잠금 + 등급 근거 | 등기부 열람 CTA + 등급/ML Tooltip + 검색 등급 범례 |
| 2026-03-06 | Phase G 투자 시뮬레이터 | InvestmentCalculator + MobileActionBar + 키워드 검색 |
| 2026-03-06 | Phase H-1 건축물대장 표시 수정 | BuildingInfo 모델 확장 + converter 보존 + 건물 정보 자동 표시, **763개 통과** |
| 2026-03-07 | Phase H-2 월세 실거래가 API | rent_price_info 컬럼 + 면적구간별 임대료 집계 (6 bins) |
| 2026-03-07 | Phase H-3 대출 금리 자동 채움 | DEFAULT_LOAN_RATE 환경변수 → API → InvestmentCalculator 초기값 |
| 2026-03-07 | Phase H-4 InvestmentCalculator 전면 개편 | 룸 테이블 + 면적구간별 참고 임대료 + 다방/네이버 링크 |
| 2026-03-08 | Phase I 사용자 인증 시스템 | Google OAuth + JWT + 즐겨찾기/저장검색 DB + localStorage 마이그레이션 |
| 2026-03-08 | Alembic heads 병합 | 4d0e491c6f8f merge (b1c2d3e4f5a6 + d2e3f4a5b6c7) |
| 2026-03-16 | Phase K-2 검색 페이지 전면 재설계 | 사이드바 필터 + 고정폭 테이블 + 리스크 신호등 + property-category/risk-signals lib |
| 2026-03-20 | 현금흐름 분석 페이지 버그 수정 | ResultCard `"use client"` + 임대 수익률 항상 표시 + 면적 소수점 `formatArea()` + `toFixed(1)` |
| 2026-03-20 | Phase H-5 상가 임대료 레퍼런스 완료 | 한국부동산원 R-ONE API + 면적구간별 임대료 밴드 |
| 2026-03-21 | Phase DB-REBUILD 완료 | 정규화 11컬럼 추출 + auction_rounds 테이블 신설 (5e6f7a8b9c0d) |
| 2026-03-21 | Phase J 텔레그램 인프라 완료 | telegram_verifications + Webhook + TelegramModal + 코드 발급 API (e3f4a5b6c7d8) |
| 2026-03-21 | 호실 면적 ×100 버그 수정 | expoArea 우선 + min 방어로 공용부 잘못된 값 차단 |
| 2026-03-22 | 버그 수정 2건 | RoundTimeline 예정/진행중 + 역이름 location_data fallback |
| 2026-03-22 | SearchSidebar 저장 검색 태그 UI 개선 | 전체 너비 태그 + summarizeParams + activeSearchId 토글 |
| 2026-03-24 | Phase 10 ML 재학습 + rule_v1 캘리브레이션 | CatBoost MAE 18.2%→7.2%, ml_v1 파이프라인 연결, 3,716건 재채점 |
| 2026-03-27 | property_sequence 다물건 지원 | Alembic f8a9b0c1d2e3 + UNIQUE(case_number,seq) + batch_collector 키 분리 + API ?seq=N |
| 2026-03-27 | GYEONGGI_COURTS 법원 코드 전면 수정 | DB 실측값 기준 9개 법원으로 전면 교체 (수원/성남/인천/부천/고양/평택/안양/남양주/안산) |
| 2026-03-27 | kyungsa-batch.service 수정 | --all-courts + send_alerts.py + TimeoutStartSec=7200, deploy/ 동기화 |
