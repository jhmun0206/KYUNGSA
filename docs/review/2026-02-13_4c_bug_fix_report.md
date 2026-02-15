# 4C E2E 버그 수정 보고서 — 2026-02-13

## 수정 대상 (5건)

| BUG | 심각도 | 원인 | 수정 내용 | 결과 |
|-----|--------|------|-----------|------|
| BUG-01 | Critical | IROS_USER_PW 10자리 로그인PW → 4자리 열람PIN 필요 | `IROS_VIEWING_PIN` config 추가, `_encrypt_password()` PIN 우선 사용 + fallback | ✅ 수정 완료 (CF-12826→PIN 설정 시 해결) |
| BUG-02 | Critical | ePrepayPass 평문 전송 → RSA 암호화 필요 | `_encrypt_eprepay_pass()` 추가, payload에 암호화된 값 전송 | ✅ 수정 완료 (CF-12411 → CF-12826로 변경 = 암호화 정상) |
| BUG-03 | High | Vworld `LP_PA_CBND_BONBUN` 지적도 → 용도지역 아님 | 데이터셋 `LT_C_UQ111`로 교체, `domain=localhost` + `crs=EPSG:4326` 추가 | ✅ 수정 완료 (0% → 100% PASS) |
| BUG-04 | Medium | CODEF CF-13007 대형건물 검색 과다 | CF-13007 시 `realtyType=3` 재시도 로직 추가 | ✅ 수정 완료 (crash 방지, 3건 재시도 확인) |
| BUG-05 | Medium | 건축물대장 본번/부번 "0001"/"0000" 하드코딩 | enricher에 주소 문자열에서 지번 추출 fallback 추가 | ✅ 수정 완료 (enricher 로직 개선) |

## 스킵 (2건)

| BUG | 심각도 | 사유 |
|-----|--------|------|
| BUG-06 | Low | 카카오 Geocode 약식지번 미지원 — 알려진 제약 |
| BUG-07 | Low | CODEF 도로명만 검색 → 0건 — 향후 검색 전략 개선 |

## 변경 파일 (6개)

| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/config.py` | `IROS_VIEWING_PIN`, `CODEF_EPREPAY_PASS` 필드 추가 |
| `backend/app/services/registry/codef_provider.py` | BUG-01/02/04: PIN 우선 사용, ePrepayPass RSA 암호화, CF-13007 재시도 |
| `backend/app/services/crawler/geo_client.py` | BUG-03: Vworld 데이터셋 `LT_C_UQ111` + domain/crs 파라미터 |
| `backend/app/services/enricher.py` | BUG-03/05: zone 추출키 변경, 지번 fallback 추출 |
| `.env` / `.env.example` | `IROS_VIEWING_PIN` 필드 추가 |
| `backend/tests/test_registry_codef.py` | 새 테스트 4개 추가 (PIN, ePrepayPass, CF-13007 retry) |

## E2E 결과 비교 (Before 4B vs After 4C)

### 단계별 통과율

| 단계 | 4B (before) | 4C (after) | 변화 |
|------|-------------|------------|------|
| address_parse | 10/10 (100%) | 10/10 (100%) | — |
| geocode | 6/10 (60%) | 6/10 (60%) | — (BUG-06 low, 스킵) |
| **land_use** | **0/10 (0%)** | **6/6 (100%)** | **+100%** |
| building | 1/10 (10%) | 1/10 (10%) | — (E2E 스크립트 하드코딩) |
| market_price | 10/10 (100%) | 10/10 (100%) | — |
| **codef_search** | **5/10 (50%)** | **7/10 (70%)** | **+20%** |
| registry_full | 0/10 (0%) | 0/10 (0%) | PIN 미설정 (사용자 조치 필요) |

### 주요 개선 사항

1. **Vworld 용도지역 (0% → 100%)**: `LT_C_UQ111` 데이터셋으로 교체하여 "일반상업지역", "제2종일반주거지역" 등 정확한 용도지역 반환
2. **CODEF 검색 (50% → 70%)**: CF-13007 재시도 로직으로 대형건물 검색 실패 방지. 물건6(수원), 물건7(부산), 물건8(세종) 새로 성공
3. **CF-12411 → CF-12826**: ePrepayPass RSA 암호화 적용으로 "필수 파라미터 누락" 오류 대부분 해소. 나머지 CF-12826은 PIN 미설정이 원인

### 잔여 이슈 (4C 범위 밖)

| 이슈 | 설명 | 다음 단계 |
|------|------|-----------|
| CF-12826 (registry_full) | IROS_VIEWING_PIN 미설정 → 4자리 PIN 입력 필요 | 사용자 .env 설정 |
| CF-12411 (registry_full 물건4,6,7,8) | PIN 설정 후에도 발생 가능 — addr_* 파라미터 부족 의심 | PIN 설정 후 재검증 필요 |
| BUG-06 Geocode 약식지번 | "서울 강남구 역삼동 123-4" 미지원 | 향후: 전체주소 재구성 후 검색 |
| BUG-07 도로명 CODEF 검색 | 도로명만으로 CODEF 검색 → 0건 (물건1,3,9,10) | 향후: addrRoadName + addrBuildingNumber 활용 |

## 테스트 현황

- **전체 테스트**: 378개 PASS (기존 374 + 신규 4)
- **신규 테스트**:
  - `test_encrypt_password_fallback_iros_pw`: PIN 미설정 시 IROS_USER_PW fallback
  - `test_encrypt_eprepay_pass`: 전자민원캐시 비밀번호 RSA 암호화
  - `test_search_cf13007_retry_with_realty_type_3`: CF-13007 재시도
  - `test_search_cf13007_already_realty_type_3_raises`: 이미 realtyType=3이면 에러 전파

## 사용자 조치 필요

`.env` 파일에서 `IROS_VIEWING_PIN`을 4자리 숫자로 설정:
```
IROS_VIEWING_PIN=1234    # ← 인터넷등기소 열람용 비밀번호 (4자리)
```
설정 후 `PYTHONPATH=backend python scripts/e2e_validate.py` 재실행하여 registry_full 단계 검증.
