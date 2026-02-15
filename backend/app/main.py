"""FastAPI 애플리케이션 엔트리포인트

실행: uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auctions import router as auction_router

app = FastAPI(
    title="KYUNGSA 경매 리스크 분석 API",
    version="0.3.0",
    description="부동산 경매 물건 필터링 + 등기부 리스크 분석",
)

# CORS (프론트엔드 연동 대비, 개발 단계)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auction_router)


@app.get("/health")
def health_check():
    """헬스 체크"""
    return {"status": "ok"}
