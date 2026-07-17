# Stage 3 수리 로그

**작업일:** 2026-05-17
**작업 범위:** Stage 2 Critical 4건 + 분포 검증 1건 (총 5건)
**절대 원칙 준수:** 명시 외 작업 금지 / ML 재학습 금지 / 가중치 식 변경 금지 / 틸코 실호출 금지

---

## Fix별 결과

| Fix | 상태 | 변경 파일 | 검증 결과 | commit |
|-----|------|----------|----------|--------|
| 1. 인천 stuck 해소 | ✅ | `scripts/run_batch.py`, `deploy/kyungsa-batch.service` | DB stuck 36건 → 0건, 처리순서 인천 first/수원 last, TimeoutStartSec 14400. 다음 배치 검증은 자동 실행 후 별도 확인 | `56f9204` |
| 2. legal 배선 복구 | ✅ | `backend/app/services/batch_collector.py` | `_load_cached_registry_analysis` 헬퍼 추가, 양 경로(L427, L832)에 `registry_analysis=existing_ra` 전달. pytest 692/692 통과. registry_analyses=0이라 회귀 없음 확인 | `88912fc` |
| 3. 등기 분석 후 자동 재채점 | ✅ | `backend/app/api/v1/auctions.py` | 엔드포인트 끝에 `BatchCollector._rescore_single_from_db` 호출 추가, try/except로 격리 (분석 보존). pytest 692 통과. 실제 흐름 검증은 사용자 등기 분석 실행 후 가능 | `3a7d6de` |
| 4. bulk 스크립트 (dry-run) | ✅ dry-run only | `scripts/bulk_registry_analysis.py` (신규) | 서버 dry-run 정상 출력 — `--max 50` 대상 50건 / 6000pt, `--max 9999` **전체 진행중 grade A/B = 2,029건 / 243,480pt** | `2df07e2` |
| 5. 분포 검증 (베이스라인만) | ⚠️ 검증 불가 | (코드 변경 없음) | registry_analyses=0건 → has_legal=0 → 분포 변화 없음. **bulk 실호출 후 재측정 필요** | — |

---

## Fix 1 상세 — stuck 36건 정리 내역

실행 전 SELECT 목록 (court_code별 집계):

| court_code | count | oldest | newest |
|---|---|---|---|
| B000251 (성남) | 18 | 2026-04-02 | 2026-05-12 |
| B000250 (수원) | 10 | 2026-03-27 | 2026-05-11 |
| B000210 (서울중앙) | 3 | 2026-02-16 | 2026-02-26 |
| RESCORE_ALL | 2 | 2026-02-28 | 2026-03-07 |
| B000213 (서울북부) | 1 | 2026-02-17 | 2026-02-17 |
| B000212 (서울남부) | 1 | 2026-02-25 | 2026-02-25 |
| B000214 (의정부) | 1 | 2026-02-24 | 2026-02-24 |
| **B000240 (인천)** | (이미 19건 1차 정리) | — | — |

**전체 36건 패턴 공통점:** `total_searched=0` AND `total_enriched=0` — PipelineRun INSERT 직후 시그널/타임아웃으로 죽음. systemd timeout SIGTERM으로 확정 처리.

**RESCORE_ALL 2건 별도 조사 결과:**
```sql
SELECT run_id, scored_in_run FROM pipeline_runs WHERE court_code='RESCORE_ALL' ...
20260228_082127_RESCORE_ALL_cc72ef6e → scored_in_run = 0
20260307_153421_RESCORE_ALL_7b7cc1de → scored_in_run = 0
```
→ **두 run 모두 scores 테이블에 어떤 레코드도 저장하지 못함 (첫 commit 전에 죽음).** DB 오염 없음. Fix 5 재채점에 영향 없음.

UPDATE 실행 결과:
```
UPDATE 36
SELECT COUNT(*) WHERE finished_at IS NULL → 0
```

다음 배치(05-17 04:00 KST 예정)에서 확인 사항:
- B000240 인천 첫 차례 정상 완료 여부
- B000250 수원 마지막 차례에 14400초 한도 내 완료 여부

---

## Fix 4 dry-run 출력

서버 실행 결과 (2026-05-17 KST):

**1. `--max 50` (실호출 시 1차 배치 후보):**
```
=== bulk_registry_analysis ===
  등급         : ['A', 'B']
  status       : 진행
  max          : 50
  기존 분석    : 제외
  대상         : 50건
  예상 비용    : 50건 × 120pt = 6000pt

--- 대상 미리보기 (10건) ---
  [1] 2025타경51970 seq=1 status=진행 addr=서울특별시 서대문구 창천동 29-81 신촌르메이에르타운5 2층201호
  [2] 2025타경72085 seq=1 status=진행 addr=경기도 동두천시 보산동 429-115
  [3] 2025타경8830 seq=1 status=진행 addr=서울특별시 구로구 구로동 212-8 대륭포스트타워1 제4층 제403호
  [4] 2025타경52347 seq=1 status=진행 addr=경기도 하남시 망월동 1148 하남미사롯데캐슬헤븐시티2 1층123호
  [5] 2025타경11065 seq=1 status=진행 addr=서울특별시 강서구 마곡동 798-16 엠밸리더블유타워4 제2층 제209호
  [6] 2025타경52044 seq=1 status=진행 addr=경기도 성남시 분당구 야탑동 341 제3층 제225호
  [7] 2025타경12218 seq=1 status=진행 addr=서울특별시 강북구 우이동 47-19 성훈팰리스 101동 2층202호
  [8] 2025타경12278 seq=1 status=진행 addr=서울특별시 강서구 화곡동 918-1 아줄리움 제13층 제1303호
  [9] 2024타경98517 seq=1 status=진행 addr=경기도 수원시 영통구 대학로 60, 1층101호 (이의동,리치프라자3)
  [10] 2024타경119  seq=1 status=진행 addr=서울특별시 송파구 위례성대로2길 10 2층201호 (방이동,피스티오피스텔)
  ... 외 40건

*** DRY-RUN 모드: 실호출 없음. 종료. ***
```

**2. `--max 9999` (진행중 grade A/B 전체 규모):**
```
대상         : 2029건
예상 비용    : 2029건 × 120pt = 243,480pt
```

→ **전체 2,029건 일괄 분석 시 243,480pt 소비.** 본인 입찰 후보로 좁힌 50건 단위 부분 배치 권장.

---

## Fix 5 분포 검증 결과

### 베이스라인 (수리 전 = 현 시점)
```sql
SELECT
  COUNT(*) FILTER (WHERE total_score < 30) AS low,         -- 303
  COUNT(*) FILTER (WHERE total_score BETWEEN 30 AND 50) AS mid_low,   -- 11,936
  COUNT(*) FILTER (WHERE total_score BETWEEN 50 AND 70) AS mid_high,  -- 3,932
  COUNT(*) FILTER (WHERE total_score >= 70) AS high,       -- 1,992
  COUNT(*) FILTER (WHERE legal_score IS NOT NULL) AS has_legal,  -- 0
  COUNT(*) AS total                                         -- 18,134
FROM scores;
```

분포 비율:
- 0-30: 1.7%
- 30-50: 65.8% (← 편중)
- 50-70: 21.7%
- 70+: 11.0%

`registry_analyses` 테이블: **0건** (Fix 4 실호출 안 함 + 사용자 등기 분석 0회).

### 수리 후 측정 (불가)
- has_legal = 0 → legal_score 회복된 물건 없음
- 분포 동일 → 가설 검증 불가

### 판정
**검증 보류.** Fix 4 실호출 + 자동 재채점 후 동일 쿼리로 재측정해야 분포 변화 확인 가능.

가설:
- `total_scorer.py:142-153`의 가중치 재정규화 메커니즘이 작동하므로, legal_score 채워지면 **legal pillar(가중치 0.30, 꼬마빌딩 기준) 정보가 합산에 반영** → 점수 변별력 확장 예상.
- 만약 legal_score 회복 후에도 편중 지속 → 가중치 식 자체 재검토 (이번 범위 밖).

---

## 사용자 승인 대기 항목

- [ ] **bulk_registry 실호출 — 1차 배치 (50건, 6,000pt)** — 승인 시 다음 명령 실행:
  ```bash
  ssh homeserver "cd /home/eric/projects/KYUNGSA && PYTHONPATH=backend backend/.venv/bin/python scripts/bulk_registry_analysis.py --grade A,B --status 진행 --max 50"
  ```
- [ ] **bulk_registry 실호출 — 전체 (2,029건, 243,480pt)** — 본인 입찰 후보 좁히기 전까지 보류 권장
- [ ] **다음 배치(05-17 04:00 KST) 결과 확인** — B000240 인천 정상 완료, B000250 수원 14400s 내 완료 여부

---

## 미해결 / 이번 범위 밖으로 미룬 것

- **ML 모델 재학습** (legal_score 회복 후 학습 데이터로 활용 가능 — 별도 작업)
- **kyungsa-batch 서비스 분할 (진단 3 옵션 B)** — 14400s + 처리순서 변경으로 충분한지 다음 배치 결과 보고 판단
- **분포 편중 가설 검증** (bulk 실호출 후 재측정 후 가중치 식 재검토 필요 여부 판단)
- **점수 분포 편중 시 가중치 식 변경** — 명시적으로 금지됨 (사용자 결정 사항)

---

## 보고 요약

### 1. Fix 1~5 각각 ✅/⚠️/❌
- Fix 1: ✅ (stuck 36건 정리 + 순서 변경 + 타임아웃 확장)
- Fix 2: ✅ (legal 배선, pytest 통과, 회귀 없음)
- Fix 3: ✅ (자동 재채점 트리거, fail-open)
- Fix 4: ✅ dry-run only (실호출 사용자 승인 대기)
- Fix 5: ⚠️ 검증 불가 (실호출 없어 분포 변화 없음 → 베이스라인만 기록)

### 2. legal_score가 실제로 채워지는 게 확인됐는가?
**아직 미확인.** 배선(Fix 2)과 트리거(Fix 3)는 코드상 완성됐으나, 실제 채워지려면 `registry_analyses` 레코드가 존재해야 함. 현재 0건.
→ Fix 4 실호출 또는 사용자가 직접 등기 분석 버튼을 누른 후 검증 가능.

### 3. 분포 검증 결과 — 편중 해소 여부
**측정 불가** (legal_score 0건). 베이스라인만 기록:
- 0-30: 1.7% / 30-50: 65.8% / 50-70: 21.7% / 70+: 11.0%
- 30-50 구간 65.8% 편중 — Fix 4 실행 후 재측정 시 변화 확인.

### 4. bulk_registry 실호출 예상 비용 (사용자 승인용)
- **1차 배치 (50건):** 6,000pt
- **전체 (2,029건):** 243,480pt
- 권장: 본인 입찰 후보를 좁힌 후 부분 배치(50건 단위)로 진행.

### 5. 이번 수리로 못 푼 것
- legal_score 실제 회복 검증 (실호출 대기)
- 분포 편중 해소 여부 (실호출 후 재측정)
- ML 재학습 (legal 데이터 누적 후 별도 작업)
- 서비스 분할 (옵션 B) — 다음 배치 결과 보고 판단
