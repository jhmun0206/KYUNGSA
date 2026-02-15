# E2E 검증 보고서 — 2026-02-13

## 요약

| 항목 | 값 |
|------|-----|
| 검증 대상 | 10건 |
| ALL_PASS | 0건 |
| PARTIAL | 10건 |
| ALL_FAIL | 0건 |
| 발견된 버그 | 14건 |
| 시작 | 2026-02-13T20:49:15.548438 |
| 종료 | 2026-02-13T20:50:22.394238 |

## API 접근 상태

| 서비스 | 상태 |
|--------|------|
| 카카오_Geocode | ✅ SET |
| Vworld | ✅ SET |
| 공공데이터 | ✅ SET |
| CODEF | ✅ SET |
| CODEF_SERVICE_TYPE | ❌ demo |

## 물건별 결과

### 물건 1: 서울특별시 강남구 테헤란로 152
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=강남구, road=테헤란로, bldg_no=152 | 0ms |
| 1_geocode | ✅ PASS | x=127.036508620542, y=37.5000242405515 | 115ms |
| 1_land_use | ✅ PASS | 2건: 일반상업지역, 미분류 | 100ms |
| 1_building | ✅ PASS | 0건 | 310ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 124ms |
| 2_codef_search | ❌ FAIL | 검색 결과 0건 | 1102ms |
| 2_registry_full | ⏭️ SKIP | 고유번호 없음 | 0ms |

### 물건 2: 서울특별시 서초구 서초대로 398
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=서초구, road=서초대로, bldg_no=398 | 0ms |
| 1_geocode | ✅ PASS | x=127.025104317477, y=37.4966368177214 | 91ms |
| 1_land_use | ✅ PASS | 2건: 일반상업지역, 미분류 | 109ms |
| 1_building | ✅ PASS | 0건 | 89ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 837ms |
| 2_codef_search | ✅ PASS | 24건, unique_no=11021996104790, addr=서울특별시 서초구 서초대로 398 그레이츠 강남 제1층 제101호 [서초 | 1889ms |
| 2_registry_full | ❌ FAIL | [CF-12826] 비밀번호 자릿수 오류입니다. 확인 후 거래하시기 바랍니다. | 996ms |

### 물건 3: 서울특별시 종로구 새문안로5가길 28 지1층비109호 (적선동,광화문플래티넘)
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=종로구, dong=적선동, road=새문안로5가길, bldg_no=28, bldg=광화문플래티넘 | 0ms |
| 1_geocode | ✅ PASS | x=126.973597076089, y=37.574460196686 | 88ms |
| 1_land_use | ✅ PASS | 2건: 일반상업지역, 미분류 | 178ms |
| 1_building | ✅ PASS | 0건 | 98ms |
| 1_market_price | ✅ PASS | 40건 (202601) | 90ms |
| 2_codef_search | ❌ FAIL | [CF-13006] 검색결과가 없습니다. 검색어에 잘못된 철자가 없는지, 정확한 주소인지 다시 한번 확인해 주세요. | 4554ms |
| 2_registry_full | ⏭️ SKIP | 고유번호 없음 | 0ms |

### 물건 4: 서울 강남구 역삼동 123-4
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=강남구, dong=역삼동, lot=123-4 | 0ms |
| 1_geocode | ❌ FAIL | 결과 없음 | 99ms |
| 1_land_use | ⏭️ SKIP | 좌표 없음 (Geocode 실패) | 0ms |
| 1_building | ✅ PASS | 0건 | 103ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 283ms |
| 2_codef_search | ✅ PASS | 5건, unique_no=11012024002057, addr=서울특별시 강남구 언주로 563 원에디션강남 401동 근린생활시설 제40 | 1412ms |
| 2_registry_full | ❌ FAIL | [CF-12411] 필수 파라미터가 누락되었습니다. | 1010ms |

### 물건 5: 서울특별시 관악구 남현6길 13 지1층비101호 (남현동,한샘빌라)
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=관악구, dong=남현동, road=남현6길, bldg_no=13, bldg=한샘빌라 | 0ms |
| 1_geocode | ✅ PASS | x=126.975473185994, y=37.4742146258685 | 93ms |
| 1_land_use | ✅ PASS | 2건: 미분류, 제2종일반주거지역 | 160ms |
| 1_building | ✅ PASS | 0건 | 270ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 151ms |
| 2_codef_search | ✅ PASS | 29건, unique_no=11012016002600, addr=서울특별시 관악구 남현8길 7 한샘빌라 제2층 제201호 [남현동 107 | 2029ms |
| 2_registry_full | ❌ FAIL | [CF-12826] 비밀번호 자릿수 오류입니다. 확인 후 거래하시기 바랍니다. | 1008ms |

### 물건 6: 경기 수원시 영통구 매탄동 123
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=경기도, sigungu=수원시, dong=매탄동, lot=123 | 0ms |
| 1_geocode | ❌ FAIL | 결과 없음 | 93ms |
| 1_land_use | ⏭️ SKIP | 좌표 없음 (Geocode 실패) | 0ms |
| 1_building | ✅ PASS | 0건 | 100ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 171ms |
| 2_codef_search | ✅ PASS | 2건, unique_no=13011996328085, addr=경기도 수원시 영통구 매봉로27번길 42 [매탄동 111-123] | 2289ms |
| 2_registry_full | ❌ FAIL | [CF-12411] 필수 파라미터가 누락되었습니다. | 970ms |

### 물건 7: 부산 해운대구 우동 123
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=부산광역시, sigungu=해운대구, dong=우동, lot=123 | 0ms |
| 1_geocode | ❌ FAIL | 결과 없음 | 100ms |
| 1_land_use | ⏭️ SKIP | 좌표 없음 (Geocode 실패) | 0ms |
| 1_building | ✅ PASS | 0건 | 109ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 136ms |
| 2_codef_search | ✅ PASS | 14건, unique_no=18112015009872, addr=부산광역시 해운대구 해운대로 620 해운대라뮤에뜨 제1층 제상점-123호 | 1588ms |
| 2_registry_full | ❌ FAIL | [CF-12411] 필수 파라미터가 누락되었습니다. | 893ms |

### 물건 8: 세종특별자치시 한솔동 123
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=세종특별자치시, dong=한솔동, lot=123 | 0ms |
| 1_geocode | ❌ FAIL | 결과 없음 | 91ms |
| 1_land_use | ⏭️ SKIP | 좌표 없음 (Geocode 실패) | 0ms |
| 1_building | ✅ PASS | 0건 | 369ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 158ms |
| 2_codef_search | ✅ PASS | 3건, unique_no=16472011003944, addr=세종특별자치시 노을3로 14 첫마을아파트 제103동 제1층 제123호 [ | 1623ms |
| 2_registry_full | ❌ FAIL | [CF-12411] 필수 파라미터가 누락되었습니다. | 1727ms |

### 물건 9: 서울특별시 마포구 월드컵북로 396 (상암동,누리꿈스퀘어)
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=마포구, dong=상암동, road=월드컵북로, bldg_no=396, bldg=누리꿈스퀘어 | 0ms |
| 1_geocode | ✅ PASS | x=126.889782954548, y=37.5794283422818 | 99ms |
| 1_land_use | ✅ PASS | 1건: 일반상업지역 | 110ms |
| 1_building | ✅ PASS | 0건 | 99ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 143ms |
| 2_codef_search | ❌ FAIL | [CF-13006] 검색결과가 없습니다. 검색어에 잘못된 철자가 없는지, 정확한 주소인지 다시 한번 확인해 주세요. | 4437ms |
| 2_registry_full | ⏭️ SKIP | 고유번호 없음 | 0ms |

### 물건 10: 서울특별시 송파구 올림픽로 300 (신천동,롯데월드타워)
**결과: ⚠️ PARTIAL**

| 단계 | 상태 | 상세 | 소요 |
|------|------|------|------|
| 1_address_parse | ✅ PASS | sido=서울특별시, sigungu=송파구, dong=신천동, road=올림픽로, bldg_no=300, bldg=롯데월드타워 | 0ms |
| 1_geocode | ✅ PASS | x=127.104301829165, y=37.5137129859207 | 100ms |
| 1_land_use | ✅ PASS | 2건: 일반상업지역, 미분류 | 140ms |
| 1_building | ✅ PASS | 1건 | 108ms |
| 1_market_price | ✅ PASS | 100건 (202601) | 166ms |
| 2_codef_search | ❌ FAIL | [CF-13006] 검색결과가 없습니다. 검색어에 잘못된 철자가 없는지, 정확한 주소인지 다시 한번 확인해 주세요. | 5342ms |
| 2_registry_full | ⏭️ SKIP | 고유번호 없음 | 0ms |

## 발견된 버그

| # | 설명 |
|---|------|
| 1 | [물건1] 2_codef_search: 검색 결과 0건 |
| 2 | [물건2] 2_registry_full: [CF-12826] 비밀번호 자릿수 오류입니다. 확인 후 거래하시기 바랍니다. |
| 3 | [물건3] 2_codef_search: [CF-13006] 검색결과가 없습니다. 검색어에 잘못된 철자가 없는지, 정확한 주소인지 다시 한번 확인해 주세요. |
| 4 | [물건4] 1_geocode: 결과 없음 |
| 5 | [물건4] 2_registry_full: [CF-12411] 필수 파라미터가 누락되었습니다. |
| 6 | [물건5] 2_registry_full: [CF-12826] 비밀번호 자릿수 오류입니다. 확인 후 거래하시기 바랍니다. |
| 7 | [물건6] 1_geocode: 결과 없음 |
| 8 | [물건6] 2_registry_full: [CF-12411] 필수 파라미터가 누락되었습니다. |
| 9 | [물건7] 1_geocode: 결과 없음 |
| 10 | [물건7] 2_registry_full: [CF-12411] 필수 파라미터가 누락되었습니다. |
| 11 | [물건8] 1_geocode: 결과 없음 |
| 12 | [물건8] 2_registry_full: [CF-12411] 필수 파라미터가 누락되었습니다. |
| 13 | [물건9] 2_codef_search: [CF-13006] 검색결과가 없습니다. 검색어에 잘못된 철자가 없는지, 정확한 주소인지 다시 한번 확인해 주세요. |
| 14 | [물건10] 2_codef_search: [CF-13006] 검색결과가 없습니다. 검색어에 잘못된 철자가 없는지, 정확한 주소인지 다시 한번 확인해 주세요. |

## 결론

- 전체 파이프라인 동작 여부: ⚠️ 부분 통과 (0/10)
