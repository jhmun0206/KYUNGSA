"""경매 물건 API 라우터

엔드포인트:
- GET  /api/auctions              — 법원별 경매 목록 (1단 필터링)
- GET  /api/auctions/{case_number} — 개별 물건 상세 (1단 + 2단)
- POST /api/auctions/analyze       — 단일 물건 즉시 분석
- GET  /api/registry/{unique_no}   — 등기부 분석 단독 조회
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_pipeline, get_registry_pipeline
from app.api.schemas import (
    AnalyzeRequest,
    AuctionDetailResponse,
    AuctionListResponse,
    RegistryAnalysisResponse,
    enriched_to_detail,
    enriched_to_summary,
    pipeline_result_to_registry,
)
from app.models.auction import AuctionCaseDetail
from app.services.address_parser import AddressParseError, extract_codef_params
from app.services.pipeline import AuctionPipeline
from app.services.registry.pipeline import (
    NoRegistryFoundError,
    RegistryPipeline,
    RegistryPipelineError,
)
from app.services.registry.provider import RegistryTwoWayAuthRequired

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["auctions"])


# ── GET /api/auctions ─────────────────────────────────────────


@router.get("/auctions", response_model=AuctionListResponse)
def list_auctions(
    court_code: str = Query(..., description="법원코드 (예: B000210)"),
    max_items: int = Query(20, ge=1, le=100, description="최대 조회 건수"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pipeline: AuctionPipeline = Depends(get_pipeline),
):
    """1단 필터링 결과 목록

    법원코드로 경매 물건을 검색하고 1단 필터(+2단 등기부) 결과를 반환한다.
    DB 없이 매 요청마다 크롤링→필터링 실행 (인메모리).
    """
    result = pipeline.run(court_code=court_code, max_items=max_items)

    items = [enriched_to_summary(e) for e in result.cases]

    # 간이 페이지네이션 (인메모리)
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = items[start:end]

    return AuctionListResponse(
        items=paged_items,
        total=len(items),
        page=page,
        page_size=page_size,
    )


# ── POST /api/auctions/analyze (analyze가 {case_number} 앞에 와야 함) ──


@router.post("/auctions/analyze", response_model=AuctionDetailResponse)
def analyze_single(
    request: AnalyzeRequest,
    pipeline: AuctionPipeline = Depends(get_pipeline),
):
    """단일 물건 즉시 분석 (주소 입력)

    주소를 파싱하여 등기부 분석까지 수행한다.
    """
    try:
        extract_codef_params(address=request.address)
    except AddressParseError as e:
        raise HTTPException(status_code=400, detail=f"주소 파싱 실패: {e}") from e

    detail = AuctionCaseDetail(
        case_number="ANALYZE-TEMP",
        court="",
        property_type="",
        address=request.address,
        appraised_value=request.appraisal_value or 0,
        minimum_bid=request.minimum_bid or 0,
    )

    enriched = pipeline.run_single(detail)
    return enriched_to_detail(enriched)


# ── GET /api/auctions/{case_number} ───────────────────────────


@router.get("/auctions/{case_number}", response_model=AuctionDetailResponse)
def get_auction_detail(
    case_number: str,
    pipeline: AuctionPipeline = Depends(get_pipeline),
):
    """개별 물건 상세 (1단 + 2단)

    DB 없이 사건번호로 재조회+분석을 수행한다.
    현재는 전체 검색 후 case_number 매칭.
    """
    result = pipeline.run(court_code="", max_items=100)

    for enriched in result.cases:
        if enriched.case.case_number == case_number:
            return enriched_to_detail(enriched)

    raise HTTPException(status_code=404, detail=f"물건을 찾을 수 없습니다: {case_number}")


# ── GET /api/registry/{unique_no} ─────────────────────────────


@router.get("/registry/{unique_no}", response_model=RegistryAnalysisResponse)
def get_registry(
    unique_no: str,
    registry_pipeline: RegistryPipeline = Depends(get_registry_pipeline),
):
    """등기부 분석 단독 조회

    CODEF 고유번호로 등기부를 직접 조회하고 분석한다.
    """
    try:
        result = registry_pipeline.analyze_by_unique_no(unique_no=unique_no)
    except NoRegistryFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RegistryPipelineError as e:
        raise HTTPException(
            status_code=500, detail=f"등기부 분석 실패: {e}"
        ) from e
    except RegistryTwoWayAuthRequired as e:
        raise HTTPException(status_code=503, detail="CODEF 추가 인증 필요") from e

    return pipeline_result_to_registry(result)
