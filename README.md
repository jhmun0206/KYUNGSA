# 🏠 KYUNGSA — 부동산 경매 큐레이션 서비스

> **경매 물건의 리스크를 자동으로 구조화해서, 볼 가치가 없는 70%를 먼저 걸러주는 서비스**

## 📌 프로젝트 상태

| 항목 | 상태 |
|------|------|
| 프로젝트명 | KYUNGSA |
| 현재 단계 | `5A 완료` → 다음: 5B (배치 수집기) |
| 최종 업데이트 | 2026-02-15 |
| 테스트 | 421개 통과 |
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

> UI/API 설계는 아래 시나리오를 기준으로 움직인다.

**페르소나 A: 김경매 (본인 — 1차 타겟)**
- 경희대 컴공 4학년, 경매 초중급, 꼬마빌딩 투자 관심
- 고충: 물건이 수백 건인데 등기부 하나하나 열어보기엔 시간/비용 부족
- 시나리오: "이번 주 서울 경매 예정 꼬마빌딩 중 Hard Stop에 안 걸리는 물건만 보여줘" → 필터링 목록 확인 → 관심 물건 리포트 열람 → Private 대시보드에서 적정가 확인

**페르소나 B: 박초보 (Public 서비스 대상)**
- 30대 직장인, 경매 입문자, 아파트/빌라 관심
- 고충: 권리분석이 뭔지도 모르겠고, 위험한 물건을 잘못 입찰할까 두렵다
- 시나리오: "서울 강남 아파트 경매 물건 검색" → 리스크 신호등으로 위험도 한눈에 확인 → "왜 위험한지" 자연어 설명 읽기 → 현장 확인 체크리스트 출력

**페르소나 C: 이중급 (확장 타겟)**
- 40대, 경매 5건 이상 경험, 효율화 니즈
- 고충: 분석은 할 줄 아는데 매번 수작업이 비효율적
- 시나리오: "조건 저장해두면 신규 물건 나올 때 알림" → 알림 수신 → 리포트 빠르게 확인 → 입찰 결정

---

## 2. 기술 스택

```
Backend:    Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2.0 / Alembic
DB:         PostgreSQL 16 (홈서버 확정)
Cache:      인메모리 (dict/lru_cache) → Redis (필요 시)
Scheduler:  APScheduler 또는 시스템 cron
Crawling:   httpx + Playwright (대법원 E2E)
Registry:   CODEF API (등기부등본 자동 조회) + PyMuPDF (PDF 백업)
Crypto:     pycryptodome (CODEF RSA 암호화)
Geo/API:    카카오 Geocode, Vworld, data.go.kr (실거래가, 건축물대장)
LLM:        OpenAI API (리스크 설명 생성, 미착수)
Server:     Ubuntu Server 24.04 LTS + systemd + Nginx — MSI GP75 홈서버
Dev Tool:   Claude Code
Repository: KYUNGSA/
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
│   │   ├── config.py            # 환경변수 설정 (Pydantic BaseSettings)
│   │   ├── api/                 # ⭐ API 레이어
│   │   │   ├── auctions.py     # 경매 API 라우터 (4 엔드포인트)
│   │   │   ├── schemas.py      # API 응답/요청 스키마 + 변환 함수
│   │   │   └── dependencies.py # 의존성 주입 (싱글톤 서비스)
│   │   ├── models/              # Pydantic 모델
│   │   │   ├── auction.py       # 대법원 경매 DTO (ListItem, CaseDetail 등 8개)
│   │   │   ├── enriched_case.py # 1단+2단 통합 모델 (EnrichedCase, FilterResult, PipelineResult)
│   │   │   ├── registry.py      # 등기부 모델 (RegistryEvent, RegistryDocument, RegistryAnalysisResult)
│   │   │   └── ...
│   │   ├── services/            # ⭐ 비즈니스 로직 (핵심)
│   │   │   ├── crawler/         # 1단 데이터 수집
│   │   │   │   ├── court_auction.py         # 대법원 HTTP 클라이언트 (✅ E2E 검증)
│   │   │   │   ├── court_auction_parser.py  # 대법원 JSON 파서
│   │   │   │   ├── codef_client.py          # CODEF OAuth2 클라이언트 (✅ 토큰/재시도)
│   │   │   │   ├── geo_client.py            # 카카오 Geocode + Vworld (✅)
│   │   │   │   └── public_api.py            # data.go.kr 실거래가/건축물대장 (✅)
│   │   │   ├── parser/          # 등기부 파싱
│   │   │   │   ├── registry_parser.py       # PDF/텍스트 → RegistryDocument (✅ 40개 테스트)
│   │   │   │   └── registry_analyzer.py     # 말소기준 + 인수/소멸 + HardStop (✅ 35개 테스트)
│   │   │   ├── registry/        # ⭐ CODEF 등기부 연동
│   │   │   │   ├── provider.py              # RegistryProvider ABC
│   │   │   │   ├── codef_provider.py        # CODEF API 호출 (✅ 실 응답 검증)
│   │   │   │   ├── codef_mapper.py          # CODEF JSON → RegistryDocument (✅ 46개 테스트)
│   │   │   │   ├── matcher.py              # ⭐ CODEF 검색결과 매칭 (지번/건물명)
│   │   │   │   └── pipeline.py              # 주소→등기부→분석 파이프라인 (✅ 27개 테스트)
│   │   │   ├── address_parser.py # ⭐ 주소 파싱 (경매주소→CODEF 파라미터)
│   │   │   ├── enricher.py      # 1단 데이터 보강 (geocode→용도→건물→시세)
│   │   │   ├── filter_engine.py # FilterEngine + CostGate
│   │   │   ├── filter_rules.py  # RED(R001~R003) + YELLOW(Y001~Y003)
│   │   │   ├── pipeline.py      # ⭐ 1단+2단 통합 AuctionPipeline
│   │   │   ├── registry_rules.py # HardStop 5종 (HS001~HS005)
│   │   │   ├── rules/           # (플레이스홀더, 미구현)
│   │   │   ├── validator/       # (플레이스홀더, 미구현)
│   │   │   ├── report/          # (플레이스홀더, 미구현)
│   │   │   └── llm/             # (플레이스홀더, 미구현)
│   │   └── tasks/
│   ├── tests/                   # 421개 테스트 전체 통과
│   │   ├── test_crawler/        # 61개 (대법원40 + 기타19 + URL2)
│   │   ├── test_enricher.py     # 22개
│   │   ├── test_filter_engine.py # 27개
│   │   ├── test_pipeline.py     # 18개 (1단8 + 2단통합10)
│   │   ├── test_address_parser.py   # 29개 (도로명/지번/정규화/엣지)
│   │   ├── test_registry_matcher.py # 13개 (지번/건물명/부분일치/매칭실패)
│   │   ├── test_registry_parser.py  # 40개
│   │   ├── test_registry_analyzer.py # 35개
│   │   ├── test_registry_codef.py   # 62개 (mapper+provider+RSA+validation)
│   │   ├── test_registry_pipeline.py # 27개 (2단 파이프라인)
│   │   ├── test_api_schemas.py      # 16개 (스키마 변환)
│   │   ├── test_api_auctions.py     # 17개 (엔드포인트)
│   │   └── fixtures/            # mock 데이터
│   │       ├── codef_registry_response.json
│   │       └── registry_sample_*.txt
│   └── requirements.txt
├── scripts/                     # CLI 도구
│   ├── run_pipeline.py          # 1단 파이프라인 실행
│   ├── parse_registry.py        # 등기부 파싱 CLI
│   ├── test_codef_registry.py   # CODEF 등기부 실 API 테스트
│   ├── test_all_apis.py         # 전체 API 연결 테스트
│   └── test_pipeline_e2e.py     # E2E 테스트 (Playwright)
└── frontend/                    # (미착수)
```

---

## 4. 로드맵 & 체크리스트

### 0단계: 사전 검증 ✅ 완료

- [x] **데이터 수집 검증**
  - [x] 대법원 경매정보 크롤러 구현 ✅ (CourtAuctionClient + CourtAuctionParser + Pydantic DTO 8개, E2E 검증)
  - [x] 대법원 경매정보 사이트 실제 수집 테스트 ✅ (Playwright E2E 10건)
  - [x] 공공 API 호출 테스트 ✅ (실거래가, 건축물대장, Vworld, 카카오)
  - [x] CODEF API 토큰 발급 ✅
  - [x] CODEF 등기부등본 실 API 호출 성공 ✅ (주소검색 + 등기부열람, 아이파크타워)
  - [x] 1단 필터링 데이터 소스 5개 확정 (대법원, 건축물대장, Vworld, 실거래가, 카카오)
  - [x] 등기정보광장 Open API — **미사용** (지역 통계만 제공, 개별 물건 조회 불가)
- [ ] **법적 지위 확인**
  - [ ] 변호사 자문 예약
  - [ ] 투자자문업 해당 여부 확인

### 1단계: 1단 필터링 파이프라인 ✅ 완료

- [x] **1단 필터링 구현**
  - [x] CaseEnricher (geocode → land_use → building → market_price)
  - [x] FilterEngine (RED > YELLOW > GREEN + CostGate)
  - [x] RED 룰 3종 (R001 그린벨트, R002 위반건축물, R003 토지단독)
  - [x] YELLOW 룰 3종 (Y001 유찰3회, Y002 시세괴리30%, Y003 건축물대장미확인)
  - [x] AuctionPipeline (crawler → enricher → filter) ✅
  - [x] 테스트 57개 통과 (enricher 22 + filter_engine 27 + pipeline 8)

### 2단계: 등기부 분석 파이프라인 ✅ 완료

- [x] **등기부 파서 + 분석기**
  - [x] RegistryParser (PDF/텍스트 → RegistryDocument, EventType 16종)
  - [x] RegistryAnalyzer (말소기준 판별 + 인수/소멸 분류 + HardStop 5종 탐지)
  - [x] 테스트 75개 통과 (parser 40 + analyzer 35)
- [x] **CODEF 등기부 연동**
  - [x] CodefRegistryProvider (주소검색 + 등기부열람 + RSA 암호화)
  - [x] CodefRegistryMapper (CODEF JSON 테이블 형식 → RegistryDocument)
  - [x] RegistryPipeline (주소 → 고유번호 → 등기부 → 분석 일괄)
  - [x] 실제 CODEF 응답 구조 확인 및 매퍼 전면 재작성 ✅
  - [x] 테스트 73개 통과 (mapper+provider 46 + pipeline 27)

### 3단계: 1단+2단 통합 + API ✅ 완료

- [x] **3A: 파이프라인 통합** ✅
  - [x] 주소 샘플 수집 + 주소 파싱 유틸리티 (address_parser.py, 29개 테스트)
  - [x] CODEF 검색결과 매칭 로직 (matcher.py, 13개 테스트)
  - [x] EnrichedCase 2단 필드 추가 (registry_analysis, registry_unique_no, registry_match_confidence, registry_error)
  - [x] AuctionPipeline 2단 통합 (fail-open, RED 건 스킵, 10개 통합 테스트)
  - [x] 전체 341개 테스트 통과
- [x] **3B: API 엔드포인트 구현** ✅
  - [x] `GET /api/auctions` — 법원별 경매 목록 (1단+2단 필터링)
  - [x] `GET /api/auctions/{case_number}` — 개별 물건 상세
  - [x] `POST /api/auctions/analyze` — 단일 물건 즉시 분석
  - [x] `GET /api/registry/{unique_no}` — 등기부 분석 단독 조회
  - [x] API 스키마 + 변환 함수 (schemas.py)
  - [x] 의존성 주입 (dependencies.py, lru_cache 싱글톤)
  - [x] 테스트 33개 (스키마 16 + 엔드포인트 17)
- [ ] DB 스키마 설계 (PostgreSQL) — 5A단계에서 구현 예정

### 4단계: 실전 E2E 검증 ✅ 완료

- [x] 실제 경매 물건 10건으로 전체 파이프라인 E2E 검증 ✅ (ALL_PASS 2/10, PARTIAL 8/10)
- [x] 1단(크롤링→필터) + 2단(CODEF→등기부→분석) 실 데이터 통과 ✅ (registry_full 86%)
- [x] 발견된 버그/파싱 오류 수정 ✅ (4C: Vworld/CF-13007/지번fallback, 4E: CODEF 전면 교정)
- [x] E2E 검증 보고서 작성 ✅ ([4B](docs/review/2026-02-13_e2e_validation.md), [4E](docs/review/2026-02-14_e2e_validation.md))
- [x] **총 391개 테스트 통과** (4E 기준, 5A에서 421개로 증가)

### 5단계: 서버 세팅 + DB + 배치 + MVP 점수 ← **현재**

- [x] **5-0: 홈서버 세팅** ✅
  - [x] Ubuntu Server 24.04 LTS 설치 (MSI GP75 Leopard, headless)
  - [x] PostgreSQL 16 설치 + 튜닝 (shared_buffers=4GB, 16GB RAM 기준)
  - [x] Python 3.11.11 (pyenv) + SSH 키 인증 + UFW 방화벽
  - [x] 프로젝트 배포 (git clone + .env + systemd 서비스 등록)
  - [x] FastAPI 서비스 가동 확인 (/health OK)
  - [x] Tailscale VPN (외부 접속: 100.71.156.101)
  - [x] 서버에서 테스트 전체 통과 확인 (391개, pycryptodome 설치 + validate_phone_no 수정)
- [x] **5A: DB 스키마 + ORM** ✅
  - [x] SQLAlchemy ORM 5개 (Auction, FilterResultORM, RegistryEventORM, RegistryAnalysisORM, PipelineRun)
  - [x] Alembic 초기 마이그레이션 (JSONB + 인덱스)
  - [x] Pydantic ↔ SQLAlchemy 양방향 변환 (converters.py) + roundtrip 검증
  - [x] FastAPI DB 세션 관리 (database.py + dependencies.py)
  - [x] SQLite in-memory 테스트 30개 (CRUD + 제약조건 + roundtrip)
  - [x] **총 421개 테스트 통과** (391 → 421, +30개)
- [ ] **5B: 배치 수집기**
  - [ ] BatchCollector: 대법원 크롤링 → DB 저장
  - [ ] 1단 보강 + 필터링 → DB 저장
  - [ ] cron 스케줄 (주 2~3회 새벽)
  - [ ] 중복 감지 (이미 있는 물건 skip)
- [ ] **5C: 법률 점수 엔진**
  - [ ] 근저당 채권최고액/감정가 비율
  - [ ] 가압류 건수/금액
  - [ ] Hard Stop 5종 통합
  - [ ] 0~100점 산출 공식
- [ ] **5D: 가격 점수 엔진**
  - [ ] 최저가/감정가 할인율
  - [ ] 실거래가 대비 괴리율
  - [ ] 유찰횟수 보정
- [ ] **5E: RuleEngine v2 통합**
  - [ ] 1단(FilterEngine) + 2단(RegistryAnalyzer) + 점수 합침
  - [ ] 룰셋 분리 (꼬마빌딩 vs 아파트)
- [ ] **5F: 백테스트 인프라**
  - [ ] 과거 낙찰 사례 수집 + Hard Stop 라벨링
  - [ ] 백테스트 러너 (Hard Stop 미탐지율 0%)
  - [ ] docs/domain/ 도메인 문서 정비

### 6단계: 입지 데이터

- [ ] 카카오 카테고리 검색 연동 + DB 캐시
- [ ] 입지 점수 엔진 (꼬마빌딩/아파트 분리)

### 7단계: 명도 데이터

- [ ] 대법원 PDF 크롤러 (매각물건명세서/현황조사서)
- [ ] 임차인 파서 (정규식)
- [ ] LLM 파싱 fallback (선택)
- [ ] 명도 점수 엔진
- [ ] Hard Stop 확장 (유치권/분쟁)

### 8단계: 대시보드

- [ ] FastAPI v2 (DB 기반 CRUD)
- [ ] Next.js 물건 리스트 + 필터
- [ ] 물건 상세 (점수 차트 + 분석)
- [ ] 알림 (텔레그램/이메일)

---

## 5. API 엔드포인트 (✅ 구현 완료)

> 실행: `cd backend && uvicorn app.main:app --reload`
> Swagger UI: http://localhost:8000/docs

| 메서드 | 엔드포인트 | 설명 | 상태 |
|--------|-----------|------|------|
| GET | `/api/auctions?court_code=B000210` | 법원별 경매 목록 (1단+2단 필터링) | ✅ |
| GET | `/api/auctions/{case_number}` | 개별 물건 상세 (1단 + 2단) | ✅ |
| POST | `/api/auctions/analyze` | 단일 물건 즉시 분석 (주소 입력) | ✅ |
| GET | `/api/registry/{unique_no}` | 등기부 분석 단독 조회 (CODEF) | ✅ |
| GET | `/health` | 헬스 체크 | ✅ |

### 요청/응답 JSON 예시

**GET `/api/auctions?court_code=B000210&page=1&page_size=20`**
```json
{
  "items": [
    {
      "case_number": "2026타경12345",
      "court_name": "서울중앙지방법원",
      "address": "서울 강남구 역삼동 123-4",
      "appraisal_value": 800000000,
      "minimum_bid": 512000000,
      "auction_date": "2026-03-15",
      "filter_result": "YELLOW",
      "filter_reasons": ["3회 이상 유찰"],
      "has_registry": true,
      "registry_hard_stop": false
    }
  ],
  "total": 47,
  "page": 1,
  "page_size": 20
}
```

**GET `/api/auctions/2026타경12345`**
```json
{
  "case_number": "2026타경12345",
  "court_name": "서울중앙지방법원",
  "address": "서울 강남구 역삼동 123-4",
  "appraisal_value": 800000000,
  "minimum_bid": 512000000,
  "auction_date": "2026-03-15",
  "filter_result": "YELLOW",
  "filter_reasons": ["3회 이상 유찰"],
  "filter_details": { "color": "YELLOW", "passed": true, "rules": [...] },
  "registry": {
    "has_hard_stop": false,
    "cancellation_base": "MORTGAGE (2020.03.15)",
    "surviving_rights": [],
    "extinguished_rights": [...],
    "total_encumbrance": 0,
    "confidence": "HIGH"
  },
  "registry_error": null
}
```

---

## 6. 룰 엔진 개요

### 물건 유형별 룰셋 분리

> ⚠️ 꼬마빌딩은 임차인 다수가 기본값이므로, 아파트와 동일한 룰을 적용하면 과도한 REJECT가 발생한다. 반드시 유형별 룰셋을 분리한다.

| 룰셋 | 파일 | 1차 타겟 |
|------|------|---------|
| 꼬마빌딩 전용 | `rulesets/building_small.py` | ✅ MVP |
| 아파트 | `rulesets/apartment.py` | 확장 |
| 공통 (base) | `rulesets/base.py` | 모든 유형 공유 |

### Hard Stop (자동 제외) — ✅ 구현 완료

> `registry_rules.py` + `registry_analyzer.py`에서 구현. 35개 테스트 검증.
> 말소되지 않은(canceled=False) 이벤트만 매칭한다.

| 코드 | 조건 | 탐지 기준 |
|------|------|----------|
| HS001 | 예고등기 존재 | 갑구에 예고등기 이벤트 (말소되지 않은 것) |
| HS002 | 신탁등기 존재 | 갑구에 신탁 이벤트 (말소되지 않은 것) |
| HS003 | 가처분등기 존재 | 갑구에 가처분 이벤트 (말소되지 않은 것) |
| HS004 | 환매특약등기 존재 | 갑구에 환매특약 이벤트 (말소되지 않은 것) |
| HS005 | 법정지상권 성립 요건 | 토지/건물 소유자 상이 + 저당권 설정시 동일소유 |

### Hard Stop 확장 예정 (미구현)

> 아래 조건은 초기 설계에 포함되었으나, 현재 데이터 소스로는 자동 판별이 어려워 향후 구현 예정.
> 매각물건명세서/현황조사서 파싱이 완료되면 추가한다.

| 코드 | 조건 | 필요 데이터 |
|------|------|-----------|
| HS-F01 | 유치권 신고/정황 | 매각물건명세서 + 현황조사서 파싱 |
| HS-F02 | 점유/임대차 정보 결손 + 분쟁 정황 | 현황조사서 + 임차인 데이터 |

### Hard Stop 라벨 기준 정의

> "미탐지율 0%"를 측정하려면 정답 라벨이 필요하다. 향후 백테스트 시 `backtest/hard_stop_labels.json`에 명문화.

| 라벨 | 정의 | 데이터 근거 |
|------|------|-----------|
| `HS001_PRELIMINARY_NOTICE` | 예고등기 존재 | 등기부 갑구 분석 |
| `HS002_TRUST` | 신탁등기 존재 | 등기부 갑구 분석 |
| `HS003_DISPOSITION` | 가처분등기 존재 | 등기부 갑구 분석 |
| `HS004_REPURCHASE` | 환매특약 존재 | 등기부 갑구 분석 |
| `HS005_SUPERFICIES` | 법정지상권 요건 | 등기부 갑구 + 건물/토지 정보 |

### 점수 체계

| 항목 | 가중치 | 평가 요소 |
|------|--------|----------|
| 법률 리스크 | 30% | 말소기준권리, 가압류/가처분, 임차권 |
| 명도 리스크 | 25% | 점유 상태, 임차인 수, 상가/주거 구분, **분쟁 시그널** |
| 입지 점수 | 25% | 역 거리, 상권, 용도지역 |
| 가격 매력도 | 20% | 감정가 대비 최저가, 유찰, 시세 비교 |

### 계산 책임 분리 (✅ 구현 완료)

```
[등기부 PDF] → RegistryParser ──┐
                                ├→ RegistryDocument → RegistryAnalyzer → RegistryAnalysisResult → RuleEngine (읽기만)
[CODEF API]  → CodefMapper    ──┘
```

### Public 금지 용어

> Public API, 리포트, 문서, UI 어디에서든 아래 용어는 절대 노출 금지. Private 모듈에서만 허용.

| 금지 | 대체 표현 |
|------|----------|
| 예측 | "유사 사례 참고 데이터" |
| 적정가 | 사용 금지 |
| 입찰가 | "최저매각가격" (법원 공식 용어) |
| 추천 | "체크 결과" 또는 "필터링 결과" |

---

## 7. 데이터 수집 파이프라인 (2단 구조, ✅ 구현 완료)

> 비용 최적화를 위해 무료/공개 데이터로 1차 필터링 후, 통과 후보만 유료 조회한다.

```
[1단 수집: 무료] ✅                    [2단 수집: CODEF API] ✅
대법원 경매정보 (httpx)                CODEF 주소검색 → 고유번호
건축물대장 (data.go.kr)          →    CODEF 등기부열람 → JSON
Vworld (용도지역/주소)                 CodefMapper → RegistryDocument
실거래가 (data.go.kr)                 RegistryAnalyzer → 리스크 분석
카카오 Geocode (좌표)                       │
     │                                    ▼
     ▼                            RegistryAnalysisResult
enricher → filter_engine           (말소기준, 인수/소멸, Hard Stop 5종)
  RED → 제외 (CostGate 차단)
  YELLOW/GREEN → 2단 진행 ──→ RegistryPipeline
```

**1단 필터링 룰 (✅ 구현 완료):**
- RED: R001 그린벨트, R002 위반건축물, R003 토지단독
- YELLOW: Y001 유찰3회, Y002 시세괴리30%, Y003 건축물대장미확인
- CostGate: RED → 2단 차단, YELLOW/GREEN → 2단 진행

**2단 등기부 분석 (✅ 구현 완료):**
- CODEF 주소검색 → 고유번호 → 등기부열람 → RegistryDocument → RegistryAnalyzer
- Hard Stop 5종: 예고등기(HS001), 신탁(HS002), 가처분(HS003), 환매(HS004), 법정지상권(HS005)
- 말소기준권리 판별: MORTGAGE > PROVISIONAL_SEIZURE > SEIZURE > AUCTION_START
- 인수/소멸 분류 + 신뢰도 산출 + 요약 생성

**3A 파이프라인 통합 (✅ 구현 완료):**
- 주소 파싱: address_parser.py (도로명/지번 2형식 → CodefAddressParams)
- 매칭: matcher.py (CODEF 검색결과 → 최적 물건 특정, 4단계 신뢰도)
- AuctionPipeline → 1단 필터 → (YELLOW/GREEN만) → 2단 등기부 분석
- Fail-open: 2단 실패해도 1단 결과 유지 (registry_error에 사유 기록)

---

## 8. 검증 체계

```
[수집] → [검증①: 파싱 신뢰도] → [정규화] → [룰 적용] → [검증②: 이상치] → [리포트] → [검증③: 기준일/면책]
```

| 검증 위치 | 내용 | 실패 시 |
|-----------|------|---------|
| 수집 직후 | 파싱 신뢰도 점수, 권리 유형 분류 확신도 | 수동 확인 큐 |
| 룰 적용 후 | 감정가 vs 최저가 괴리 등 이상치 | 플래그 + 수동 리뷰 |
| 리포트 출력 전 | 데이터 기준일, 변동 미반영 고지 | 면책 문구 자동 삽입 |

---

## 9. 개발 규칙

### 커밋 컨벤션

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정 (README, CLAUDE.md, docs/)
rule: 룰 엔진 변경 (반드시 백테스트 동반)
test: 테스트 추가/수정
refactor: 리팩토링
chore: 빌드, 설정 변경
```

### 룰 엔진 변경 프로토콜

```
1. docs/rules/*.md 에 변경 내용 먼저 기록
2. 스프레드시트(또는 backtest.py)로 영향도 확인
3. 코드 반영
4. 테스트 통과 확인
5. README.md 체크리스트 업데이트
```

### README 업데이트 규칙

- 단계 완료 시 체크박스 체크 `[x]`
- 구조 변경 시 프로젝트 구조 섹션 즉시 반영
- 룰 변경 시 룰 엔진 섹션 즉시 반영
- 기술 스택 변경 시 즉시 반영

---

## 10. 변경 이력

| 날짜 | 변경 내용 | 비고 |
|------|----------|------|
| 2026-02-07 | v1.0 초기 계획 수립 | 0단계 시작 |
| 2026-02-07 | v1.1 ChatGPT/Perplexity 교차검증 반영 | 룰셋 분리, 2단 파이프라인, 라벨 기준, DB 강화, 페르소나 추가 |
| 2026-02-07 | v1.2 계산 책임 분리 + Public 금지 용어 | RegistryAnalyzer 신설, HS 강등 규칙, Public 금지어 정의 |
| 2026-02-07 | 프로젝트 초기 디렉토리 구조 생성 | 전체 디렉토리 + placeholder 파일 + requirements.txt |
| 2026-02-08 | API 클라이언트 구현 + 연결 테스트 | CODEF/공공데이터/카카오/Vworld, Mock 19개, 실 API 4/7 성공 |
| 2026-02-08 | 0단계 API 의사결정 확정 | 1단 데이터소스 5개 확정, 1단 필터링 룰 초안 |
| 2026-02-08 | 대법원 경매정보 크롤러 구현 | CourtAuctionClient + Parser + DTO 8개, 테스트 38개 |
| 2026-02-09 | 대법원 크롤러 E2E 검증 완료 | Playwright → 파서 → DTO, 실제 10건 수집, mock 40개 통과 |
| 2026-02-09 | 1단 필터링 파이프라인 구현 | Enricher + FilterEngine + CostGate + Pipeline, 테스트 95개 |
| 2026-02-10 | RegistryParser + RegistryAnalyzer 구현 | PDF/텍스트 등기부 파싱, 말소기준+인수/소멸+HardStop 5종, 테스트 75개 |
| 2026-02-10 | CODEF 등기부등본 연동 구현 | CodefProvider + CodefMapper, mock fixture 기반, 테스트 46개 |
| 2026-02-10 | CODEF 실 API 검증 + 매퍼 재작성 | 실제 응답 구조 발견 (테이블 형식), mapper 전면 재작성, 262개 통과 |
| 2026-02-13 | RegistryPipeline(2단) 구현 | 주소→등기부→분석 일괄, 테스트 27개, **총 289개 통과** |
| 2026-02-13 | CLAUDE.md + README.md 업데이트 | 프로젝트 구조·체크리스트·변경이력 현행화 |
| 2026-02-13 | 3A 파이프라인 통합 완료 | 주소파싱+매칭+1단2단연결, **총 341개 통과** (289→341, +52개) |
| 2026-02-13 | 3B API 엔드포인트 완료 | FastAPI 4개 엔드포인트+스키마+테스트33개, **총 374개 통과** |
| 2026-02-13 | 문서 불일치 7건 정리 + 홈서버 로드맵 재구성 | HS 통일, 기술스택 경량화, 실전검증 단계 삽입 |
| 2026-02-13 | 4B 실전 E2E 검증 실행 | 10건 실행, 0/10 ALL_PASS, BUG 7건 발견 → [보고서](docs/review/2026-02-13_e2e_validation.md) |
| 2026-02-14 | 4C E2E 버그 수정 | Vworld LT_C_UQ111, CF-13007 재시도, 지번 fallback |
| 2026-02-14 | 4E CODEF 등기부 열람 전면 교정 | inquiryType=0, password/ePrepayPass 분리, **391개 통과**, registry_full 86% → [보고서](docs/review/2026-02-14_e2e_validation.md) |
| 2026-02-14 | 로드맵 v2.2 확정 | PostgreSQL 16 확정, 5단계 재구성 (서버세팅+DB+배치+점수), 6~8단계 재편 |
| 2026-02-15 | 5-0 홈서버 세팅 완료 | Ubuntu 24.04 LTS + PostgreSQL 16 + pyenv 3.11 + systemd + Tailscale, /health OK |
| 2026-02-15 | 5A DB 스키마 + ORM 완료 | SQLAlchemy ORM 5개 + Alembic + converter + SQLite 테스트 30개, **421개 통과** |
