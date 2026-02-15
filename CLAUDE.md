# CLAUDE.md — KYUNGSA 개발 지시서

> 이 파일은 Claude Code가 KYUNGSA 프로젝트를 이해하고 일관된 개발을 수행하기 위한 지시서입니다.
> 모든 작업 전에 이 파일을 먼저 읽으세요.

---

## 🎯 프로젝트 핵심 요약

경매 물건의 리스크를 자동으로 구조화하여, 볼 가치가 없는 70%를 먼저 걸러주는 부동산 경매 큐레이션 시스템.

**절대 원칙:**
1. LLM은 자연어 "설명"만 한다. 판단/점수/추천은 반드시 룰/수식 기반.
2. 데이터 검증 레이어 없이는 어떤 분석도 출력하지 않는다.
3. Public 출력에는 투자 추천/판단 문장을 절대 포함하지 않는다.
4. 룰 엔진 변경 시 반드시 백테스트를 동반한다.
5. **`is_before_base`, `will_extinguish`는 RegistryAnalyzer(Parser)가 계산한다. RuleEngine은 파생 필드를 소비만 한다.**
6. **Hard Stop 라벨이 애매하거나 교차검증 결과가 충돌하면, 해당 조건은 Hard Stop이 아닌 Yellow Zone으로 강등한다.**
7. **Public API/문서/리포트에는 '예측', '적정가', '입찰가'를 절대 사용하지 않는다. 해당 개념은 Private 모듈에서만 허용된다.**

---

## 📁 프로젝트 구조 이해

```
KYUNGSA/
├── CLAUDE.md          ← 지금 이 파일. 모든 작업 전에 읽을 것
├── README.md          ← 살아있는 문서. 변경사항 즉시 반영할 것
├── docs/              ← 도메인 지식 + 룰 명세. 코드 전에 여기 먼저 작성
│   ├── domain/        ← 법률/경매 도메인 지식
│   ├── rules/         ← 룰 엔진 명세 (Hard Stop, Yellow Zone, 점수, 라벨 기준)
│   ├── api/           ← API 명세
│   └── review/        ← ⭐ 교차검증 결과 기록 (YYYY-MM-DD_주제.md)
├── backend/           ← Python FastAPI 백엔드
│   ├── app/
│   │   ├── models/    ← Pydantic 모델 (auction, enriched_case, registry)
│   │   ├── api/       ← API 라우터
│   │   ├── services/  ← 비즈니스 로직
│   │   │   ├── crawler/    ← 데이터 수집 (대법원, CODEF, 공공API, Geocode)
│   │   │   ├── parser/     ← 등기부 파싱 + ⭐ RegistryAnalyzer (말소기준권리 판별)
│   │   │   ├── registry/   ← ⭐ CODEF 등기부 연동 (provider, mapper, pipeline)
│   │   │   ├── validator/  ← 검증 레이어
│   │   │   ├── rules/      ← 룰 엔진 (핵심 자산)
│   │   │   │   └── rulesets/  ← 물건 유형별 룰셋 분리
│   │   │   ├── report/     ← 리포트 생성
│   │   │   └── llm/        ← LLM 연동 (설명 전용)
│   │   ├── enricher.py     ← 1단 데이터 보강 (geocode → 용도지역 → 건축물대장 → 시세)
│   │   ├── filter_engine.py ← 1단 RED/YELLOW/GREEN 필터링 + CostGate
│   │   ├── filter_rules.py  ← RED(R001~R003) + YELLOW(Y001~Y003) 룰 함수
│   │   ├── pipeline.py      ← 1단 파이프라인 (crawler → enricher → filter)
│   │   └── registry_rules.py ← 2단 Hard Stop 5종 (HS001~HS005)
│   │   └── tasks/     ← 스케줄러 (APScheduler/cron, 미구현)
│   ├── config/        ← ⭐ 설정 파일 (banned_phrases.json 등)
│   └── tests/
├── scripts/           ← CLI 스크립트 (run_pipeline, parse_registry, test_codef_registry 등)
└── frontend/          ← Next.js 프론트엔드
```

---

## 🔧 기술 스택 & 규칙

### 백엔드
- **Python 3.11+**, **FastAPI**, **SQLAlchemy 2.0**, **Alembic**
- DB: **PostgreSQL 16** (홈서버 확정, Ubuntu Server 24.04 LTS)
- ORM: SQLAlchemy 2.0 + Alembic (마이그레이션)
- 캐시: 인메모리 (dict/lru_cache) → Redis (필요 시 추가)
- 스케줄러: APScheduler 또는 시스템 cron (Celery 불필요)
- 인프라: Ubuntu Server + systemd + Nginx (Docker는 Phase 8+ 선택)
- 타입 힌트 필수, docstring 필수
- 함수 하나는 하나의 역할만

### 프론트엔드
- **Next.js** (App Router) + **TypeScript**
- 컴포넌트는 서버/클라이언트 명확히 분리
- API 호출은 `lib/` 아래에 모아서 관리

### 공통
- 한국어 주석 사용 (코드는 영어, 주석/문서는 한국어)
- 에러 메시지는 한국어로 작성
- 환경변수는 `.env` 관리, 절대 하드코딩 금지

---

## ⭐ 핵심 데이터 모델 정의

> 아래는 **초기 설계 참조 모델**이다. 실제 구현 모델은 다음 파일을 참조:
> - `backend/app/models/auction.py` — AuctionCaseListItem, AuctionCaseDetail 등 (Pydantic DTO 8개)
> - `backend/app/models/enriched_case.py` — EnrichedCase, FilterResult, PipelineResult
> - `backend/app/models/registry.py` — RegistryEvent, RegistryDocument, RegistryAnalysisResult
> - `backend/app/api/schemas.py` — API 응답 스키마 (AuctionItemSummary, AuctionDetailResponse 등)
>
> **설계 모델과 구현이 다른 경우, 구현이 우선한다.**

```python
# === 초기 설계 참조 모델 (실제 구현은 위 파일 참조) ===

@dataclass
class Auction:
    """경매 물건 기본 정보"""
    id: str                      # UUID
    case_number: str             # 사건번호 "2026타경12345"
    court: str                   # 관할 법원
    address: str                 # 소재지
    property_type: str           # "꼬마빌딩" | "아파트" | "빌라" | "다세대" | "토지"
    appraised_value: int         # 감정가 (원)
    minimum_bid: int             # 최저입찰가 (원)
    auction_date: date           # 입찰일
    auction_count: int           # 회차 (유찰 횟수 + 1)
    status: str                  # "예정" | "진행" | "낙찰" | "유찰"
    rights: list[Right]          # 등기부 권리 목록
    tenants: list[Tenant]        # 임차인 목록
    documents: AuctionDocuments  # 서류 데이터

@dataclass
class Right:
    """등기부 권리 항목"""
    id: str
    right_type: str              # "근저당" | "가압류" | "전세권" | "가처분" | ...
    holder: str                  # 권리자
    amount: int | None           # 채권액
    accepted_at: date            # 접수일 (⭐ ChatGPT 피드백 반영)
    registered_at: date          # 설정일
    registration_seq: int        # 등기 순번 (⭐ 접수번호 기준 정렬)
    registry_section: str        # "갑구" | "을구" (⭐ 갑/을구 구분)
    raw_text: str                # 원문 근거 텍스트 (⭐ 파싱 검증용)
    is_before_base: bool         # 말소기준권리 이전 여부 (⭐ RegistryAnalyzer가 계산)
    will_extinguish: bool        # 소멸 예정 여부 (⭐ RegistryAnalyzer가 계산)
    # ※ is_before_base, will_extinguish는 RegistryAnalyzer/Parser가 산출하는 파생 필드.
    #    RuleEngine은 이 값을 읽기만 한다. 절대 RuleEngine에서 재계산하지 말 것.

@dataclass
class Tenant:
    """임차인 정보"""
    name: str
    deposit: int | None          # 보증금
    has_opposing_power: bool     # 대항력 여부
    fixed_date: date | None      # 확정일자
    requested_dividend: bool     # 배당요구 여부
    occupancy_confirmed: bool    # 점유 확인 여부

# === 출력 모델 ===

@dataclass
class RuleResult:
    """룰 엔진 평가 결과"""
    status: str                  # "PASS" | "REVIEW" | "REJECT"
    hard_stop_codes: list[str]   # ["HS001", "HS003"] (빈 리스트면 통과)
    hard_stop_reasons: list[str] # 사유 문자열
    warnings: list[Warning]      # Yellow Zone 경고 목록
    scores: Scores               # 4개 영역 점수
    total_score: float           # 가중 합산
    ruleset_used: str            # "building_small" | "apartment" | "base"

@dataclass
class Scores:
    """4개 영역 점수 (0~100, 높을수록 좋음)"""
    legal: float                 # 법률 리스크 (가중치 0.30)
    eviction: float              # 명도 리스크 (가중치 0.25)
    location: float              # 입지 (가중치 0.25)
    price: float                 # 가격 매력도 (가중치 0.20)
    
    def weighted_total(self) -> float:
        return self.legal * 0.30 + self.eviction * 0.25 + self.location * 0.25 + self.price * 0.20

@dataclass
class Warning:
    code: str                    # "YZ-001"
    message: str
    severity: str                # "LOW" | "MEDIUM" | "HIGH"
```

---

## ⭐ 핵심 모듈 상세 지시

### 1. 룰 엔진 (`services/rules/`)

이것이 프로젝트의 가장 핵심 자산이다.

```python
# engine.py 구조
class RuleEngine:
    def __init__(self, property_type: str):
        """물건 유형에 따라 적절한 룰셋 로드"""
        self.ruleset = self._load_ruleset(property_type)
    
    def _load_ruleset(self, property_type: str) -> BaseRuleset:
        """꼬마빌딩 → building_small, 아파트 → apartment, 기타 → base"""
        mapping = {
            "꼬마빌딩": BuildingSmallRuleset(),
            "아파트": ApartmentRuleset(),  # 확장 시 구현
        }
        return mapping.get(property_type, BaseRuleset())
    
    def evaluate(self, auction: Auction) -> RuleResult:
        """
        1단계: Hard Stop 체크 → 하나라도 걸리면 즉시 REJECT
        2단계: Yellow Zone 체크 → 경고 플래그 부착
        3단계: 점수 산출 → 4개 영역 가중 합산
        """
        hard_stop = self.ruleset.check_hard_stops(auction)
        if hard_stop.triggered:
            return RuleResult(status="REJECT", ...)
        
        warnings = self.ruleset.check_yellow_zones(auction)
        scores = self.ruleset.calculate_scores(auction)
        
        return RuleResult(
            status="REVIEW" if warnings else "PASS",
            warnings=warnings,
            scores=scores,
            total_score=scores.weighted_total(),
            ruleset_used=self.ruleset.name
        )
```

**Hard Stop 조건 (✅ 구현 완료 — `registry_rules.py` + `registry_analyzer.py`, 35개 테스트 검증):**

| 코드 | 조건 | 탐지 기준 |
|------|------|----------|
| HS001 | 예고등기 존재 | 갑구에 예고등기 이벤트 (말소되지 않은 것) |
| HS002 | 신탁등기 존재 | 갑구에 신탁 이벤트 (말소되지 않은 것) |
| HS003 | 가처분등기 존재 | 갑구에 가처분 이벤트 (말소되지 않은 것) |
| HS004 | 환매특약등기 존재 | 갑구에 환매특약 이벤트 (말소되지 않은 것) |
| HS005 | 법정지상권 성립 요건 | 토지/건물 소유자 상이 + 저당권 설정시 동일소유 |

**Hard Stop 확장 예정 (미구현):**

> 아래 조건은 초기 설계에 포함되었으나, 현재 데이터 소스로는 자동 판별이 어려워 향후 구현 예정.
> 매각물건명세서/현황조사서 파싱이 완료되면 추가한다.

| 코드 | 조건 | 필요 데이터 |
|------|------|-----------|
| HS-F01 | 유치권 신고/정황 | 매각물건명세서 + 현황조사서 파싱 |
| HS-F02 | 점유/임대차 정보 결손 + 분쟁 정황 | 현황조사서 + 임차인 데이터 |

**점수 체계:**
| 항목 | 가중치 | 점수 범위 |
|------|--------|----------|
| 법률 리스크 | 0.30 | 0~100 (높을수록 안전) |
| 명도 리스크 | 0.25 | 0~100 |
| 입지 점수 | 0.25 | 0~100 |
| 가격 매력도 | 0.20 | 0~100 |

**룰 변경 프로토콜:**
```
1. docs/rules/*.md 에 변경 사유 + 내용 기록
2. tests/backtest/ 에서 영향도 확인 (hard_stop_labels.json 기준)
3. 코드 반영
4. 테스트 통과 확인
5. README.md 업데이트
```

### 2. 검증 레이어 (`services/validator/`)

데이터 파이프라인의 모든 단계에 검증이 내장된다.

```python
# parse_validator.py — 수집 직후
class ParseValidator:
    def validate(self, parsed_data: dict) -> ValidationResult:
        """
        - 등기부 파싱 신뢰도 점수 산출
        - 권리 유형 자동 분류 확신도 측정
        - raw_text 필드로 원문 대조 가능 여부 확인
        - 확신도 < 0.8 이면 수동 확인 큐에 적재
        """

# rule_validator.py — 룰 적용 후
class RuleValidator:
    def validate(self, auction: Auction, rule_result: RuleResult) -> ValidationResult:
        """
        - 감정가 vs 최저가 괴리 이상치 탐지
        - 점수 역전 감지 (법률 위험한데 종합 안전 등)
        - 경계값 위반 시 플래그
        """

# cost_gate.py — ⭐ 유료 조회 트리거 (2단 파이프라인)
class CostGate:
    def should_proceed_to_paid(self, auction: Auction, preliminary_result: RuleResult) -> bool:
        """
        1단(무료) 필터 통과 후, 2단(유료) 조회 진행 여부 판단
        - REJECT → False (등기부 열람 불필요)
        - PASS/REVIEW + 감정가/최저가 비율이 목표 범위 → True
        - 비용 절감: 명백한 REJECT를 유료 조회 전에 제거
        """

# report_validator.py — 리포트 출력 전
class ReportValidator:
    def __init__(self):
        self.banned_phrases = self._load_banned_phrases()  # config/banned_phrases.json
    
    def validate(self, report: Report) -> Report:
        """
        - 데이터 기준일 자동 삽입
        - 면책 문구 자동 포함
        - ⭐ LLM 출력에 금지 표현 발견 시: 삭제가 아닌 '재작성(Rewrite)' 프롬프트 실행
          → 문맥을 유지하면서 안전한 표현으로 변환
        - 재작성 후에도 금지 표현 잔존 시 해당 문장 제거 + 로그
        """
    
    def _load_banned_phrases(self) -> list[str]:
        """config/banned_phrases.json에서 금지 표현 로드"""
```

**`config/banned_phrases.json` 구조:**
```json
{
  "exact_match": [
    "추천합니다", "투자하세요", "매수", "매도", "사세요", "파세요",
    "수익이 보장", "반드시", "확실히", "틀림없이"
  ],
  "pattern_match": [
    "안전합니다$", "위험하지 않습니다$",
    "좋은 물건", "나쁜 물건", "매수 적기"
  ],
  "public_banned": [
    "예측", "적정가", "입찰가", "추천", "비추천"
  ],
  "public_replacements": {
    "입찰가": "최저매각가격",
    "추천": "체크 결과"
  },
  "rewrite_prompt": "아래 문장에서 투자 추천/판단 표현을 제거하고, 객관적 사실 설명으로만 재작성해줘. 원래 문맥은 유지해. 문장: {sentence}"
}
```

### 3. 파서 & 등기 분석 (`services/parser/` + `services/registry/`)

```python
# registry_parser.py — 등기부 PDF/텍스트 → RegistryDocument (갑구/을구 이벤트 리스트)
class RegistryParser:
    """등기부등본 PDF/텍스트를 파싱하여 RegistryDocument로 변환
    - parse_pdf(): PyMuPDF로 텍스트 추출 후 파싱
    - parse_text(): 텍스트 직접 파싱
    - _split_sections(): 표제부/갑구/을구 분리
    - _classify_event_type(): 등기목적 → EventType(16종) 매핑
    """

# registry_analyzer.py — 말소기준권리 판별 + 인수/소멸 분류 + Hard Stop 탐지
class RegistryAnalyzer:
    """RegistryDocument → RegistryAnalysisResult 분석
    1. 말소기준권리(base right) 판별 (MORTGAGE > PROVISIONAL_SEIZURE > SEIZURE > AUCTION_START)
    2. 각 권리의 인수/소멸/불확실 분류
    3. Hard Stop 5종 탐지 (예고등기, 신탁, 가처분, 환매, 법정지상권)
    4. 신뢰도 산출 + 요약 생성
    ※ RuleEngine이 아니라 여기서 수행. RuleEngine은 파생 필드를 소비만 한다.
    """
```

**CODEF 등기부 연동 (`services/registry/`):**
```python
# provider.py — RegistryProvider ABC + RegistryTwoWayAuthRequired 예외
# codef_provider.py — CODEF API 호출 (주소검색 + 등기부열람 + RSA 암호화)
# codef_mapper.py — CODEF JSON 테이블 형식 → RegistryDocument 변환
# pipeline.py — 주소 → 등기부 조회 → 분석 자동화 파이프라인 (RegistryPipeline)
```

**데이터 흐름 (2경로):**
```
[경로A: CODEF API]                      [경로B: PDF 업로드]
CODEF 주소검색 → 고유번호                  등기부등본 PDF
     │                                       │
     ▼                                       ▼
CODEF 등기부열람 → JSON                 RegistryParser
     │                                       │
     ▼                                       │
CodefRegistryMapper                          │
     │                                       │
     └──────────┬────────────────────────────┘
                ▼
        RegistryDocument (갑구/을구 이벤트)
                │
                ▼
        RegistryAnalyzer
        ├─ 말소기준권리 판별
        ├─ 인수/소멸 분류
        ├─ Hard Stop 5종 탐지
        └─ 신뢰도 산출
                │
                ▼
        RegistryAnalysisResult
```

### 4. 크롤러 (`services/crawler/`)

```python
# ⭐ 1단+2단 통합 파이프라인 (3A 완료)
# 1단 (무료): court_auction + public_api + geo_client → enricher → filter_engine
# 2단 (유료): address_parser → matcher → CODEF 등기부 → registry pipeline → analyzer
# AuctionPipeline이 1단 필터 후 YELLOW/GREEN 건만 2단 자동 연결 (fail-open)

# court_auction.py — 대법원 경매정보 HTTP 클라이언트 (✅ E2E 검증 완료)
#   CourtAuctionClient + collect_full_case (목록→상세→기일→문서)
# court_auction_parser.py — 대법원 응답 JSON 파서
#   parse_list/detail/history/documents → Pydantic DTO 8개

# public_api.py — 공공 API 연동 (무료, 1단 수집, ✅ 실 API 검증 완료)
#   apis.data.go.kr: 실거래가 (영문 필드명), 건축물대장

# geo_client.py — 지리/주소 API 연동 (무료, 1단 수집, ✅ 검증 완료)
#   카카오 Geocode: 주소 → 좌표
#   Vworld: 용도지역/지구 조회, 지번 주소 검색

# codef_client.py — CODEF API 연동 (유료, 2단 수집, ✅ 실 응답 확보)
#   OAuth 2.0 Bearer Token (7일 유효, 메모리 캐싱)
#   URL-encoded 응답 자동 파싱 (text/plain → unquote_plus → json.loads)
#   등기부등본 조회는 services/registry/codef_provider.py에서 호출
```

### 5. LLM 연동 (`services/llm/`)

> **사용 모델: OpenAI API** (GPT-4o 계열). 환경변수 `OPENAI_API_KEY`로 관리.

```python
# explainer.py
class RiskExplainer:
    """
    LLM은 오직 '설명'만 한다. (OpenAI GPT-4o 사용)

    입력: 룰 엔진 결과 (RuleResult)
    출력: 자연어 설명 문자열

    ⭐ 금지 표현 처리:
    - config/banned_phrases.json 기준
    - 금지 표현 발견 시 '삭제'가 아닌 '재작성' 프롬프트 실행
    - 재작성 프롬프트: banned_phrases.json의 rewrite_prompt 사용
    - 재작성 후에도 잔존 시 해당 문장 제거 + 로그 기록
    - 금지 표현 테스트를 고정하여 회귀 방지 (test_report_validator.py)

    허용 표현:
    - "~리스크가 존재합니다"
    - "~에 해당하여 주의가 필요합니다"
    - "~를 확인할 필요가 있습니다"
    """
```

---

## 📋 작업 흐름 가이드

### 새 기능 개발 시

```
1. README.md 체크리스트에서 현재 할 일 확인
2. 관련 docs/ 문서가 있는지 확인, 없으면 먼저 작성
3. 테스트 먼저 작성 (TDD 권장)
4. 코드 구현
5. 테스트 통과 확인
6. README.md 체크리스트 업데이트
```

### 룰 엔진 수정 시

```
1. docs/rules/ 에 변경 내용 먼저 기록
2. tests/backtest/ 실행하여 영향도 확인
3. Hard Stop 미탐지율 0% 유지 확인
4. 코드 반영
5. 전체 테스트 통과 확인
6. README.md 룰 엔진 섹션 업데이트
```

### 버그 수정 시

```
1. 버그 재현 테스트 먼저 작성
2. 수정
3. 테스트 통과 확인
4. 검증 레이어에 해당 케이스 추가 검토
```

---

## 🧪 테스트 전략

### 필수 테스트

```
tests/
├── test_rules/
│   ├── test_hard_stop.py      # Hard Stop 조건별 단위 테스트
│   ├── test_yellow_zone.py    # Yellow Zone 조건별 단위 테스트
│   ├── test_scorer.py         # 점수 산출 로직 테스트
│   ├── test_engine.py         # 룰 엔진 통합 테스트
│   └── test_ruleset_building_small.py  # ⭐ 꼬마빌딩 룰셋 전용
├── test_parser/
│   ├── test_registry_parser.py # 등기부 파싱 정확도
│   ├── test_registry_analyzer.py # ⭐ 말소기준권리 판별 + 파생 필드 계산
│   └── test_normalizer.py      # 정규화 로직
├── test_validator/
│   ├── test_parse_validator.py  # 파싱 검증
│   ├── test_rule_validator.py   # 이상치 탐지
│   ├── test_report_validator.py # ⭐ 면책/금지어 재작성 검사 (회귀 방지)
│   └── test_cost_gate.py        # ⭐ 유료 조회 트리거 검증
└── backtest/
    ├── historical_cases.json    # 과거 낙찰 사례 데이터
    ├── hard_stop_labels.json    # ⭐ Hard Stop 정답 라벨 (측정 기준)
    └── test_backtest.py         # 백테스트 실행
```

### 테스트 기준

| 대상 | 기준 | 측정 방법 |
|------|------|----------|
| Hard Stop | 미탐지율 **0%** (위험 물건 통과 금지) | `hard_stop_labels.json` 라벨 항목 한정 |
| Yellow Zone | 오탐율 **20% 이내** (보수적 판단 허용) | 백테스트 결과 대비 |
| 전체 룰 엔진 | 수동 분석 대비 일치율 **90% 이상** | 과거 사례 대조 |
| 파싱 정확도 | 권리 유형 분류 정확도 **95% 이상** | raw_text 원문 대조 |
| 금지 표현 | 재작성 후 잔존율 **0%** | banned_phrases.json 기준 |

---

## 🗄️ DB 스키마 가이드

> 홈서버 확정: **PostgreSQL 16**. UUID, JSONB, TEXT[] 네이티브 지원.
> 현재는 인메모리 처리만 (DB 미연동). **5A단계에서 구현 예정.**

### 핵심 테이블

```sql
-- 경매 물건
auctions (
    id UUID PRIMARY KEY,
    case_number VARCHAR UNIQUE,      -- 사건번호 (2026타경XXXXX)
    court VARCHAR,                    -- 관할 법원
    address TEXT,                     -- 소재지
    property_type VARCHAR,            -- 물건 유형 (꼬마빌딩, 아파트, 빌라 등)
    appraised_value BIGINT,          -- 감정가
    minimum_bid BIGINT,              -- 최저입찰가
    auction_date DATE,               -- 입찰일
    auction_count INT DEFAULT 1,     -- 회차 (유찰 횟수 + 1)
    status VARCHAR,                  -- 상태 (예정/진행/낙찰/유찰)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- 등기부 권리 (⭐ ChatGPT 피드백 반영: 강화된 모델)
rights (
    id UUID PRIMARY KEY,
    auction_id UUID REFERENCES auctions,
    right_type VARCHAR,              -- 권리 유형 (근저당, 가압류, 전세권 등)
    holder VARCHAR,                  -- 권리자
    amount BIGINT,                   -- 채권액
    accepted_at DATE,                -- ⭐ 접수일 (등기 접수 시점)
    registered_at DATE,              -- 설정일
    registration_seq INT,            -- ⭐ 등기 순번 (접수번호 기준)
    registry_section VARCHAR,        -- ⭐ "갑구" | "을구"
    raw_text TEXT,                   -- ⭐ 원문 근거 (파싱 검증용)
    is_before_base BOOLEAN,          -- 말소기준권리 이전 여부 (⭐ RegistryAnalyzer가 계산)
    will_extinguish BOOLEAN,         -- 소멸 예정 여부 (⭐ RegistryAnalyzer가 계산)
    priority INT                     -- 순위
    -- ※ is_before_base, will_extinguish: RegistryAnalyzer가 산출하여 저장.
    --   RuleEngine은 이 컬럼을 읽기만 한다.
)

-- 분석 결과
analyses (
    id UUID PRIMARY KEY,
    auction_id UUID REFERENCES auctions,
    base_right_id UUID REFERENCES rights,  -- ⭐ 선정된 말소기준권리
    ruleset_used VARCHAR,            -- ⭐ 사용된 룰셋 (building_small 등)
    rule_status VARCHAR,             -- PASS / REVIEW / REJECT
    hard_stop_codes TEXT[],          -- ⭐ ["HS001", "HS003"]
    hard_stop_reasons JSONB,         -- Hard Stop 사유
    warnings JSONB,                  -- Yellow Zone 경고
    legal_score FLOAT,               -- 법률 리스크 점수 (0~100)
    eviction_score FLOAT,            -- 명도 리스크 점수
    location_score FLOAT,            -- 입지 점수
    price_score FLOAT,               -- 가격 매력도 점수
    total_score FLOAT,               -- 가중 합산 종합 점수
    parse_confidence FLOAT,          -- 파싱 신뢰도
    needs_manual_review BOOLEAN,     -- 수동 리뷰 필요 여부
    llm_explanation TEXT,            -- LLM 자연어 설명
    data_reference_date DATE,        -- 데이터 기준일
    analyzed_at TIMESTAMP
)

-- Private 전용 (절대 Public API에 노출 금지)
private_recommendations (
    id UUID PRIMARY KEY,
    auction_id UUID REFERENCES auctions,
    recommendation VARCHAR,          -- BUY / SKIP / WATCH
    suggested_bid BIGINT,            -- 적정 입찰가
    expected_return FLOAT,           -- 기대 수익률
    risk_premium FLOAT,              -- 리스크 프리미엄
    simulation JSONB,                -- 수익률 시뮬레이션 데이터
    created_at TIMESTAMP
)
```

---

## ⚠️ 금기 사항

### 절대 하지 말 것
1. **LLM에게 투자 판단을 시키지 말 것** — 점수, 추천, 가격은 반드시 수식/룰
2. **검증 없이 데이터를 신뢰하지 말 것** — 파싱 결과는 반드시 검증 통과 후 사용
3. **Private 로직을 Public 코드에 넣지 말 것** — 분리 유지
4. **룰 엔진 수정 시 백테스트 생략하지 말 것**
5. **API 키, 비밀번호를 코드에 하드코딩하지 말 것**
6. **README.md 업데이트를 미루지 말 것** — 변경 즉시 반영
7. **⭐ RuleEngine에서 `is_before_base`, `will_extinguish`를 계산하지 말 것** — RegistryAnalyzer의 책임
8. **⭐ 애매한 조건을 Hard Stop에 넣지 말 것** — 교차검증 충돌 시 Yellow Zone으로 강등
9. **⭐ Public API/문서/리포트에 '예측', '적정가', '입찰가'를 사용하지 말 것** — Private 전용 용어

### LLM 출력 금지 표현
> `config/banned_phrases.json`에서 관리. 코드에 하드코딩하지 말 것.
> 금지 표현 발견 시: 삭제가 아닌 **재작성(Rewrite) → 재검증 → 잔존 시 제거** 순서.
> `test_report_validator.py`에 금지어 테스트를 고정하여 회귀 방지.

### ⭐ Public 금지 용어 (Private 전용)
> Public API 응답, 리포트, 문서, UI 어디에서든 아래 표현은 절대 노출 금지.
> 해당 개념은 `private_recommendations` 테이블과 Private 대시보드에서만 사용.

| 금지 용어 | Public 대체 표현 | Private 허용 |
|----------|-----------------|-------------|
| 예측 | "유사 사례 참고 데이터" 또는 표현 자체 제거 | ✅ 낙찰가 예측 |
| 적정가 | 사용 금지 | ✅ 적정 입찰가 |
| 입찰가 | "최저매각가격" (법원 공식 용어) | ✅ 입찰 제안가 |
| 추천 | "체크 결과" 또는 "필터링 결과" | ✅ 추천/비추천 |

---

## 📝 커밋 컨벤션

```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정 (README, CLAUDE.md, docs/)
rule: 룰 엔진 변경 (반드시 백테스트 동반)
test: 테스트 추가/수정
refactor: 리팩토링
chore: 빌드, 설정 변경
```

예시:
```
feat: 대법원 크롤러 기본 구조 구현
rule: Hard Stop에 법정지상권 조건 추가 (백테스트 통과)
docs: 말소기준권리 도메인 문서 작성
fix: 등기부 파싱 시 날짜 형식 오류 수정
```

---

## 📊 데이터 파이프라인 의사결정 (확정)

### 2단 파이프라인 구조

```
[1단: 무료 필터링]                    [2단: CODEF 등기부 분석]
대법원 경매정보 크롤링                 CODEF 주소검색 → 고유번호
건축물대장 API (data.go.kr)     →    CODEF 등기부열람 → JSON
Vworld (용도지역/주소)                CodefMapper → RegistryDocument
실거래가 API (data.go.kr)             RegistryAnalyzer → 리스크 분석
카카오 Geocode (좌표)                      │
     │                                   ▼
     ▼                            RegistryAnalysisResult
enricher → filter_engine           (말소기준, 인수/소멸, Hard Stop)
  RED → 제외                             │
  YELLOW/GREEN → 2단 진행 →──────────────┘
```

### 등기부등본 조회 방식
- **메인: CODEF API 자동 조회** (주소검색 + 등기부열람, 실 응답 확보 완료)
- **백업: 수동 PDF 업로드 → RegistryParser 파싱**
- CODEF 등기부 파이프라인: `RegistryPipeline` (주소 → 고유번호 → 등기부 → 분석 일괄 실행)
- 등기정보광장 Open API: **미사용** (지역 통계만 제공, 개별 물건 조회 불가)

### 1단 무료 필터링 데이터 소스 (확정, 5개)

| # | 데이터 | 출처 | 필터링 용도 |
|---|--------|------|-------------|
| 1 | 경매 사건 정보 | 대법원 경매정보 크롤링 | 감정가, 최저가, 유찰횟수, 물건종류, 사건번호 |
| 2 | 건축물대장 | data.go.kr API | 건물 용도·구조·면적, 위반건축물 여부 |
| 3 | 토지이용계획 | Vworld API | 용도지역·지구, 개발행위제한 |
| 4 | 실거래가 | data.go.kr API | 시세 대비 감정가 괴리율 |
| 5 | 주소/좌표 | 카카오 + Vworld | 위치 기반 조회 연결고리 |

### 1단 필터링 룰 (구현 완료)

| 구분 | 코드 | 조건 |
|------|------|------|
| RED (즉시 제외) | R001 | 그린벨트 (개발제한구역) |
| RED | R002 | 위반건축물 표시 |
| RED | R003 | 토지단독 (법정지상권 위험) |
| YELLOW (주의) | Y001 | 유찰 3회 이상 |
| YELLOW | Y002 | 시세 괴리 30% 이상 |
| YELLOW | Y003 | 건축물대장 미확인 |
| GREEN | — | 위 조건 미해당 → 2단 진행 |

CostGate: RED → passed=False (2단 진입 차단), YELLOW/GREEN → passed=True

---

## 🧪 현재 테스트 현황

- **총 391개 mock 테스트 전체 통과** (`cd backend && python -m pytest tests/ -v`)
  - 크롤러: 61개 (기타 19 + 대법원 40 + URL-decode 2)
  - Enricher: 22개
  - FilterEngine: 27개 (RED 11 + YELLOW 12 + FilterEngine 6 + CostGate 3)
  - Pipeline: 18개 (1단 8 + 2단 통합 10)
  - AddressParser: 29개 (도로명 6 + 지번 6 + 정규화 6 + 엣지 6 + 보충 5)
  - RegistryMatcher: 13개 (지번일치 3 + 건물명 2 + 부분 1 + 동 1 + 실패 2 + 선택 2 + 결과 2)
  - RegistryParser: 40개
  - RegistryAnalyzer: 35개
  - CODEF Registry: 62개 (mapper 40 + provider fetch 13 + search 6 + RSA 3 + Validation 9 = 71 → 실제 62)
  - RegistryPipeline(2단): 27개
  - API 스키마: 16개 (summary 5 + detail 7 + registry 2 + request 2)
  - API 엔드포인트: 17개 (health 1 + list 5 + detail 4 + analyze 3 + registry 4)
  - 기타: 23개
- **E2E 실전 검증 (4E, 2026-02-14):** address 100%, geocode 60%, land_use 100%, building 100%, market 100%, codef_search 70%, registry_full 86% (6/7)

---

## 🔄 현재 진행 상황

> 이 섹션은 매 작업 세션 시작/종료 시 업데이트한다.

**현재 단계:** 4단계 완료 → 5단계 진입 (로드맵 v2.2 확정)
**완료된 것:**
- 0단계: API 검증 및 데이터소스 확정
- 1단 필터링: crawler → enricher → filter_engine (RED/YELLOW/GREEN + CostGate)
- 등기부 파서/분석기: RegistryParser + RegistryAnalyzer (PDF/텍스트 경로)
- CODEF 등기부 연동: CodefRegistryProvider + CodefMapper + RegistryPipeline (API 경로)
- 3A 통합: 주소파싱(address_parser) + 매칭(matcher) + AuctionPipeline 1단+2단 연결
- 3B API: FastAPI 엔드포인트 4개 + 스키마 + 테스트 33개
- 4A 문서정리: 불일치 7건 해소, 홈서버 로드맵 재구성
- 4B 실전검증: E2E 10건 실행, BUG 7건 발견
- 4C 버그수정: Vworld 데이터셋(LT_C_UQ111), CF-13007 재시도, 지번 fallback
- 4E CODEF 전면 교정: inquiryType=0, password/ePrepayPass 분리, CF-12826/12411/13328 해소
- 전체 391개 테스트 통과, E2E registry_full 86% (6/7)

**다음 할 일:** 5-0 홈서버 세팅 (Ubuntu + PostgreSQL) → 5A DB 스키마 + ORM
**블로커:** 홈서버 세팅 (Ubuntu 설치 + PostgreSQL 16)
**최근 변경:** 2026-02-14 — 로드맵 v2.2 확정 (PostgreSQL, 5단계 재구성)

---

*이 파일은 프로젝트와 함께 계속 업데이트됩니다. 구조가 변경되면 즉시 반영하세요.*
