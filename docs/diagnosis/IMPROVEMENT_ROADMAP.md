# KYUNGSA 개선 로드맵 (실행 지시서)

> **작성일:** 2026-07-12
> **작성자:** 시니어 엔지니어링 파트장 리뷰 (Claude Fable 5)
> **근거 문서:** [SENIOR_REVIEW_2026-07-12.md](SENIOR_REVIEW_2026-07-12.md) (종합 진단), STAGE1~3 리포트
> **이 문서의 목적:** 하위 모델(또는 다음 세션)이 컨텍스트 없이도 항목 하나를 골라 바로 착수할 수 있도록, 작업 단위마다 배경·대상 파일·완료 기준·금지 사항을 명시한다.
>
> **작업 규칙 (모든 항목 공통):**
> 1. 착수 전 이 문서와 CLAUDE.md를 읽는다. 완료 시 이 문서의 체크박스와 "진행 로그"를 갱신한다.
> 2. 룰 엔진/점수 관련 변경은 반드시 `scripts/backtest_scores.py` 실행 결과를 첨부한다.
> 3. 유료 API(틸코 등기 열람, 건당 120pt) 실호출은 **사용자 승인 없이 절대 실행 금지.** dry-run까지만.
> 4. 서버 DB에 대한 UPDATE/DELETE는 실행 전 SELECT로 대상 확인 + 사용자 보고.
> 5. 커밋은 작업 단위별로 분리하고 컨벤션(feat/fix/docs/rule/test/refactor/chore)을 따른다.

---

## 우선순위 총괄표

| # | 작업 | 우선순위 | 예상 공수 | 유형 |
|---|------|---------|----------|------|
| W1 | legal_score 실데이터 회복 (bulk 등기 분석 소량 실행 → 검증) | 🔴 P0 | 사용자 승인 + 1h | 운영 |
| W2 | 배치 stuck 재발 (54건) 근본 해결 — 법원별 서비스 분할 | 🔴 P0 | 2~3h | 운영 |
| W3 | JWT_SECRET 기본값 제거 + webhook secret 강제 | 🔴 P0 | 30m | 보안 |
| W4 | 평가 지표 3중 체계(등급/신호등/ML) 단일화 | 🟠 P1 | 4~6h | UX |
| W5 | 상세 페이지 상시 ⚫ 표현 개선 ("데이터 없음" → "직접 확인 체크리스트") | 🟠 P1 | 2h | UX |
| W6 | 죽은 코드 일괄 제거 (프론트 ~1,000줄 + 백엔드 v0 API + frontend_backup/) | 🟠 P1 | 2~3h | 부채 |
| W7 | 문서-코드 불일치 해소 (CLAUDE.md/README: CODEF→틸코, 가중치, 검증레이어 상태) | 🟠 P1 | 1~2h | 문서 |
| W8 | 검증 레이어 원칙 재정의 — 구현하거나 원칙에서 내리거나 (모순 해소) | 🟡 P2 | 결정 후 2~4h | 설계 |
| W9 | ML 재학습 (낙찰 실측 21,394건 반영) | 🟡 P2 | 2h + 학습시간 | ML |
| W10 | 초보자 UX — 용어 툴팁 + 면책 배너 확대 + SEO 메타 | 🟡 P2 | 3~4h | UX |
| W11 | requirements.txt 버전 핀 + celery/selenium 등 미사용 의존성 제거 | 🟢 P3 | 1h | 부채 |
| W12 | scripts/ 정리 (운영/일회성/실험 분리) | 🟢 P3 | 1h | 부채 |

> **중단 권고 (공수 투입 금지):** 비교 페이지 고도화, InvestmentCalculator 추가 개편, 홈 화면 재개편, 개발예정지역 필터(Phase 8), 서울시 상권분석 연동. 이유는 진단 보고서 §4 "과투자 영역" 참조 — 사용자 1명 상태에서 핵심 가치(권리분석 데이터)가 비어 있는데 주변 기능만 계속 다듬어 왔다.

---

## W1. legal_score 실데이터 회복 🔴

**배경:** 서비스의 핵심 차별점인 "법률 리스크 자동 분석"이 출시 이래 단 1건도 작동한 적 없다. `scores` 24,427건 전건 `legal_score IS NULL`, `registry_analyses` 0건 (2026-07-12 서버 실측). 배선(Stage3 Fix2/3)과 스크립트(Fix4)는 2026-05-17에 완성됐으나 두 달째 실호출이 없다.

**작업:**
1. 사용자에게 1차 배치 실행 승인 요청: `scripts/bulk_registry_analysis.py --grade A,B --status 진행 --max 50` (비용 6,000pt). **승인 없이 실행 금지.**
2. 실행 후 검증 쿼리 (STAGE3_FIXLOG.md의 분포 쿼리 재사용):
   - `SELECT COUNT(*) FROM registry_analyses;` → 50 근처
   - `SELECT COUNT(*) FROM scores WHERE legal_score IS NOT NULL;` → 0보다 커야 함 (자동 재채점 배선 검증)
   - 재채점이 자동으로 안 붙으면 `run_batch.py --rescore-db` 대상 확인
3. 점수 분포 before/after 기록 → `docs/diagnosis/STAGE3_FIXLOG.md`의 "Fix 5 분포 검증" 섹션 갱신.
4. 성공 시 다음 단계 제안: 즐겨찾기/입찰 후보 물건 온디맨드 분석 UX(프론트 버튼) 활성화 확인.

**완료 기준:** `legal_score NOT NULL > 0` + 자동 재채점 동작 확인 + 분포 변화 기록.
**주의:** 틸코 호출 실패율/응답 포맷 오류 발생 시 즉시 중단하고 로그 첨부 보고. 2,029건 전체 배치(243,480pt)는 제안하지 말 것.

- [ ] 완료

## W2. 배치 stuck 근본 해결 🔴

**배경:** Stage3 Fix1(타임아웃 14400s + 순서 변경)로 해결됐다고 기록됐으나, 2026-07-12 실측 결과 stuck run 54건 재발 (부천 B000241 15건, 성남 B000251 13건, 고양 B214807 8건, 5/17~7/10 지속). 특정 법원 문제가 아니라 **15개 법원 순차 처리 구조 자체가 한계.** stuck된 날의 해당 법원 물건은 조용히 누락된다.

**작업:**
1. 서버 journalctl로 최근 stuck 발생일의 종료 원인 확인 (timeout SIGTERM인지, 크롤러 에러인지):
   `ssh homeserver "journalctl -u kyungsa-batch --since '3 days ago' | tail -50"`
2. Stage2 진단 3의 **옵션 B 구현**: `kyungsa-batch-seoul.service` / `kyungsa-batch-gyeonggi.service` 분할 (타이머 03:00 / 04:30 등 시차). `deploy/` 파일 작성 + `run_batch.py`에 `--courts seoul|gyeonggi` 그룹 인자 추가.
3. 법원 단위 실패 격리: `run_batch.py`의 법원 루프에서 한 법원 예외가 전체를 죽이지 않는지 확인, PipelineRun에 finally로 finished_at 기록 (SIGTERM 대비 signal handler 또는 systemd `TimeoutStopSec` + graceful shutdown).
4. 기존 stuck 54건 DB 정리 (Stage3와 동일 패턴 UPDATE — 실행 전 SELECT 보고).

**완료 기준:** 분할 배포 후 7일간 stuck 0건 (사용자가 서버에서 확인).
- [ ] 완료

## W3. 보안 기본값 제거 🔴

**배경:** `backend/app/config.py`의 `JWT_SECRET` 기본값이 `"change-me-in-production"`. `.env` 누락 시 토큰 위조 가능. 텔레그램 webhook은 secret 미설정 시 검증 생략 (`backend/app/api/v1/telegram.py`).

**작업:**
1. `JWT_SECRET` 기본값 제거 → 미설정 시 앱 기동 실패(fail-fast)로 변경. `.env.example`에 항목 추가.
2. webhook: `TELEGRAM_WEBHOOK_SECRET` 미설정 시 webhook 라우트 비활성(503) 또는 기동 경고 로그.
3. (선택) `/api/v1/auth/upsert`에 최소한의 rate limit (slowapi 도입 또는 Cloudflare 레벨 설정 문서화).
4. 서버 `.env`에 실제 JWT_SECRET 설정돼 있는지 확인 후 배포.

**완료 기준:** 기본값 시크릿으로 서명된 토큰이 검증 실패. 테스트 추가.
- [ ] 완료

## W4. 평가 지표 단일화 🟠

**배경:** 등급(A~D), 리스크 신호등(🟢🟡🔴⚫), ML 낙찰가율 3개 체계가 화면마다 다르게 노출된다. 검색 리스트=신호등만(`frontend/components/search/AuctionTable.tsx`), 홈=등급만(`AuctionListRow.tsx`), 비교 페이지=3개 동시. 관계 설명은 어디에도 없다. 초보자 페르소나(박초보)에게 치명적 혼란.

**결정 필요 (사용자에게 물어볼 것):** 대표 지표를 무엇으로 할지. **권고안: 신호등을 유일한 1차 지표로, 등급은 상세 페이지의 보조 지표로 강등, ML 수치는 상세+현금흐름에서만.**

**작업 (권고안 기준):**
1. 홈 `AuctionListRow`를 신호등 표시로 교체 (GradeBadge 제거 또는 보조 배치).
2. 비교 페이지에서 legal_score 원점수 노출 제거 (현재 전건 NULL이기도 함).
3. `GradeLegend`를 "신호등 ↔ 등급 관계" 설명 포함으로 확장, 상세 페이지에서 등급 옆에 링크.
4. `lib/risk-signals.ts`의 `calcListSignal`이 legal_score를 안 쓰는 현재 로직을 문서화 (W1 이후 legal 반영 여부 결정).

**완료 기준:** 모든 리스트 화면에서 1차 지표가 동일. `npm run build` 통과.
- [ ] 완료

## W5. 상시 ⚫ 표현 개선 🟠

**배경:** 상세 `RiskChecklist.tsx`에서 유치권/법정지상권·선순위권리 2개 항목이 데이터와 무관하게 **항상 하드코딩 ⚫**. 데이터 커버리지 낮은 물건은 화면이 검정 도배 → "분석 못 하는 서비스" 인상.

**작업:**
1. 항상-⚫ 항목을 별도 시각 언어로 분리: "자동 분석 대상 아님 — 입찰 전 직접 확인" 체크리스트 스타일 (아이콘 ⚫ → 체크박스/문서 아이콘).
2. 등기 분석 완료 물건(W1 이후 존재)은 선순위권리 항목이 실데이터 신호로 전환되는지 확인 — 안 되면 배선 추가.
3. score null로 인한 ⚫에는 "현황조사서 미공개" 등 **이유** 한 줄 표시 (`score_coverage` 활용).

**완료 기준:** 하드코딩 ⚫ 0개. 이유 없는 ⚫ 0개.
- [ ] 완료

## W6. 죽은 코드 일괄 제거 🟠

**대상 (역참조 검증 완료, 2026-07-12):**
- 프론트: `components/search/SearchFilters.tsx`(440줄), `ClientFilteredResults.tsx`, `SearchResultsList.tsx`, `SearchResultsGrid.tsx`, `components/landing/TopPicksGrid.tsx`, `components/domain/AuctionCard.tsx`, `CoveragePill.tsx`, `PredictionPill.tsx`(미사용), 중복 `FavoriteButton` 한 벌(`components/common/` vs `components/domain/` — import 확인 후 미사용 쪽), `app/fonts/` 미사용 Geist.
- 루트: `frontend_backup/`, `CLAUDE.md.bak`, `README.md.bak`, `PROJECT_STATUS_CHECKPOINT.md`(구버전), `docker-compose.yml`(37바이트 스텁).
- 백엔드: v0 API (`app/api/auctions.py` — main.py에서 마운트 해제 먼저, 프론트 참조 0 확인 후 삭제), `app/api/analysis.py`/`search.py` 빈 스텁, `scripts/seed_data.py`/`backtest.py` 빈 스텁. CODEF 경로(`services/registry/codef_*`, `crawler/codef_client.py`)는 **틸코 전환 후에도 백업 경로로 쓸지 사용자 확인 후** 제거.
- git: `backend/app/models/db/auction 2.py` 삭제 상태 커밋 반영.

**작업 순서:** 삭제 전 각 파일 역참조 grep 재확인 → 763개 테스트 + `npm run build` 통과 → 커밋 분리(프론트/백엔드/루트).
**완료 기준:** 테스트/빌드 통과, README 구조도 갱신.
- [ ] 완료

## W7. 문서-코드 불일치 해소 🟠

**확인된 불일치:**
1. CLAUDE.md/README 전체가 등기부 연동을 **CODEF 기준**으로 서술하나, 실제는 2026-03~04에 **틸코블렛(Tilko)으로 전면 교체** (`backend/app/services/registry/tilko_provider.py`, git: `3365b20`, `ee63d39`). 환경변수 표도 구식.
2. CLAUDE.md "법률 리스크 가중치 0.30" — 실제 `total_scorer.py`는 유형별 가중치 (아파트 0.20/꼬마빌딩 0.35/토지 0.25).
3. CLAUDE.md 절대원칙 #2 "검증 레이어 없이는 분석 출력 금지" — validator 전체가 스텁. W8 결정과 연동해 원칙 문구 수정.
4. README "763개 테스트 통과" — Stage1 실측 692/763. 실제 수치로 갱신.
5. CLAUDE.md "현재 진행 상황" 섹션이 2026-03-27에 멈춰 있음 — 틸코 전환, Stage1~3 진단/수리, 이 로드맵 존재를 반영.
6. `.env.example`에 JWT_SECRET, 틸코 관련 키 누락.

**완료 기준:** CLAUDE.md·README가 현재 코드와 일치, "다음 할 일"이 이 문서를 가리킴.
- [ ] 완료

## W8. 검증 레이어 모순 해소 (설계 결정) 🟡

**배경:** 절대원칙 #2와 달리 `services/validator/` 4개 파일 전부 docstring 스텁, `banned_phrases.json`은 로드하는 코드가 0곳. 단, 현재 LLM 리포트 기능 자체가 미구현이라 "금지어가 노출될 출력물"도 아직 없다 — 원칙 위반이 실해를 만들기 전 상태.

**결정 옵션 (사용자 선택):**
- A. LLM 설명 기능을 만들 때까지 validator를 백로그로 명시하고 원칙 문구를 "LLM 출력 도입 시 필수 게이트"로 수정 (권고 — 공수 0, 정직한 문서).
- B. 지금 ReportValidator + banned_phrases 로더 + 테스트를 선구현 (LLM 도입 대비, 2~4h).

**완료 기준:** 선택된 옵션 반영 + CLAUDE.md 문구 일치.
- [ ] 완료

## W9. ML 재학습 🟡

**배경:** 마지막 학습(2026-03-24)은 12,211건 기준. 현재 `winning_ratio` 실측 21,394건 (+75%). `retrain_model.py`가 "개선 시에만 교체" 로직 보유.

**작업:** 서버에서 `retrain_model.py` 실행 → CV MAE 비교 보고 → 개선 시 모델 교체 + 진행 물건 재채점(`--rescore-db`). legal_score가 W1으로 일부 채워졌다면 피처 반영 여부 확인.
**완료 기준:** 재학습 결과 수치 보고 + 교체 여부 기록.
- [ ] 완료

## W10. 초보자 UX 보강 🟡

1. 용어 툴팁: "유찰", "명도", "인수 권리", "말소기준권리", "대항력"에 `ui/tooltip` 연결. 용어 사전은 `frontend/lib/glossary.ts` 신설 (Public 금지어 규칙 준수 — "입찰가" 대신 "최저매각가격").
2. `DisclaimerBanner`를 검색/비교/현금흐름 페이지에도 노출.
3. SEO: 상세 페이지 `generateMetadata` (사건번호+주소+최저매각가격), sitemap, robots. Pretendard를 `next/font`로 전환.

**완료 기준:** 툴팁 5개 이상 동작, 빌드 통과, 상세 페이지 OG 태그 확인.
- [ ] 완료

## W11. 의존성 정리 🟢

`backend/requirements.txt`: 버전 핀 추가, 미사용 의존성(celery, selenium, beautifulsoup4, redis, pymongo — import 여부 grep 후) 제거. catboost/pandas/numpy/pycryptodome 등 **실사용 중인데 목록에 없는 패키지**를 서버 venv `pip freeze`와 대조해 추가.
- [ ] 완료

## W12. scripts/ 정리 🟢

`scripts/`를 `scripts/ops/`(운영: run_batch, send_alerts, collect_*, retrain, fix_past_due, bulk_registry_analysis), `scripts/oneoff/`(백필/마이그레이션 완료분), `scripts/dev/`(test_*, capture_*, eda)로 분리. systemd 서비스 파일의 경로 동시 수정 필수 (deploy/ 5개 파일 + 서버 재설치 명령 문서화).
- [ ] 완료

---

## 진행 로그

| 날짜 | 작업 | 결과 |
|------|------|------|
| 2026-07-12 | 로드맵 최초 작성 (종합 진단과 함께) | — |
