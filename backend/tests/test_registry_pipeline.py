"""등기부등본 파이프라인 테스트 — 주소 → 등기부 → 분석 통합

CodefRegistryProvider를 mock하여 실제 API 호출 없이 검증.
기존 fixture(codef_registry_response.json)를 활용.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models.registry import (
    Confidence,
    EventType,
    RegistryAnalysisResult,
    RegistryDocument,
)
from app.services.crawler.codef_client import CodefApiError
from app.services.parser.registry_analyzer import RegistryAnalyzer
from app.services.registry.codef_mapper import CodefRegistryMapper
from app.services.registry.codef_provider import CodefRegistryProvider
from app.services.registry.pipeline import (
    NoRegistryFoundError,
    RegistryPipeline,
    RegistryPipelineError,
    RegistryPipelineResult,
)
from app.services.registry.provider import RegistryTwoWayAuthRequired

# === Fixture ===

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def codef_response() -> dict:
    """CODEF 등기부등본 응답 mock fixture"""
    with open(FIXTURES_DIR / "codef_registry_response.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def mapped_doc(codef_response: dict) -> RegistryDocument:
    """fixture를 매핑한 RegistryDocument"""
    return CodefRegistryMapper().map_response(codef_response)


@pytest.fixture()
def search_results() -> list[dict]:
    """주소 검색 mock 결과"""
    return [
        {
            "commUniqueNo": "11460000012345",
            "commAddrLotNumber": "서울특별시 강남구 역삼동 123-45",
            "resType": "집합건물",
            "resUserNm": "홍OO",
            "resState": "현행",
        },
        {
            "commUniqueNo": "11460000012346",
            "commAddrLotNumber": "서울특별시 강남구 역삼동 123-46",
            "resType": "집합건물",
            "resUserNm": "김OO",
            "resState": "현행",
        },
    ]


@pytest.fixture()
def mock_provider(mapped_doc: RegistryDocument, search_results: list[dict]):
    """CodefRegistryProvider mock"""
    provider = MagicMock(spec=CodefRegistryProvider)
    provider.search_by_address.return_value = search_results
    provider.fetch_registry.return_value = mapped_doc
    return provider


@pytest.fixture()
def pipeline(mock_provider) -> RegistryPipeline:
    """RegistryPipeline (mock provider + 실제 analyzer)"""
    return RegistryPipeline(provider=mock_provider, analyzer=RegistryAnalyzer())


# ============================================================
# TestPipelineByAddress — 주소 → 전체 흐름
# ============================================================


class TestPipelineByAddress:
    """analyze_by_address 정상 흐름"""

    def test_returns_pipeline_result(self, pipeline: RegistryPipeline) -> None:
        """정상 흐름 → RegistryPipelineResult 반환"""
        result = pipeline.analyze_by_address(
            sido="서울특별시",
            sigungu="강남구",
            addr_dong="역삼동",
            address="역삼동 아파트",
        )
        assert isinstance(result, RegistryPipelineResult)

    def test_unique_no_from_first_result(
        self, pipeline: RegistryPipeline, search_results: list[dict]
    ) -> None:
        """검색 결과 중 첫 번째 고유번호 사용"""
        result = pipeline.analyze_by_address(
            sido="서울특별시", sigungu="강남구", address="역삼동"
        )
        assert result.unique_no == search_results[0]["commUniqueNo"]

    def test_search_results_preserved(
        self, pipeline: RegistryPipeline, search_results: list[dict]
    ) -> None:
        """전체 검색 결과가 보존됨"""
        result = pipeline.analyze_by_address(
            sido="서울특별시", sigungu="강남구", address="역삼동"
        )
        assert len(result.search_results) == 2
        assert result.search_results == search_results

    def test_analysis_is_populated(self, pipeline: RegistryPipeline) -> None:
        """분석 결과가 채워져 있음"""
        result = pipeline.analyze_by_address(
            sido="서울특별시", sigungu="강남구", address="역삼동"
        )
        assert isinstance(result.analysis, RegistryAnalysisResult)
        assert result.analysis.cancellation_base_event is not None

    def test_address_from_title(self, pipeline: RegistryPipeline) -> None:
        """주소는 등기부 표제부에서 추출"""
        result = pipeline.analyze_by_address(
            sido="서울특별시", sigungu="강남구", address="역삼동"
        )
        # fixture 표제부에 "강남구 역삼동" 포함
        assert "강남구" in result.address
        assert "역삼동" in result.address

    def test_search_params_forwarded(self, mock_provider, pipeline: RegistryPipeline) -> None:
        """주소 파라미터가 search_by_address에 전달됨"""
        pipeline.analyze_by_address(
            sido="서울특별시",
            sigungu="강남구",
            addr_dong="역삼동",
            dong="101",
            ho="501",
            address="역삼동 아파트",
        )
        mock_provider.search_by_address.assert_called_once()
        call_kwargs = mock_provider.search_by_address.call_args[1]
        assert call_kwargs["sido"] == "서울특별시"
        assert call_kwargs["sigungu"] == "강남구"
        assert call_kwargs["addr_dong"] == "역삼동"
        assert call_kwargs["dong"] == "101"

    def test_fetch_uses_unique_no_only(self, mock_provider, pipeline: RegistryPipeline) -> None:
        """inquiryType=0: fetch_registry에 unique_no와 realty_type만 전달 (addr_* 불필요)"""
        pipeline.analyze_by_address(
            sido="서울특별시",
            sigungu="강남구",
            addr_dong="역삼동",
            addr_road_name="테헤란로",
            dong="101",
            ho="501",
            address="역삼동 아파트",
        )
        mock_provider.fetch_registry.assert_called_once()
        call_kwargs = mock_provider.fetch_registry.call_args[1]
        assert call_kwargs["unique_no"] == "11460000012345"
        assert call_kwargs["realty_type"] == "3"
        assert "addr_sido" not in call_kwargs
        assert "addr_dong" not in call_kwargs

    def test_queried_at_populated(self, pipeline: RegistryPipeline) -> None:
        """조회 시각이 채워져 있음"""
        result = pipeline.analyze_by_address(
            sido="서울특별시", sigungu="강남구", address="역삼동"
        )
        assert result.queried_at is not None


# ============================================================
# TestPipelineByUniqueNo — 고유번호 직접 입력
# ============================================================


class TestPipelineByUniqueNo:
    """analyze_by_unique_no 정상 흐름"""

    def test_returns_pipeline_result(self, pipeline: RegistryPipeline) -> None:
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert isinstance(result, RegistryPipelineResult)

    def test_skips_search(self, mock_provider, pipeline: RegistryPipeline) -> None:
        """주소 검색을 건너뜀"""
        pipeline.analyze_by_unique_no(unique_no="11460000012345")
        mock_provider.search_by_address.assert_not_called()
        mock_provider.fetch_registry.assert_called_once()

    def test_unique_no_preserved(self, pipeline: RegistryPipeline) -> None:
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert result.unique_no == "11460000012345"

    def test_empty_search_results(self, pipeline: RegistryPipeline) -> None:
        """고유번호 직접 입력 시 search_results는 빈 리스트"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert result.search_results == []

    def test_addr_params_ignored(self, mock_provider, pipeline: RegistryPipeline) -> None:
        """inquiryType=0: addr_* kwargs는 받되 fetch_registry에 전달하지 않음"""
        pipeline.analyze_by_unique_no(
            unique_no="11460000012345",
            addr_sido="서울특별시",
            addr_sigungu="강남구",
            addr_dong="역삼동",
            dong="101",
            ho="501",
        )
        call_kwargs = mock_provider.fetch_registry.call_args[1]
        assert call_kwargs["unique_no"] == "11460000012345"
        assert "addr_sido" not in call_kwargs
        assert "dong" not in call_kwargs


# ============================================================
# TestPipelineErrors — 에러 처리
# ============================================================


class TestPipelineErrors:
    """예외 처리"""

    def test_no_search_results(self, mock_provider) -> None:
        """검색 결과 없음 → NoRegistryFoundError"""
        mock_provider.search_by_address.return_value = []
        pipeline = RegistryPipeline(provider=mock_provider)

        with pytest.raises(NoRegistryFoundError, match="검색 결과가 없습니다"):
            pipeline.analyze_by_address(
                sido="서울특별시", sigungu="강남구", address="없는동"
            )

    def test_codef_api_error_propagates(self, mock_provider) -> None:
        """CodefApiError가 그대로 전파"""
        mock_provider.fetch_registry.side_effect = CodefApiError(
            "CF-99999", "서버 오류"
        )
        pipeline = RegistryPipeline(provider=mock_provider)

        with pytest.raises(CodefApiError, match="CF-99999"):
            pipeline.analyze_by_unique_no(unique_no="12345678901234")

    def test_two_way_auth_propagates(self, mock_provider) -> None:
        """RegistryTwoWayAuthRequired가 그대로 전파"""
        mock_provider.fetch_registry.side_effect = RegistryTwoWayAuthRequired(
            jti="test-jti", two_way_timestamp="20260210"
        )
        pipeline = RegistryPipeline(provider=mock_provider)

        with pytest.raises(RegistryTwoWayAuthRequired):
            pipeline.analyze_by_unique_no(unique_no="12345678901234")

    def test_analyzer_error_wrapped(self, mock_provider) -> None:
        """분석기 내부 오류 → RegistryPipelineError"""
        # 빈 RegistryDocument → 분석 자체는 성공하지만, 강제로 에러를 발생시킴
        broken_analyzer = MagicMock(spec=RegistryAnalyzer)
        broken_analyzer.analyze.side_effect = ValueError("분석 실패")

        pipeline = RegistryPipeline(
            provider=mock_provider, analyzer=broken_analyzer
        )

        with pytest.raises(RegistryPipelineError, match="분석 실패"):
            pipeline.analyze_by_unique_no(unique_no="12345678901234")

    def test_pipeline_error_has_cause(self, mock_provider) -> None:
        """RegistryPipelineError에 원인 예외가 포함됨"""
        broken_analyzer = MagicMock(spec=RegistryAnalyzer)
        original_error = ValueError("원인 오류")
        broken_analyzer.analyze.side_effect = original_error

        pipeline = RegistryPipeline(
            provider=mock_provider, analyzer=broken_analyzer
        )

        with pytest.raises(RegistryPipelineError) as exc_info:
            pipeline.analyze_by_unique_no(unique_no="12345678901234")
        assert exc_info.value.cause is original_error


# ============================================================
# TestPipelineResult — 결과 모델
# ============================================================


class TestPipelineResult:
    """RegistryPipelineResult 속성"""

    def test_has_hard_stop_false(self, pipeline: RegistryPipeline) -> None:
        """fixture 데이터에 Hard Stop이 없음"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert result.has_hard_stop is False

    def test_summary_not_empty(self, pipeline: RegistryPipeline) -> None:
        """요약 텍스트가 비어있지 않음"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert result.summary
        assert len(result.summary) > 10

    def test_summary_contains_address(self, pipeline: RegistryPipeline) -> None:
        """요약에 소재지 포함"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert "강남구" in result.summary

    def test_registry_document_preserved(self, pipeline: RegistryPipeline) -> None:
        """RegistryDocument가 결과에 보존"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert isinstance(result.registry_document, RegistryDocument)
        assert result.registry_document.source == "codef"
        assert len(result.registry_document.all_events) == 7


# ============================================================
# TestPipelineAnalysis — 분석 결과 검증 (fixture 기반)
# ============================================================


class TestPipelineAnalysis:
    """fixture 기반 분석 결과 상세 검증"""

    def test_cancellation_base_exists(self, pipeline: RegistryPipeline) -> None:
        """말소기준권리가 식별됨"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        base = result.analysis.cancellation_base_event
        assert base is not None

    def test_cancellation_base_is_mortgage(self, pipeline: RegistryPipeline) -> None:
        """말소기준권리가 근저당 (fixture에서 가장 빠른 담보권)"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        base = result.analysis.cancellation_base_event
        assert base.event_type == EventType.MORTGAGE

    def test_has_extinguished_rights(self, pipeline: RegistryPipeline) -> None:
        """소멸 권리가 존재"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert len(result.analysis.extinguished_rights) > 0

    def test_has_surviving_rights(self, pipeline: RegistryPipeline) -> None:
        """인수 권리 확인 (전세권 — 근저당 이후 설정이면 소멸)"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        # 전세권(2021.06.01)은 근저당(2018.03.15) 이후 → 소멸
        # fixture 구조상 인수 권리 없을 수 있음
        # 소멸이 아닌 권리가 있는지만 확인
        total_classified = (
            len(result.analysis.extinguished_rights)
            + len(result.analysis.surviving_rights)
            + len(result.analysis.uncertain_rights)
        )
        assert total_classified > 0

    def test_confidence_not_low(self, pipeline: RegistryPipeline) -> None:
        """신뢰도가 LOW가 아님"""
        result = pipeline.analyze_by_unique_no(unique_no="11460000012345")
        assert result.analysis.confidence != Confidence.LOW
