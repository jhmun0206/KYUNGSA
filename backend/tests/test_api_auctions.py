"""API 엔드포인트 테스트

FastAPI TestClient + mock 서비스 주입.
실제 외부 API 호출 없이 엔드포인트 동작을 검증한다.
"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_pipeline, get_registry_pipeline
from app.main import app
from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import (
    EnrichedCase,
    FilterColor,
    FilterResult,
    PipelineResult,
    RuleMatch,
)
from app.models.registry import (
    Confidence,
    RegistryAnalysisResult,
    RegistryDocument,
    RegistryEvent,
    EventType,
    SectionType,
)
from app.services.registry.pipeline import (
    NoRegistryFoundError,
    RegistryPipelineError,
    RegistryPipelineResult,
)
from app.services.registry.provider import RegistryTwoWayAuthRequired


# ── 헬퍼 ──────────────────────────────────────────────────────


def _make_detail(case_number: str = "2025타경10001") -> AuctionCaseDetail:
    return AuctionCaseDetail(
        case_number=case_number,
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123-4",
        appraised_value=500_000_000,
        minimum_bid=320_000_000,
        auction_date=date(2026, 3, 15),
    )


def _make_enriched(
    case_number: str = "2025타경10001",
    color: FilterColor = FilterColor.GREEN,
) -> EnrichedCase:
    detail = _make_detail(case_number)
    rules = []
    if color == FilterColor.RED:
        rules = [RuleMatch(rule_id="R001", rule_name="개발제한구역", description="그린벨트")]
    return EnrichedCase(
        case=detail,
        filter_result=FilterResult(
            color=color,
            passed=color != FilterColor.RED,
            matched_rules=rules,
        ),
    )


def _make_pipeline_result(cases: list[EnrichedCase] | None = None) -> PipelineResult:
    if cases is None:
        cases = [_make_enriched()]
    return PipelineResult(
        total_searched=len(cases),
        total_enriched=len(cases),
        total_filtered=len(cases),
        green_count=sum(1 for c in cases if c.filter_result and c.filter_result.color == FilterColor.GREEN),
        cases=cases,
    )


def _make_registry_pipeline_result() -> RegistryPipelineResult:
    doc = RegistryDocument(source="codef")
    analysis = RegistryAnalysisResult(
        document=doc,
        confidence=Confidence.HIGH,
        summary="테스트 요약",
    )
    return RegistryPipelineResult(
        unique_no="11460000012345",
        address="서울특별시 강남구 역삼동 123-45",
        registry_document=doc,
        analysis=analysis,
    )


# ── Fixture ───────────────────────────────────────────────────


@pytest.fixture()
def mock_pipeline():
    """mock AuctionPipeline"""
    mock = MagicMock()
    mock.run.return_value = _make_pipeline_result()
    mock.run_single.return_value = _make_enriched()
    return mock


@pytest.fixture()
def mock_registry():
    """mock RegistryPipeline"""
    mock = MagicMock()
    mock.analyze_by_unique_no.return_value = _make_registry_pipeline_result()
    return mock


@pytest.fixture()
def client(mock_pipeline, mock_registry):
    """mock 주입된 TestClient"""
    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline
    app.dependency_overrides[get_registry_pipeline] = lambda: mock_registry
    yield TestClient(app)
    app.dependency_overrides.clear()


# ============================================================
# TestHealthCheck
# ============================================================


class TestHealthCheck:
    """헬스 체크"""

    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ============================================================
# TestListAuctions — GET /api/auctions
# ============================================================


class TestListAuctions:
    """GET /api/auctions"""

    def test_normal_list(self, client: TestClient) -> None:
        """정상 목록 반환"""
        resp = client.get("/api/auctions?court_code=B000210")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["case_number"] == "2025타경10001"

    def test_court_code_required(self, client: TestClient) -> None:
        """court_code 누락 → 422"""
        resp = client.get("/api/auctions")
        assert resp.status_code == 422

    def test_pagination(self, client: TestClient, mock_pipeline) -> None:
        """페이지네이션 동작"""
        cases = [_make_enriched(f"2025타경{i:05d}") for i in range(5)]
        mock_pipeline.run.return_value = _make_pipeline_result(cases)

        resp = client.get("/api/auctions?court_code=B000210&page=2&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["case_number"] == "2025타경00002"

    def test_empty_results(self, client: TestClient, mock_pipeline) -> None:
        """빈 결과 → 빈 리스트"""
        mock_pipeline.run.return_value = _make_pipeline_result([])
        resp = client.get("/api/auctions?court_code=B000210")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_filter_result_in_items(self, client: TestClient, mock_pipeline) -> None:
        """필터 결과가 items에 포함"""
        cases = [
            _make_enriched("A", FilterColor.GREEN),
            _make_enriched("B", FilterColor.RED),
        ]
        mock_pipeline.run.return_value = _make_pipeline_result(cases)

        resp = client.get("/api/auctions?court_code=B000210")
        data = resp.json()
        assert data["items"][0]["filter_result"] == "GREEN"
        assert data["items"][1]["filter_result"] == "RED"
        assert "그린벨트" in data["items"][1]["filter_reasons"][0]


# ============================================================
# TestGetAuctionDetail — GET /api/auctions/{case_number}
# ============================================================


class TestGetAuctionDetail:
    """GET /api/auctions/{case_number}"""

    def test_found(self, client: TestClient) -> None:
        """존재하는 물건"""
        resp = client.get("/api/auctions/2025타경10001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_number"] == "2025타경10001"
        assert data["filter_result"] == "GREEN"

    def test_not_found(self, client: TestClient, mock_pipeline) -> None:
        """존재하지 않는 물건 → 404"""
        mock_pipeline.run.return_value = _make_pipeline_result([])
        resp = client.get("/api/auctions/NONEXIST")
        assert resp.status_code == 404

    def test_detail_with_registry(self, client: TestClient, mock_pipeline) -> None:
        """등기부 분석 포함 물건"""
        enriched = _make_enriched()
        enriched.registry_analysis = RegistryAnalysisResult(
            document=RegistryDocument(source="codef"),
            confidence=Confidence.HIGH,
            summary="테스트 분석",
        )
        enriched.registry_unique_no = "12345"
        mock_pipeline.run.return_value = _make_pipeline_result([enriched])

        resp = client.get("/api/auctions/2025타경10001")
        data = resp.json()
        assert data["registry"] is not None
        assert data["registry"]["unique_no"] == "12345"

    def test_detail_without_registry(self, client: TestClient) -> None:
        """등기부 없는 물건 → registry=null"""
        resp = client.get("/api/auctions/2025타경10001")
        data = resp.json()
        assert data["registry"] is None


# ============================================================
# TestAnalyzeSingle — POST /api/auctions/analyze
# ============================================================


class TestAnalyzeSingle:
    """POST /api/auctions/analyze"""

    def test_normal_analysis(self, client: TestClient) -> None:
        """정상 분석"""
        resp = client.post(
            "/api/auctions/analyze",
            json={"address": "서울특별시 강남구 역삼동 123-4"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["address"] == "서울특별시 강남구 역삼동 123-4"

    def test_bad_address(self, client: TestClient) -> None:
        """잘못된 주소 → 400"""
        resp = client.post(
            "/api/auctions/analyze",
            json={"address": ""},
        )
        assert resp.status_code == 400
        assert "주소 파싱 실패" in resp.json()["detail"]

    def test_unknown_sido(self, client: TestClient) -> None:
        """인식 불가 시도 → 400"""
        resp = client.post(
            "/api/auctions/analyze",
            json={"address": "알수없는지역 강남구 역삼동 123"},
        )
        assert resp.status_code == 400


# ============================================================
# TestGetRegistry — GET /api/registry/{unique_no}
# ============================================================


class TestGetRegistry:
    """GET /api/registry/{unique_no}"""

    def test_normal(self, client: TestClient) -> None:
        """정상 등기부 조회"""
        resp = client.get("/api/registry/11460000012345")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unique_no"] == "11460000012345"
        assert data["analysis"]["confidence"] == "HIGH"

    def test_not_found(self, client: TestClient, mock_registry) -> None:
        """존재하지 않는 고유번호 → 404"""
        mock_registry.analyze_by_unique_no.side_effect = NoRegistryFoundError()
        resp = client.get("/api/registry/99999999999999")
        assert resp.status_code == 404

    def test_two_way_auth(self, client: TestClient, mock_registry) -> None:
        """CODEF 2-Way → 503"""
        mock_registry.analyze_by_unique_no.side_effect = RegistryTwoWayAuthRequired(
            jti="test-jti", two_way_timestamp="20260210"
        )
        resp = client.get("/api/registry/11460000012345")
        assert resp.status_code == 503
        assert "추가 인증" in resp.json()["detail"]

    def test_pipeline_error(self, client: TestClient, mock_registry) -> None:
        """분석 실패 → 500"""
        mock_registry.analyze_by_unique_no.side_effect = RegistryPipelineError("분석 오류")
        resp = client.get("/api/registry/11460000012345")
        assert resp.status_code == 500
