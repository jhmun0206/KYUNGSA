"""AuctionPipeline 단위 테스트

크롤러/보강기/필터 엔진을 mock하여 파이프라인 흐름을 검증한다.
2단 등기부 통합 테스트 포함.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.auction import (
    AuctionCaseDetail,
    AuctionCaseListItem,
)
from app.models.enriched_case import (
    EnrichedCase,
    FilterColor,
    FilterResult,
    PipelineResult,
)
from app.models.registry import (
    Confidence,
    RegistryAnalysisResult,
    RegistryDocument,
)
from app.services.address_parser import AddressParseError
from app.services.pipeline import AuctionPipeline
from app.services.registry.matcher import NoMatchError
from app.services.registry.pipeline import RegistryPipeline, RegistryPipelineResult


# --- 테스트 헬퍼 ---

def _make_list_item(case_number: str = "2025타경10001") -> AuctionCaseListItem:
    return AuctionCaseListItem(
        case_number=case_number,
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123-4",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
        court_office_code="B000210",
        internal_case_number="20250130010001",
        property_sequence="1",
    )


def _make_detail(case_number: str = "2025타경10001") -> AuctionCaseDetail:
    return AuctionCaseDetail(
        case_number=case_number,
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123-4",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
    )


def _make_enriched(
    case_number: str = "2025타경10001",
    color: FilterColor = FilterColor.GREEN,
) -> EnrichedCase:
    detail = _make_detail(case_number)
    return EnrichedCase(
        case=detail,
        filter_result=FilterResult(
            color=color,
            passed=color != FilterColor.RED,
        ),
    )


# === TestPipelineRun ===


class TestPipelineRun:
    """배치 파이프라인 run() 테스트"""

    def _setup_pipeline(
        self,
        items: list[AuctionCaseListItem] | None = None,
        detail: AuctionCaseDetail | None = None,
        enriched: EnrichedCase | None = None,
    ) -> AuctionPipeline:
        crawler = MagicMock()
        crawler.search_cases.return_value = items or [_make_list_item()]
        crawler.fetch_case_detail.return_value = detail or _make_detail()

        enricher = MagicMock()
        enricher.enrich.return_value = enriched or _make_enriched()

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        return AuctionPipeline(
            crawler=crawler,
            enricher=enricher,
            filter_engine=filter_engine,
        )

    def test_normal_flow(self):
        """정상 흐름: 검색 → 상세 → 보강 → 필터"""
        pipeline = self._setup_pipeline()
        with patch("app.services.pipeline.time.sleep"):
            result = pipeline.run(court_code="B000210", max_items=5)

        assert isinstance(result, PipelineResult)
        assert result.total_searched == 1
        assert result.total_enriched == 1
        assert result.total_filtered == 1
        assert len(result.cases) == 1

    def test_search_failure(self):
        """검색 실패 시 에러 기록 후 조기 종료"""
        crawler = MagicMock()
        crawler.search_cases.side_effect = Exception("네트워크 오류")
        pipeline = AuctionPipeline(crawler=crawler)

        result = pipeline.run()

        assert result.total_searched == 0
        assert len(result.errors) == 1
        assert "검색 실패" in result.errors[0]

    def test_detail_failure_continues(self):
        """상세 조회 실패 시 에러 기록 후 다음 물건 계속"""
        crawler = MagicMock()
        items = [_make_list_item(f"2025타경1000{i}") for i in range(3)]
        crawler.search_cases.return_value = items

        call_count = 0
        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("상세 조회 타임아웃")
            return _make_detail()

        crawler.fetch_case_detail.side_effect = side_effect

        enricher = MagicMock()
        enricher.enrich.return_value = _make_enriched()

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            crawler=crawler,
            enricher=enricher,
            filter_engine=filter_engine,
        )
        with patch("app.services.pipeline.time.sleep"):
            result = pipeline.run(max_items=3)

        assert result.total_searched == 3
        assert result.total_enriched == 2  # 3건 중 1건 실패
        assert len(result.errors) == 1
        assert len(result.cases) == 2

    def test_max_items_limit(self):
        """max_items로 처리 건수 제한"""
        items = [_make_list_item(f"2025타경1000{i}") for i in range(10)]
        pipeline = self._setup_pipeline(items=items)

        with patch("app.services.pipeline.time.sleep"):
            result = pipeline.run(max_items=3)

        assert result.total_searched == 10
        assert result.total_enriched == 3
        assert len(result.cases) == 3

    def test_color_count_aggregation(self):
        """RED/YELLOW/GREEN 카운트 집계"""
        items = [_make_list_item(f"2025타경1000{i}") for i in range(4)]

        crawler = MagicMock()
        crawler.search_cases.return_value = items
        crawler.fetch_case_detail.return_value = _make_detail()

        enricher = MagicMock()
        enricher.enrich.return_value = _make_enriched()

        colors = [FilterColor.RED, FilterColor.YELLOW, FilterColor.GREEN, FilterColor.GREEN]
        call_idx = 0

        def evaluate_side_effect(ec):
            nonlocal call_idx
            c = colors[call_idx]
            call_idx += 1
            return FilterResult(color=c, passed=c != FilterColor.RED)

        filter_engine = MagicMock()
        filter_engine.evaluate.side_effect = evaluate_side_effect

        pipeline = AuctionPipeline(
            crawler=crawler,
            enricher=enricher,
            filter_engine=filter_engine,
        )
        with patch("app.services.pipeline.time.sleep"):
            result = pipeline.run(max_items=4)

        assert result.red_count == 1
        assert result.yellow_count == 1
        assert result.green_count == 2

    def test_uses_list_item_fields_for_detail(self):
        """상세 조회 시 ListItem의 내부코드 필드 사용"""
        item = _make_list_item()
        item.internal_case_number = "20250130099999"
        item.court_office_code = "B000250"
        item.property_sequence = "2"

        crawler = MagicMock()
        crawler.search_cases.return_value = [item]
        crawler.fetch_case_detail.return_value = _make_detail()

        enricher = MagicMock()
        enricher.enrich.return_value = _make_enriched()

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            crawler=crawler,
            enricher=enricher,
            filter_engine=filter_engine,
        )
        with patch("app.services.pipeline.time.sleep"):
            pipeline.run()

        crawler.fetch_case_detail.assert_called_once_with(
            case_number="20250130099999",
            court_office_code="B000250",
            property_sequence="2",
        )


# === TestPipelineSingle ===


class TestPipelineSingle:
    """run_single() 테스트"""

    def test_run_single_normal(self):
        """단일 물건 정상 처리"""
        enricher = MagicMock()
        enriched = _make_enriched()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.YELLOW, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
        )
        result = pipeline.run_single(_make_detail())

        assert isinstance(result, EnrichedCase)
        enricher.enrich.assert_called_once()
        filter_engine.evaluate.assert_called_once()

    def test_run_single_enrichment_fail_returns_green(self):
        """보강 실패해도 filter_result는 설정됨"""
        enricher = MagicMock()
        # 보강은 성공하지만 모든 필드가 None인 EnrichedCase
        bare_enriched = EnrichedCase(case=_make_detail())
        enricher.enrich.return_value = bare_enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
        )
        result = pipeline.run_single(_make_detail())

        assert result.filter_result is not None
        assert result.filter_result.color == FilterColor.GREEN


# --- 2단 등기부 통합 테스트 헬퍼 ---


def _make_mock_registry_pipeline() -> MagicMock:
    """RegistryPipeline mock (provider + analyze_by_unique_no)"""
    mock_doc = RegistryDocument(source="codef")
    mock_analysis = RegistryAnalysisResult(
        document=mock_doc,
        confidence=Confidence.MEDIUM,
        summary="서울특별시 강남구 역삼동 — 말소기준 근저당, Hard Stop 없음",
    )
    mock_result = RegistryPipelineResult(
        unique_no="11460000012345",
        address="서울특별시 강남구 역삼동 123-45",
        registry_document=mock_doc,
        analysis=mock_analysis,
    )

    # spec 없이 생성 — _provider(private) 접근 필요
    mock_pipeline = MagicMock()
    mock_pipeline.analyze_by_unique_no.return_value = mock_result
    mock_pipeline._provider.search_by_address.return_value = [
        {
            "commUniqueNo": "11460000012345",
            "commAddrLotNumber": "서울특별시 강남구 역삼동 123-4",
            "resType": "집합건물",
        }
    ]
    return mock_pipeline


# === TestPipelineRegistryIntegration ===


class TestPipelineRegistryIntegration:
    """2단 등기부 통합 테스트"""

    def test_green_case_gets_registry_analysis(self) -> None:
        """GREEN 건 → 등기부 분석 수행"""
        mock_reg = _make_mock_registry_pipeline()
        enriched = _make_enriched(color=FilterColor.GREEN)

        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        assert result.registry_analysis is not None
        assert result.registry_unique_no == "11460000012345"
        assert result.registry_match_confidence is not None

    def test_yellow_case_gets_registry_analysis(self) -> None:
        """YELLOW 건 → 등기부 분석 수행 (passed=True)"""
        mock_reg = _make_mock_registry_pipeline()
        enriched = _make_enriched(color=FilterColor.YELLOW)

        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.YELLOW, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        assert result.registry_analysis is not None

    def test_red_case_skips_registry(self) -> None:
        """RED 건 → 등기부 분석 건너뜀"""
        mock_reg = _make_mock_registry_pipeline()
        enriched = _make_enriched(color=FilterColor.RED)

        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.RED, passed=False,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        assert result.registry_analysis is None
        assert result.registry_unique_no is None
        mock_reg._provider.search_by_address.assert_not_called()

    def test_no_registry_pipeline_runs_first_stage_only(self) -> None:
        """registry_pipeline 없으면 1단만 실행"""
        enriched = _make_enriched(color=FilterColor.GREEN)

        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=None,  # 명시적으로 없음
        )
        result = pipeline.run_single(_make_detail())

        assert result.filter_result is not None
        assert result.registry_analysis is None

    def test_address_parse_failure_preserves_first_stage(self) -> None:
        """주소 파싱 실패 → 1단 결과 유지, registry_error 기록"""
        mock_reg = _make_mock_registry_pipeline()

        # 빈 주소로 파싱 실패 유도
        detail = _make_detail()
        detail.address = ""

        enriched = EnrichedCase(
            case=detail,
            filter_result=FilterResult(color=FilterColor.GREEN, passed=True),
        )

        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(detail)

        assert result.filter_result is not None
        assert result.filter_result.color == FilterColor.GREEN
        assert result.registry_analysis is None
        assert result.registry_error is not None
        assert "주소 파싱 실패" in result.registry_error

    def test_no_search_results_preserves_first_stage(self) -> None:
        """CODEF 검색 결과 없음 → 1단 결과 유지"""
        mock_reg = _make_mock_registry_pipeline()
        mock_reg._provider.search_by_address.return_value = []

        enriched = _make_enriched(color=FilterColor.GREEN)
        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        assert result.registry_analysis is None
        assert result.registry_error == "CODEF 검색 결과 없음"

    def test_no_match_preserves_first_stage(self) -> None:
        """매칭 실패 → 1단 결과 유지, registry_error 기록"""
        mock_reg = _make_mock_registry_pipeline()
        # 동이 전혀 다른 결과만 반환 → matcher가 NoMatchError
        mock_reg._provider.search_by_address.return_value = [
            {
                "commUniqueNo": "WRONG",
                "commAddrLotNumber": "부산광역시 해운대구 우동 999",
            }
        ]

        enriched = _make_enriched(color=FilterColor.GREEN)
        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        assert result.registry_analysis is None
        assert result.registry_error is not None
        assert "매칭 실패" in result.registry_error

    def test_registry_api_failure_preserves_first_stage(self) -> None:
        """등기부 조회 실패 → 1단 결과 유지"""
        mock_reg = _make_mock_registry_pipeline()
        mock_reg.analyze_by_unique_no.side_effect = Exception("CODEF 서버 오류")

        enriched = _make_enriched(color=FilterColor.GREEN)
        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        assert result.filter_result.color == FilterColor.GREEN
        assert result.registry_analysis is None
        assert result.registry_error is not None
        assert "2단 분석 실패" in result.registry_error

    def test_correct_unique_no_selected_by_matcher(self) -> None:
        """matcher가 올바른 고유번호를 선택"""
        mock_reg = _make_mock_registry_pipeline()
        mock_reg._provider.search_by_address.return_value = [
            {
                "commUniqueNo": "WRONG",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 999-99",
            },
            {
                "commUniqueNo": "CORRECT",
                "commAddrLotNumber": "서울특별시 강남구 역삼동 123-4",
            },
        ]

        enriched = _make_enriched(color=FilterColor.GREEN)
        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        result = pipeline.run_single(_make_detail())

        # matcher가 지번 123-4와 일치하는 CORRECT를 선택
        mock_reg.analyze_by_unique_no.assert_called_once()
        call_kwargs = mock_reg.analyze_by_unique_no.call_args[1]
        assert call_kwargs["unique_no"] == "CORRECT"

    def test_batch_run_with_registry(self) -> None:
        """배치 run()에서 2단 통합 동작"""
        mock_reg = _make_mock_registry_pipeline()
        items = [_make_list_item(f"2025타경1000{i}") for i in range(2)]

        crawler = MagicMock()
        crawler.search_cases.return_value = items
        crawler.fetch_case_detail.return_value = _make_detail()

        enriched = _make_enriched(color=FilterColor.GREEN)
        enricher = MagicMock()
        enricher.enrich.return_value = enriched

        filter_engine = MagicMock()
        filter_engine.evaluate.return_value = FilterResult(
            color=FilterColor.GREEN, passed=True,
        )

        pipeline = AuctionPipeline(
            crawler=crawler,
            enricher=enricher,
            filter_engine=filter_engine,
            registry_pipeline=mock_reg,
        )
        with patch("app.services.pipeline.time.sleep"):
            result = pipeline.run(max_items=2)

        assert result.total_filtered == 2
        # 2건 모두 GREEN → 2단 분석 2회 호출
        assert mock_reg._provider.search_by_address.call_count == 2
