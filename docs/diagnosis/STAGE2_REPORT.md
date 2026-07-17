# KYUNGSA 자기진단 — Stage 2 정밀 진단 리포트

**진단일:** 2026-05-16
**진단 범위:** Stage 1에서 도출된 Critical 4건 코드 레벨 추적
**진단 원칙:** 코드 수정 금지 / 추측 금지 / 5종 세트(원인·증거·인과·계획·공수) 정리

---

## 진단 1: `legal_score` 전건 NULL

### 근본 원인
**`batch_collector`가 `RuleEngineV2.evaluate()` 호출 시 `registry_analysis=None`을 전달하므로, 등기부 분석이 있어도 없어도 무관하게 `legal_scorer.score()`가 영구히 호출되지 않는다.**

### 증거

`backend/app/services/rules/engine.py:101-110`:
```python
# 3. 법률 점수 (등기부 있을 때만)
legal_result: LegalScoreResult | None = None
needs_expert = False
if registry_analysis is not None:  # ← 이 조건이 False
    legal_result = self._legal_scorer.score(
        case=case,
        registry_analysis=registry_analysis,
    )
    needs_expert = legal_result.needs_expert_review
```

`backend/app/services/batch_collector.py:427`:
```python
eval_result = self._rule_engine.evaluate(enriched, tenants=tenants)
# ↑ registry_analysis 인자 누락 — 항상 None
```

`backend/app/services/batch_collector.py:832` (rescore 경로):
```python
eval_result = self._rule_engine.evaluate(enriched, tenants=tenants)
# ↑ 동일 — registry_analysis 미전달
```

`batch_collector.py` 전체에 `registry|Registry|RegistryAnalyzer|fetch_by_address` 키워드 **0건** — 배치 흐름에서 등기 분석 호출 자체가 없음.

DB 증거:
```
scores 18,134건 중 legal_score IS NOT NULL = 0건
avg(total_score) = 46.6 (전건이 legal pillar 빠진 상태로 산출됨)
```

### 인과관계
**진단 1 ← 진단 2 (직접 인과).**
batch가 등기 분석을 호출하지 않음 → registry_analyses 0건 → legal_scorer 호출 0회 → legal_score 영구 NULL.

추가 영향: `total_scorer.py:142-153`이 누락 pillar를 가중치 재정규화로 처리하므로 total_score는 NULL이 아니지만 **legal축(가중치 0.30) 정보 완전 손실**. 결과적으로 모든 물건이 "legal 정보 없는 상태"로 동일 처리 → 변별력 저하(진단 4 연결).

### 수리 계획
**전략 A — 배치 흐름에 자동 등기 분석 통합 (비용 대규모):**
- `batch_collector._process_single_item()` 내에서 `RegistryPipeline.analyze_by_address()` 호출 추가
- 매 물건당 틸코 120pt × 진행 4,173건 = **약 50만 포인트/회 (1회 풀배치)**
- 비현실적. 비용 폭증.

**전략 B — 캐시된 registry_analyses만 활용 (권장):**
```python
# batch_collector.py:427 (그리고 832)
# 변경 전
eval_result = self._rule_engine.evaluate(enriched, tenants=tenants)

# 변경 후
from app.models.db.converters import registry_orm_to_dto  # 이미 존재 (L265~)
existing_ra = None
if existing := self._db.query(RegistryAnalysisORM).filter(
    RegistryAnalysisORM.case_number == enriched.case.case_number,
    RegistryAnalysisORM.property_sequence == int(enriched.case.property_sequence or 1),
).first():
    existing_ra = registry_orm_to_dto(existing, events=existing.auction.registry_events)
eval_result = self._rule_engine.evaluate(enriched, registry_analysis=existing_ra, tenants=tenants)
```

**전략 C — 유료 분석 사용자 호출 시 즉시 재채점 트리거 (필수 보완):**
- 사용자가 등기부 분석 버튼 누르면 `auctions.py:fetch_registry_analysis` 엔드포인트가 호출됨
- 이 함수 끝에서 `rule_engine.evaluate(..., registry_analysis=analysis)` 재실행 → scores UPDATE
- 사용자 1명만 100건 분석해도 100건의 legal_score 회복

### 공수 / 리스크
- 전략 B + C 조합: **2~3시간** (코드 변경 50줄 내외)
- 리스크: 기존 `_save_score()` 로직과의 중복 commit 처리, score 캐시 만료 정책 결정 필요

---

## 진단 2: `registry_analyses` 테이블 0건

### 근본 원인
**등기부 분석 자동 실행 경로가 코드상 존재하지 않음.** 모든 `RegistryAnalysisORM` INSERT는 `auctions.py:fetch_registry_analysis` API 엔드포인트(사용자 on-demand) 한 곳에서만 발생.

### 증거

`RegistryAnalysisORM` INSERT 호출처 grep:
```
backend/app/api/v1/auctions.py:839  orm = RegistryAnalysisORM(...)  ← 단 1곳
```

`backend/app/models/db/converters.py:165` — `registry_analysis_dto_to_orm()` 헬퍼 존재하나 호출자는 위 엔드포인트뿐.

`pipeline.py`에 `RegistryPipeline` 사용처 있으나 (L24, 39, 44, 115, 157, 198, 218) — **`pipeline.py` 자체가 `batch_collector`에 의해 호출되지 않음**. 즉 데드 코드에 가까움.

### 인과관계
**진단 1의 직접 원인.** + 사용자 1명 + 즐겨찾기 0건이라 on-demand 호출도 사실상 0회.

### 수리 계획
배치 자동화는 비용 폭증 우려 → **on-demand 강화** 방향 권장.

1. **사용자 등기부 분석 시 자동 재채점:** (진단 1 전략 C와 동일)
   - `auctions.py:fetch_registry_analysis` 함수 끝에 추가:
     ```python
     # 분석 저장 후 즉시 재채점 트리거
     from app.services.rules.engine import RuleEngineV2
     from app.models.db.converters import auction_orm_to_enriched  # 또는 유사 헬퍼
     analysis_dto = registry_orm_to_dto(orm, events=auction.registry_events)
     # ... eval_result = rule_engine.evaluate(enriched, registry_analysis=analysis_dto)
     # ... scores 테이블 UPDATE
     ```

2. **대량 분석 도구 (운영자 전용):**
   - `scripts/bulk_registry_analysis.py` 신규 스크립트
   - 대상: 진행 중 + grade A/B 후보만 (예: 4,562건 중 정밀 분석 대상 약 200건)
   - 비용: 200 × 120pt = 24,000pt (현실적 수준)
   - 본인 입찰 후보 좁힌 후 일괄 처리

### 공수 / 리스크
- **1번:** 1~2시간 (auctions.py 엔드포인트에 30줄 추가)
- **2번:** 2시간 (스크립트 신규 작성)
- 리스크: 틸코 비용 통제 — 대량 분석 스크립트에 `--max` 한도 + dry-run 필수

---

## 진단 3: B000240(인천) 배치 stuck

### 근본 원인
**systemd `TimeoutStartSec=7200`(2시간) 한도 내에서 15개 법원 순차 처리가 끝나지 않아, 마지막 차례에 도달하기 전에 SIGTERM으로 강제 종료된다.** B000240(인천)이 처리 도중에 죽으므로 `pipeline_runs.finished_at`이 NULL로 남는다.

### 증거

서버 로그 (`journalctl -u kyungsa-batch --since '24 hours ago'`):
```
May 16 05:03:41 [INFO] 오피스텔 전월세 조회: 28237 / 202602
May 16 05:03:41 systemd[1]: kyungsa-batch.service: start operation timed out. Terminating.
May 16 05:03:42 systemd[1]: kyungsa-batch.service: Main process exited, code=killed, status=15/TERM
May 16 05:03:42 systemd[1]: kyungsa-batch.service: Failed with result 'timeout'.
May 16 05:03:42 systemd[1]: kyungsa-batch.service: Consumed 15min 48.852s CPU time.
```

DB 증거 (`pipeline_runs WHERE court_code='B000240' ORDER BY started_at DESC LIMIT 10`):
- 2026-04-29부터 매일 RUNNING, finished_at 전부 NULL
- total_searched=0 (PipelineRun 시작 직후 시그널 받음)
- **17일 연속 동일 패턴**

처리 순서 분석:
- 같은 날 다른 법원은 모두 COMPLETED + 정상 total_searched
- B000240은 SEOUL(6) + GYEONGGI 앞쪽(B000250 수원 1100건, B000251 성남 등) 처리 후 차례
- 수원(B000250)이 1100~1200건 처리하느라 시간 잡아먹음

`deploy/kyungsa-batch.service`:
```
TimeoutStartSec=7200  # 2시간 — 부족함
ExecStart=run_batch.py --all-courts (15개)
ExecStart=fix_past_due.py
ExecStart=send_alerts.py
```

### 인과관계
독립 이슈. 다른 진단과 직접 연관 없음. 단, 인천 진행 중 물건이 누적 누락되면 → location_data NULL 비율에 기여 가능.

### 수리 계획
**옵션 A — 타임아웃 확장:**
```ini
# deploy/kyungsa-batch.service
TimeoutStartSec=14400  # 4시간으로 확대
```
- 가장 단순. 그러나 매물 증가 시 다시 부족해질 수 있음.

**옵션 B — 법원별 독립 서비스 분할 (권장):**
```
kyungsa-batch-seoul.service  (B000210~B000215, B000214)
kyungsa-batch-gyeonggi.service (B000250~)
```
- 각각 다른 시각에 타이머 시작 → 병렬/직렬 무관 독립
- 한 법원 실패가 다른 법원에 영향 없음

**옵션 C — 처리 순서 변경 (즉시 적용 가능):**
`scripts/run_batch.py:60`:
```python
# 변경 전
ALL_COURTS = {**SEOUL_COURTS, **GYEONGGI_COURTS}

# 변경 후 — 큰 법원 먼저, 작은 법원 나중
# B000240 인천을 앞으로 옮기거나, B000250 수원(가장 큰 1100건)을 맨 뒤로
```
- 인천 차례를 일찍 앞당기면 SIGTERM 받기 전에 완료 가능

**즉시 조치 (DB 정리):**
```sql
UPDATE pipeline_runs 
SET finished_at = NOW(), status = 'ERROR', errors = '[\"systemd timeout SIGTERM\"]'::jsonb
WHERE court_code = 'B000240' AND finished_at IS NULL;
```

### 공수 / 리스크
- 옵션 A: **5분** (.service 파일 한 줄)
- 옵션 B: **1시간** (서비스 분할 + 타이머 2개)
- 옵션 C: **2분** (dict 순서 변경)
- 리스크: 옵션 A로 늘려도 매물 계속 증가 시 다시 부족 → 옵션 B가 본질적 해결

---

## 진단 4: building_info / location_data NULL 50% + 점수 변별력 부족

### 근본 원인
두 개의 별개 원인이 겹쳐 있음:

**원인 4-1: NULL 50%는 통계적 착시.**
sale_result_collector가 매각 완료 물건을 INSERT 시 enrichment 단계를 거치지 않음. 매각 15,191건 + 진행 4,173건 중 매각 INSERT 분이 통계 왜곡.

**원인 4-2: 점수 30~50 편중 66%의 진짜 원인은 legal_score NULL.**
`total_scorer.py:142-153`이 누락 pillar를 가중치 재정규화로 처리. legal(0.30)이 빠진 상태로 모든 18,134건이 동일 처리 → 분산 축소.

### 증거

`property_type` 별 진행 중 보강율:
```
다세대        869건 → has_bld 833 (96%), has_loc 839 (97%)
빌라          572건 → has_bld 547 (96%)
아파트        433건 → has_bld 362 (84%)
토지(전답)    100건 → has_bld 60 (60%)  # 토지는 건축물대장 없는 게 정상
자동차         78건 → has_bld 55 (71%)  # 동산은 건축물대장 무관
```
→ **건물형 진행 중 물건은 보강율 90% 이상**. NULL 50%는 매각/동산/토지 합산 착시.

`total_scorer.py:147`:
```python
if not pillar_scores:
    total_score = 0.0
```
→ 모든 pillar NULL이어야만 0점. legal만 NULL이면 다른 3개로 정상화하므로 NULL 자체는 발생 안 함.

```sql
scores WHERE legal_score IS NULL → 18,134건 (전건)
avg(total_score) = 46.6, min=0.0, max=92.4
```
→ 변별력은 있으나 중앙에 편중.

### 인과관계
- **4-1**은 디자인 의도(sale_result_collector는 enrichment 안 함) — 버그 아님. 통계 해석 주의.
- **4-2**는 진단 1·2의 결과 — legal_score 회복되면 자연 해소될 가능성 높음.

### 수리 계획
**4-1: 없음** (디자인 의도. 매각 완료 물건은 어차피 점수 의미 없음).

**4-2: 진단 1·2 수리 후 재채점 → 분포 변화 모니터링.**
가설 검증 쿼리:
```sql
-- legal_score 회복 후 비교용 베이스라인 확보
SELECT 
  COUNT(*) FILTER (WHERE total_score < 30) low,
  COUNT(*) FILTER (WHERE total_score BETWEEN 30 AND 50) mid_low,
  COUNT(*) FILTER (WHERE total_score BETWEEN 50 AND 70) mid_high,
  COUNT(*) FILTER (WHERE total_score >= 70) high
FROM scores;
```
→ 재채점 후 동일 쿼리 비교.

만약 legal_score 회복 후에도 편중 지속되면 **가중치 식 자체 재검토** 필요 (예: legal 가중치 0.30 → 0.40 상향, 또는 점수 분포 자체가 0~100 풀스케일로 안 나오는 정규화 이슈).

### 공수 / 리스크
- 진단 1·2 수리에 포함됨. 추가 공수 없음.
- 검증 공수: 30분 (재채점 후 분포 비교)

---

## 수리 우선순위 (의존관계 반영)

### 1순위: **진단 3 (B000240 stuck)** — 즉시 조치 5분
- 이유: 다른 작업에 영향 없는 독립 이슈. 가장 빠르게 해결되며 운영 안정성 즉시 회복.
- 조치: `TimeoutStartSec=14400` + `ALL_COURTS` dict 순서에서 인천 앞당기기 + 기존 stuck 레코드 DB 수정.

### 2순위: **진단 2-1 (등기부 사용자 분석 후 자동 재채점)** — 1~2시간
- 이유: 진단 1의 출구. 사용자가 등기부 분석 누르면 → registry_analyses 채워짐 → legal_score 회복 → total_score 갱신. 비용 폭증 없이 점진적 데이터 채움.
- 조치: `auctions.py:fetch_registry_analysis` 끝에 재채점 로직 추가.

### 3순위: **진단 1 (legal_score 회복)** — 2~3시간
- 이유: 2순위와 함께 작업하면 통합 가능. batch 흐름과 rescore 흐름 모두에서 캐시된 registry_analyses 활용.
- 조치: `batch_collector.py:427, 832` 양 경로에 `registry_analysis=existing_ra` 전달.

### 4순위: **bulk_registry_analysis.py 스크립트** — 2시간
- 이유: 진행 중 grade A/B 후보 ~200건에 대해 일괄 분석 (24,000pt 비용). 운영자 본인 입찰 시나리오에 직접 활용.
- 조치: 신규 스크립트.

### 5순위: **재채점 → 분포 검증** — 30분
- 이유: 진단 4-2 가설 확인. 분포 여전히 편중되면 가중치 재검토.

**합계 예상 공수: 6~8시간** (1일치 작업).

---

## 재채점 필요 여부

**필요. 진단 1·2 수리 후 진행 중 4,173건 중 등기 분석 보유분에 대해 재채점.**
- 부분 재채점: `RegistryAnalysisORM` 보유 건만 (현재 0건 → bulk_registry 실행 후 200건 + 사용자 분석 누적분)
- 예상 시간: 진행 중 200건 기준 약 5~10분 (보강 캐시 활용)
- 전체 재채점 불필요 — legal_score 없는 18,134건은 어차피 정보 없는 상태로 동일 처리됨

---

## "배선 문제 / 신규 개발" 구분

### 배선만 연결하면 되는 것 (총 4~5시간)
- ✅ **진단 1 코어**: `engine.evaluate()` 호출 시 `registry_analysis` 인자 추가 (2줄)
- ✅ **진단 2 자동 재채점**: API 엔드포인트에 평가 로직 호출 추가 (30줄)
- ✅ **진단 3 타임아웃**: .service 파일 1줄 + dict 순서 변경
- ✅ **registry_orm_to_dto 변환**: 이미 `converters.py:265`에 존재. 그대로 사용.

### 새로 만들어야 하는 것 (총 2시간)
- 🆕 **bulk_registry_analysis.py 스크립트**: 신규 (그러나 기존 `RegistryPipeline` 재사용)
- 🆕 **kyungsa-batch 서비스 분할** (옵션): 옵션 B 선택 시 systemd 단위 2개 신규

**비율: 배선 70% / 신규 30%.** 코드 자산은 이미 충분하고, 연결만 빠져 있음.

---

## 종합 평가: 본인 입찰 도구로서의 사용성

### 솔직한 평가
**Critical 4건 모두 수리 후 KYUNGSA는 본인 입찰 도구로 "충분히" 쓸 만해진다.** 단, 한 가지 조건이 붙음:

> **본인이 입찰 후보를 200건 미만으로 좁힌 후 `bulk_registry_analysis.py`를 돌리는 워크플로우**.

이유:
1. 1순위(타임아웃)+ 3순위(legal 배선) 후 → 진행 중 4,173건 중 등기 분석 보유분에 한해 점수 신뢰도 회복
2. 4순위(bulk script) 후 → 본인이 골라낸 후보군에 대해 법률 위험도까지 산출됨
3. 등기부까지 본 후의 점수는 4축 풀스케일 → 변별력 회복 기대

**여전히 한계로 남는 것:**
- ML 예측은 학습 데이터 부족(legal_score 0건 학습 제외) → ML 정확도 개선은 별도 과제
- 점수 분포 편중이 가중치 식 자체 문제일 가능성 → 재채점 후 재검토 필요
- B000240 인천 매물 17일치 누적 누락 → 보강 재실행 필요

**핵심 메시지:**
> "코드는 거의 완성돼 있는데 마지막 결선 5cm가 안 이어진 상태." 이번 4건 수리(1일치) 이후 본인 입찰에 실전 투입 가능.
