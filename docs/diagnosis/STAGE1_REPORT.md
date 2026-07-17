# KYUNGSA 자기진단 — Stage 1 표면 진단 리포트

**진단일:** 2026-05-16
**진단 범위:** 8축 표면 점검 (코드 깊이 진입 금지)
**진단자:** Claude Code 자동 진단

---

## A. 8축 점수표

| 축 | 점수 | 한 줄 평가 | 핵심 결함 |
|----|------|-----------|----------|
| 1. 인증/세션 | 3/5 | NextAuth+JWT 동작, middleware 부재 | 라우트 단위 보호 게이트 없음 — 페이지 보호는 클라이언트 의존 |
| 2. 데이터 정합성 | 2/5 | 22,523건 수집됐으나 보강율 50% 미만 | `legal_score` 18,134건 전부 NULL, `building_info` NULL 51%, `location_data` NULL 50% |
| 3. E2E 플로우 | 확인 필요 | 페이지/컴포넌트 구조는 갖춰짐 | 브라우저 실측 미수행 — 사용자 시연 필요 |
| 4. 룰/ML 신뢰도 | 2/5 | ML/rule 절반씩 분포, 점수 변별력 부족 | 점수 30~50 구간 66% 편중, 등급 D 42%, `legal_scorer.py` 존재하나 저장 안됨 |
| 5. UI/UX | 확인 필요 | 6개 페이지, 9개 상세 컴포넌트 | 사용자 입장 평가 필요 (브라우저 사용기 미수행) |
| 6. 성능/안정성 | 3/5 | 서버 에러 0건, 배치 1건 stuck | **B000240(인천) 배치 3일 연속 RUNNING stuck** |
| 7. 코드 부채 | 4/5 | TODO 1개, 763 테스트 | 692/763 pass (test_db, test_enricher 사전 실패) |
| 8. 운영 가능성 | 확인 필요 | 실 사용자 1명, 즐겨찾기 0건 | 본인 시나리오 실측 필요 |

**총점: 14/40 (확인 완료된 6개 축 기준)** — 확인 필요 항목 3개(3·5·8)는 사용자 응답 후 보정

---

## B. 이슈 리스트

### 🔴 Critical (서비스 동작 자체에 지장)

- [ ] **[축2] `legal_score` 전건 NULL** — `scores` 테이블 18,134건 중 `legal_score IS NOT NULL` 0건. `backend/app/services/rules/legal_scorer.py`(495줄)는 구현돼 있으나 `total_scorer.py`/`engine.py`가 결과를 `scores.legal_score` 컬럼에 저장하지 않거나 호출 자체가 누락. **CLAUDE.md 최우선 원칙 "법률 리스크 가중치 0.30"이 사실상 작동 안 함.**

- [ ] **[축2] `registry_analyses` 테이블 0건** — 등기부 분석 결과 DB 저장 0건. 틸코블렛 연동 완료됐지만 실제 호출/저장 흐름 단절. `RegistryAnalysisORM` 모델 존재하나 데이터 없음.

- [ ] **[축6] B000240(인천) 배치 stuck** — 3일 연속(2026-05-13/14/15) `pipeline_runs.status='RUNNING'`, `finished_at IS NULL`. 인천 법원 수집이 매일 멈춤. 다른 법원(서울 6개 + 경기 8개)은 정상.

- [ ] **[축2] `building_info` NULL 51%** — 22,523건 중 11,483건 보강 실패. 면적/용도/건축연도 등 점수 산출 핵심 데이터 절반 누락.

### 🟡 Major (사용성·신뢰도 저하)

- [ ] **[축2] `location_data` NULL 50%** — 입지 점수(`location_score`, 가중치 0.25) 산출 기반 부재. 22,523건 중 11,332건 누락. 진행 중 4,173건 중 카테고리 미설정 398건 (10%).

- [ ] **[축2] `exclusive_area_m2_real` NULL 69%** — 정규화 컬럼 채워진 건 7,042/22,523. 가격/수익률 시뮬레이터 정확도 영향.

- [ ] **[축4] 점수 변별력 부족** — `total_score` 30~50 구간 66% (11,932/18,134), A등급 0.4% (68건). 양극단이 너무 좁고 중앙 편중. 사용자 입장에선 "다 비슷한 점수" 인식 우려.

- [ ] **[축4] 등급 D 비율 42%** — D 7,604 / C 5,900 / B 4,562 / A 68. D 등급이 가장 많아 비관적 분포. CLAUDE.md "70% 필터링" 목표와 부합하지만 사용자 만족도는 낮을 수 있음.

- [ ] **[축6] systemd 배치 에러 컬럼 일관성 결여** — 모든 `pipeline_runs.errors`가 'null' 문자열로 채워짐. JSONB NULL이 아닌 `'null'`이라 모니터링 쿼리 혼동 가능.

- [ ] **[축1] frontend `middleware.ts` 부재** — Next.js 미들웨어 없음. 페이지 보호는 클라이언트 컴포넌트의 `useSession()` 분기에 의존. 직접 URL 진입 시 깜빡임 + 비보호 데이터 유출 가능성.

### 🟢 Minor (정리 필요하지만 시급하지 않음)

- [ ] **[축7] test_db, test_enricher 사전 실패 3건** — `RegistryAnalysisCRUD::test_unique_auction_id`, `TestBuildingRegister::test_building_no_sigungu_match`, `TestMarketPrice::test_market_price_no_lawd_cd`. 이번 세션과 무관한 pre-existing 실패.

- [ ] **[축2] 진행 중 물건 좌표 누락 457건** — 4,173건 중 10%. 지도 페이지에서 누락 표시.

- [ ] **[축7] `.env.example`에 `JWT_SECRET` 누락** — 서버 `.env`엔 설정돼 있으나 예시 파일에 항목 없음.

- [ ] **[축8] 실사용자 1명, 즐겨찾기 0건** — `users` 1 / `user_favorites` 0 / `user_saved_searches` 1. 운영 적용 사실상 없음 (개인 도구 단계).

---

## C. Stage 2 정밀 진단 후보 (2점 이하 영역)

### 1. **데이터 정합성 (2/5)** — 최우선 정밀 진단 대상
- `legal_score` NULL 원인 추적:
  - `RuleEngineV2.evaluate()` 흐름에서 `legal_scorer.score()` 호출 여부
  - `_save_score()` 함수에서 `legal_score` 필드 매핑 누락 여부
  - `LegalScoreResult.score` → `scores.legal_score` 변환 경로
- 등기부 분석 DB 저장 흐름:
  - `RegistryAnalysisORM` INSERT가 일어나는 코드 경로 (있긴 한가?)
  - 틸코 fetch_by_address 후 분석 결과를 저장하는 함수
- building_info / location_data 보강 실패 원인:
  - `_extract_building_params()` 실패율
  - 카카오/Vworld API 응답 누락률

### 2. **룰/ML 신뢰도 (2/5)**
- 점수 변별력: 30~50 구간 편중 원인
  - 가중치 합산식 검토 (`total_scorer.py` 가중치 0.30/0.25/0.25/0.20)
  - `legal_score`가 항상 NULL이면 어떻게 처리되는지 (디폴트값? 평균치?)
- ML vs 룰 갈래(`prediction_method`) — 어떤 조건에서 ml_v1 / rule_v1 갈리는지

### 3. **운영 가능성 (확인 필요 → 추정 2/5)**
- 본인 입찰 시나리오 시연 필요
- 외부 도구 의존 지점 파악

---

## D. 확인 필요 항목 (사용자 응답 필요)

1. **축 3 (E2E 플로우):** kyungsa.com 접속해서 다음 단계 직접 클릭 후 알려주세요.
   - 메인 → 검색 → 상세 진입 시 깨지는 화면 있나요?
   - ML 예측 / 현금흐름 시뮬레이터 / 명도 정보가 상세 페이지에서 표시되나요?

2. **축 5 (UI/UX):** 
   - 모바일에서 깨지는 부분 있나요?
   - 첫 진입 시 "이게 뭐 하는 서비스인지" 5초 내에 보이나요?

3. **축 8 (운영 가능성):**
   - 다음 주 본인 입찰 시나리오 1개를 KYUNGSA만으로 끝까지 돌려본 적 있나요?
   - 막힌 지점이 있다면 외부 도구(엑셀/탱크옥션/등기열람)를 어디서 썼나요?

---

## 진단 후 보고 (요청 형식)

### 1. 총점과 가장 약한 축 3개
- **총점: 14/40** (확인 완료 6축 기준)
- **가장 약한 축:**
  1. **데이터 정합성 (2/5)** — legal_score 전건 NULL, registry_analyses 0건, 보강율 50%
  2. **룰/ML 신뢰도 (2/5)** — 점수 분포 편중, legal 축 사실상 비활성
  3. **운영 가능성 (확인 필요, 추정 2/5)** — 실사용자 1명, 즐겨찾기 0건

### 2. Critical 이슈 개수
- **4건**: legal_score NULL, registry_analyses 0건, B000240 stuck, building_info NULL 51%

### 3. A 피봇(본인 입찰 도구화) 관점 가장 큰 장애물
**`legal_score`가 전건 NULL이라 룰 엔진의 핵심 축(법률 리스크 가중치 0.30)이 실질적으로 비활성 상태.**
입찰 도구로서 "이 물건 법적으로 안전한가?"라는 가장 중요한 질문에 답을 못 주는 상태. `legal_scorer.py`는 495줄로 구현돼 있으므로 **호출/저장 경로 단절**일 가능성이 높음 → Stage 2에서 1순위로 추적해야 함.

### 4. Stage 2에서 깊게 볼 영역 추천
- **1순위:** `RuleEngineV2` → `TotalScorer` → `_save_score()` 흐름에서 `legal_score` 누락 지점 추적
- **2순위:** `registry_analyses` 테이블 INSERT 경로 (어디서도 호출 안 됨일 가능성)
- **3순위:** B000240(인천) 배치 stuck 원인 — `court_office_code` 매핑 오류 또는 대법원 API 응답 형식 차이
- **4순위:** 점수 분포 편중 — 가중치 식 점검 + `legal_score` 누락 시 fallback 로직
