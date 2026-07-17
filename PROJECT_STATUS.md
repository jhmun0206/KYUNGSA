# KYUNGSA 프로젝트 현황 정리

> 작성일: 2026-03-22
> 목적: 새 채팅/새 세션에서 컨텍스트 없이도 즉시 파악할 수 있는 원스톱 레퍼런스

---

## 1. 백엔드 API 엔드포인트 목록

### v1 API (`/api/v1/` prefix, 현재 프론트에서 사용)

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| `GET` | `/api/v1/auctions` | 경매 목록 (필터/정렬/페이징) | ❌ |
| `GET` | `/api/v1/auctions/map` | 지도용 마커 목록 | ❌ |
| `GET` | `/api/v1/auctions/{case_number}` | 경매 상세 정보 | ❌ |
| `GET` | `/api/v1/auctions/{case_number}/rent-reference` | 인근 임대료 레퍼런스 | ❌ |
| `POST` | `/api/v1/auth/upsert` | Google OAuth → JWT 발급 (NextAuth 콜백) | ❌ |
| `GET` | `/api/v1/users/me` | 로그인 사용자 정보 | ✅ JWT |
| `GET` | `/api/v1/users/me/favorites` | 즐겨찾기 목록 | ✅ JWT |
| `PUT` | `/api/v1/users/me/favorites/{case_number}` | 즐겨찾기 추가 | ✅ JWT |
| `DELETE` | `/api/v1/users/me/favorites/{case_number}` | 즐겨찾기 삭제 | ✅ JWT |
| `POST` | `/api/v1/users/me/favorites/bulk` | 즐겨찾기 일괄 동기화 | ✅ JWT |
| `GET` | `/api/v1/users/me/saved-searches` | 저장 검색 목록 | ✅ JWT |
| `POST` | `/api/v1/users/me/saved-searches` | 저장 검색 등록 | ✅ JWT |
| `DELETE` | `/api/v1/users/me/saved-searches/{id}` | 저장 검색 삭제 | ✅ JWT |
| `POST` | `/api/v1/users/me/telegram/code` | 텔레그램 연동 코드 발급 | ✅ JWT |
| `GET` | `/api/v1/users/me/telegram` | 텔레그램 연동 상태 | ✅ JWT |
| `DELETE` | `/api/v1/users/me/telegram` | 텔레그램 연동 해제 | ✅ JWT |
| `POST` | `/api/v1/telegram/webhook` | 텔레그램 Bot Webhook 수신 (내부용, schema 미노출) | ❌ |

> 인증: JWT Bearer Token (`Authorization: Bearer <token>`), PyJWT HS256, 30일 만료

---

## 2. 외부 API 연동 현황

| 서비스 | 환경변수 | 용도 | 상태 |
|--------|----------|------|------|
| **공공데이터포털** (data.go.kr) | `PUBLIC_DATA_API_KEY` | 실거래가, 건축물대장, 건축물대장 | ✅ 검증 완료 |
| **CODEF API** — Sandbox | `CODEF_SANDBOX_CLIENT_ID/SECRET` | 등기부등본 조회 (개발용) | ✅ 응답 확보 |
| **CODEF API** — Demo | `CODEF_DEMO_CLIENT_ID/SECRET` | 등기부등본 조회 (테스트) | ✅ |
| **CODEF API** — Production | `CODEF_CLIENT_ID/SECRET` | 등기부등본 조회 (운영) | ✅ |
| **CODEF RSA 공개키** | `CODEF_PUBLIC_KEY` | 비밀번호 RSA 암호화 | ✅ |
| **Vworld** (국토정보플랫폼) | `VWORLD_API_KEY` | 용도지역, 지번 주소 검색 | ✅ 검증 완료 |
| **카카오 개발자** | `KAKAO_REST_API_KEY` | 주소 → 좌표 (Geocode) | ✅ 검증 완료 |
| **인터넷등기소** (CODEF용 비회원) | `IROS_PHONE_NO`, `IROS_PASSWORD` | CODEF 등기부 비회원 로그인 | ✅ |
| **전자민원캐시** | `IROS_EPREPAY_NO`, `IROS_EPREPAY_PASS` | 등기부 열람 수수료 결제 (700원/건) | ✅ |
| **OpenAI API** | `OPENAI_API_KEY` | LLM 자연어 설명 생성 | ✅ |
| **텔레그램 Bot** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 배치 결과 알림 + 개인 알림 | ✅ |
| **텔레그램 Webhook** | `TELEGRAM_WEBHOOK_SECRET` | Webhook 검증 | ✅ |
| **Google OAuth** | NextAuth.js 환경변수 | 소셜 로그인 | ✅ |

> CODEF 서비스 타입: `CODEF_SERVICE_TYPE` = "sandbox" | "demo" | "production" (기본값: sandbox)

---

## 3. DB 테이블 목록 (PostgreSQL 16)

> DB: `kyungsa_db`, User: `kyungsa`, Host: `localhost:5432`

| 테이블 | 마이그레이션 | 핵심 컬럼 / 용도 |
|--------|-------------|----------------|
| **auctions** | a0c347536398 + 5e6f7a8b9c0d | 경매 물건 메인. case_number(UNIQUE), address, property_type, appraised_value, minimum_bid, auction_date, status, bid_count, court_office_code, lat/lng(float), building_type, build_year, exclusive_area_m2_real, floor_count, units_count_real, station_distance_m, location_data(JSONB), building_info(JSONB), detail(JSONB), market_price_info(JSONB), rent_price_info(JSONB), land_use_info(JSONB), occupancy_status/risk_level, winning_bid/date/ratio |
| **auction_rounds** | 5e6f7a8b9c0d | 기일 히스토리. auction_id(FK), round_no, bid_date, minimum_bid, result |
| **scores** | b1d458637499 | 채점 결과. auction_id(FK), grade(A~E), total_score, legal/price/location/occupancy_score, predicted_winning_ratio, grade_provisional |
| **filter_results** | a0c347536398 | 1단 필터 결과. auction_id(FK), result(RED/YELLOW/GREEN), triggered_rules(JSONB) |
| **registry_events** | a0c347536398 | 등기부 이벤트. auction_id(FK), section(갑/을구), event_type, holder, amount, accepted_at |
| **registry_analyses** | a0c347536398 | 등기부 분석 결과. auction_id(FK), hard_stops, base_right_type, analysis_result(JSONB) — **현재 0건** |
| **pipeline_runs** | a0c347536398 | 파이프라인 실행 로그. run_id, court_code, started/finished_at, counts |
| **occupancy_reports** | f7a1b2c3d4e5 | 현황조사서 원문. case_number(UNIQUE FK), raw_json(JSON) |
| **occupancy_tenants** | f7a1b2c3d4e5 | 임차인 상세. report_id(FK), tenant_name, deposit, monthly_rent, move_in_date |
| **occupancy_properties** | f7a1b2c3d4e5 | 점유 물건별. report_id(FK), address, tenant_count, possession_desc |
| **users** | d2e3f4a5b6c7 | 사용자. email(UNIQUE), google_sub, telegram_chat_id, telegram_verified_at |
| **user_favorites** | d2e3f4a5b6c7 | 즐겨찾기. user_id(FK), case_number |
| **user_saved_searches** | d2e3f4a5b6c7 | 저장 검색. user_id(FK), name, params_json(JSONB) |
| **telegram_verifications** | e3f4a5b6c7d8 | 텔레그램 연동 코드. user_id(FK), code(6자리), expires_at |

> 마이그레이션 체인 (최신순):
> `e3f4a5b6c7d8` ← `5e6f7a8b9c0d` ← `4d0e491c6f8f(merge)` ← `f7a1b2c3d4e5` ← `e5a2c947f310` ← `d4f721839b6c` ← `b1d458637499` ← `a0c347536398`

---

## 4. systemd 타이머 (홈서버, Ubuntu 24.04)

| 타이머 파일 | 실행 시각 | 명령 | 설명 |
|------------|----------|------|------|
| `kyungsa-batch.timer` | 매일 03:00 | `run_batch.py --all-seoul` | 서울 5개 법원 신규 물건 수집 + 채점 |
| `kyungsa-occupancy.timer` | 매일 04:00 | 현황조사서 수집 스크립트 | 진행 물건 현황조사서 자동 수집 |
| `kyungsa-fix-past-due.timer` | 매일 04:30 | `scripts/fix_past_due.py` | 기일경과 물건 상태 복원 |
| `kyungsa-sale-results.timer` | 매일 06:00 | 낙찰 결과 수집 스크립트 | 전국 낙찰 완료 건 상태/낙찰가 갱신 |
| `kyungsa-winning-bids.timer` | 매주 일 07:00 | 낙찰가 추적 스크립트 | 기수집 물건 낙찰가 일괄 추적 |

> 서비스 파일: `deploy/*.service` / 설치 위치: `/etc/systemd/system/`

---

## 5. 완료된 Phase 목록

| Phase | 내용 | 완료 시점 |
|-------|------|----------|
| 0~5F | 전체 파이프라인 (크롤러→보강→필터→등기부→점수→배치) | 2026-02 |
| Phase 6 | 입지 데이터 (Vworld, 역 거리, 편의시설) | 2026-02 |
| Phase 7 | 현황조사서 + 명도 데이터 | 2026-02 |
| Phase 8 | CatBoost ML 낙찰가율 예측 + Vercel 배포 | 2026-02 |
| Phase 9 | UX 재설계 (랜딩/검색 분리, Framer Motion) | 2026-02 |
| Phase A | 홈 리디자인 | 2026-03 |
| Phase B~D | AuctionListRow + SearchResultsList + 리스트뷰 전환 | 2026-03 |
| Phase E | 홈 3섹션 개편 + 점수근거 Accordion + 기일 0원 필터 | 2026-03 |
| Phase F | 권리분석 잠금 UI + 등기부 열람 CTA + 등급/ML 근거 Tooltip | 2026-03 |
| Phase G | InvestmentCalculator v1 (낙찰가 슬라이더 + 세금/대출/수익률) | 2026-03 |
| Phase H-1~4 | 건축물대장 자동채움 + 월세 실거래가 + 대출 금리 + 룸 테이블 | 2026-03 |
| Phase H-5 | 한국부동산원 R-ONE API 상가 임대료 레퍼런스 | 2026-03 |
| Phase I | Google OAuth (NextAuth.js v5) + JWT + 즐겨찾기/저장검색 DB | 2026-03 |
| Phase K-1 | 상세 페이지 2컬럼 + 로드뷰 + 전유부 호실 자동채움 | 2026-03 |
| Phase K-2 | 검색 페이지 전면 재설계 (SearchSidebar 8섹션 + 리스크 신호등) | 2026-03 |
| Phase DB-REBUILD | DB 정규화 (11개 컬럼 추출, auction_rounds 테이블 신설) | 2026-03 |

---

## 6. TODO / 미구현 기능

### 코드 내 TODO/FIXME
- 백엔드 Python 코드에서 TODO/FIXME 없음 (코드베이스 전수 검색 결과)

### 백로그 (계획됨)

| 항목 | 상태 | 비고 |
|------|------|------|
| **Phase J: 텔레그램 알림** | ⏳ 다음 | 즐겨찾기 D-day 알림, 상태변경 알림. Webhook endpoint는 구현 완료 |
| **325건 location_data 재수집** | ⏳ 잔여 | geocode 실패 케이스 → 주소 정규화 후 재시도. 현재 진행 3,245건 중 2,924건(90.1%) 확보 |
| **CODEF 등기부 v1 API 연결** | ⏳ 미구현 | 백엔드 pipeline 구현 완료. `registry_analyses` 0건 (한 번도 호출 안 됨). 프론트는 static iros.go.kr 링크만 |
| **잘못된 area_m2 재수집** | ⏳ 잔여 | enricher `expoArea` 버그 수정 후 기존 DB 데이터 재보강 필요 |
| **서울시 상권분석 연동** | 📋 백로그 | golmok.seoul.go.kr 유동인구/카드매출 |
| **Nginx 리버스프록시 설정** | 📋 백로그 | 홈서버 직접 배포 구성 |

---

## 7. 프론트엔드 컴포넌트 → API 매핑

### 공개 API (`frontend/lib/api.ts`, 인증 불필요)

| 호출 함수 | 엔드포인트 | 캐시 | 사용 컴포넌트/페이지 |
|----------|-----------|------|-------------------|
| `fetchAuctions(params)` | `GET /api/v1/auctions` | 5분 (revalidate: 300) | `/search/page.tsx`, `/page.tsx` (홈), `/favorites/page.tsx` |
| `fetchAuctionDetail(caseNumber)` | `GET /api/v1/auctions/{case_number}` | 5분 | `/auction/[caseNumber]/page.tsx` |
| `fetchMapItems(params)` | `GET /api/v1/auctions/map` | 5분 | `/map/page.tsx` |
| `fetchRentReference(caseNumber)` | `GET /api/v1/auctions/{case_number}/rent-reference` | 없음 (client, useEffect) | `/auction/[caseNumber]/page.tsx` (CashflowSection) |

### 인증 API (`frontend/lib/auth-api.ts`, JWT 필요)

| 호출 함수 | 엔드포인트 | 사용 컴포넌트 |
|----------|-----------|--------------|
| `fetchFavorites(token)` | `GET /api/v1/users/me/favorites` | `FavoriteButton`, `/favorites/page.tsx` |
| `addFavorite(token, caseNumber)` | `PUT /api/v1/users/me/favorites/{case_number}` | `FavoriteButton` |
| `removeFavorite(token, caseNumber)` | `DELETE /api/v1/users/me/favorites/{case_number}` | `FavoriteButton` |
| `bulkSyncFavorites(token, caseNumbers)` | `POST /api/v1/users/me/favorites/bulk` | `FavoriteButton` (localStorage 마이그레이션) |
| `fetchSavedSearches(token)` | `GET /api/v1/users/me/saved-searches` | 검색 페이지 저장검색 드롭다운 |
| `saveSearch(token, name, params)` | `POST /api/v1/users/me/saved-searches` | 검색 저장 버튼 |
| `deleteSavedSearch(token, id)` | `DELETE /api/v1/users/me/saved-searches/{id}` | 저장검색 삭제 |
| `fetchTelegramStatus(token)` | `GET /api/v1/users/me/telegram` | 마이페이지 텔레그램 섹션 |
| `issueTelegramCode(token)` | `POST /api/v1/users/me/telegram/code` | 텔레그램 연동 버튼 |
| `disconnectTelegram(token)` | `DELETE /api/v1/users/me/telegram` | 텔레그램 연동 해제 버튼 |

### 인증 흐름
```
사용자 Google 로그인
  → NextAuth.js v5 (frontend)
  → POST /api/v1/auth/upsert (google_sub + email 전달)
  → 백엔드: users 테이블 upsert → JWT(HS256, 30일) 발급
  → NextAuth session에 backendToken 저장
  → 이후 모든 auth-api.ts 호출에 Authorization: Bearer {backendToken}
```

---

## 8. 인프라 구성

```
사용자 (브라우저)
  └── kyungsa.com → Vercel (프론트엔드, Next.js)
  └── api.kyungsa.com → Cloudflare Tunnel → 홈서버:8000 (FastAPI)

홈서버 (MSI GP75, Ubuntu Server 24.04)
  ├── FastAPI (uvicorn, port 8000) — systemd kyungsa.service
  ├── PostgreSQL 16 — DB: kyungsa_db
  ├── systemd 타이머 5개 (배치 수집)
  └── Tailscale 100.71.156.101 (원격 접속용)

배포 흐름: Mac(개발) → git push → homeserver git pull → sudo systemctl restart kyungsa
```

---

## 9. 주요 배치 스크립트 명령어

```bash
# 홈서버 venv 활성화
source backend/.venv/bin/activate && cd /home/eric/projects/KYUNGSA

# 단일 법원 수집
PYTHONPATH=backend python scripts/run_batch.py --court B000210

# 서울 전체 수집
PYTHONPATH=backend python scripts/run_batch.py --all-seoul

# DB 재채점 (진행 물건만, 강제 전체)
PYTHONPATH=backend python scripts/run_batch.py --rescore-db --status 진행 --force

# location_data 없고 좌표 있는 물건만 재채점
PYTHONPATH=backend python scripts/run_batch.py --rescore-db --missing-location --status 진행

# 기일경과 복원
PYTHONPATH=backend python scripts/fix_past_due.py

# 검증 쿼리 (진행 물건 데이터 커버리지)
PYTHONPATH=backend python -c "
from sqlalchemy import text
from app.database import SessionLocal
db = SessionLocal()
r = db.execute(text('''
  SELECT COUNT(*) total,
    SUM(CASE WHEN lat IS NOT NULL THEN 1 ELSE 0 END) has_coords,
    SUM(CASE WHEN location_data IS NOT NULL THEN 1 ELSE 0 END) has_loc_data,
    SUM(CASE WHEN station_distance_m IS NOT NULL THEN 1 ELSE 0 END) has_station
  FROM auctions WHERE status = :s
'''), {'s': '진행'}).fetchone()
print(f'total={r[0]}, coords={r[1]}, loc_data={r[2]}, station={r[3]}')
db.close()
"
```

---

*마지막 업데이트: 2026-03-22*
*다음 작업: Phase J (텔레그램 알림) 또는 325건 location_data 재수집*
