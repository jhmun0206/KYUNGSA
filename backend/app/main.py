"""FastAPI 애플리케이션 엔트리포인트

실행: uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auctions import router as v1_router
from app.api.v1.auth import router as auth_router
from app.api.v1.telegram import router as telegram_router
from app.api.v1.users import router as users_router

app = FastAPI(
    title="KYUNGSA 경매 리스크 분석 API",
    version="0.4.0",
    description="부동산 경매 물건 필터링 + 등기부 리스크 분석 + 대시보드 API",
)

# CORS — Phase I: POST/PUT/DELETE 허용 (사용자 API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",                    # 로컬 개발
        "https://kyungsa.vercel.app",              # Vercel 기본 도메인
        "https://kyungsa-frontend.vercel.app",     # Vercel 프로젝트 도메인
        "https://kyungsa.com",                     # 커스텀 도메인
        "https://www.kyungsa.com",                 # www 서브도메인
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# DB 기반 대시보드 API (v1)
app.include_router(v1_router, prefix="/api/v1")

# Phase I: 인증 + 사용자 API
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

# Phase J: 텔레그램 Webhook (prefix 없음 — /telegram/webhook)
app.include_router(telegram_router)


@app.get("/health")
def health_check():
    """헬스 체크"""
    return {"status": "ok"}
