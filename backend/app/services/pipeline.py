"""1단+2단 파이프라인 오케스트레이터

1단: 크롤러 → 보강기 → 필터 엔진 (RED/YELLOW/GREEN)
2단: CODEF 주소검색 → 매칭 → 등기부 조회 → 분석 (1단 통과 건만)
"""

import logging
import time

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import (
    EnrichedCase,
    FilterColor,
    PipelineResult,
)
from app.services.address_parser import (
    AddressParseError,
    extract_codef_params,
)
from app.services.crawler.court_auction import CourtAuctionClient
from app.services.enricher import CaseEnricher
from app.services.filter_engine import FilterEngine
from app.services.registry.matcher import NoMatchError, RegistryMatcher
from app.services.registry.pipeline import RegistryPipeline
from app.services.rules.price_scorer import PriceScorer
from app.services.rules.total_scorer import TotalScorer

logger = logging.getLogger(__name__)


class AuctionPipeline:
    """1단+2단 통합 파이프라인"""

    def __init__(
        self,
        crawler: CourtAuctionClient | None = None,
        enricher: CaseEnricher | None = None,
        filter_engine: FilterEngine | None = None,
        registry_pipeline: RegistryPipeline | None = None,
    ) -> None:
        self._crawler = crawler or CourtAuctionClient()
        self._enricher = enricher or CaseEnricher()
        self._filter = filter_engine or FilterEngine()
        self._registry_pipeline = registry_pipeline
        self._matcher = RegistryMatcher()
        self._price_scorer = PriceScorer()
        self._total_scorer = TotalScorer()

    def run(
        self,
        court_code: str = "",
        max_items: int = 20,
        enrich_delay: float = 2.0,
    ) -> PipelineResult:
        """배치 파이프라인 실행

        Args:
            court_code: 법원코드 (빈 문자열이면 전체)
            max_items: 최대 처리 물건 수
            enrich_delay: 보강 API 호출 간 대기 시간 (초)

        Returns:
            PipelineResult
        """
        result = PipelineResult()

        # 1단계: 검색
        try:
            items = self._crawler.search_cases(court_code=court_code)
            result.total_searched = len(items)
            logger.info("검색 완료: %d건", len(items))
        except Exception as e:
            logger.error("검색 실패: %s", e)
            result.errors.append(f"검색 실패: {e}")
            return result

        # 2단계: 상세 조회 + 보강 + 필터링 (+ 2단 등기부 분석)
        for i, item in enumerate(items[:max_items]):
            if i > 0:
                time.sleep(enrich_delay)

            try:
                # 상세 조회
                detail = self._crawler.fetch_case_detail(
                    case_number=item.internal_case_number,
                    court_office_code=item.court_office_code,
                    property_sequence=item.property_sequence or "1",
                )

                # 보강
                enriched = self._enricher.enrich(detail)
                result.total_enriched += 1

                # 필터링
                enriched.filter_result = self._filter.evaluate(enriched)
                result.total_filtered += 1

                # 가격 매력도 점수 (1단 데이터만으로 산출)
                enriched.price_score = self._price_scorer.score(
                    case=enriched.case,
                    market_price=enriched.market_price,
                )

                # 카운트 집계
                color = enriched.filter_result.color
                if color == FilterColor.RED:
                    result.red_count += 1
                elif color == FilterColor.YELLOW:
                    result.yellow_count += 1
                else:
                    result.green_count += 1

                # 2단: 1단 필터 통과 건만 등기부 분석
                if (
                    self._registry_pipeline
                    and enriched.filter_result.passed
                ):
                    self._run_registry_analysis(enriched)

                # 통합 점수 (가용 pillar 가중 합산)
                enriched.total_score = self._total_scorer.score(
                    property_type=enriched.case.property_type,
                    legal_score=enriched.legal_score.score if enriched.legal_score else None,
                    price_score=enriched.price_score.score if enriched.price_score else None,
                    needs_expert_review=(
                        enriched.legal_score.needs_expert_review
                        if enriched.legal_score else False
                    ),
                )

                result.cases.append(enriched)

            except Exception as e:
                logger.error("물건 처리 실패 [%s]: %s", item.case_number, e)
                result.errors.append(f"[{item.case_number}] {e}")

        logger.info(
            "파이프라인 완료: 검색=%d, 보강=%d, 필터=%d (R=%d, Y=%d, G=%d)",
            result.total_searched, result.total_enriched, result.total_filtered,
            result.red_count, result.yellow_count, result.green_count,
        )
        return result

    def run_single(self, case_detail: AuctionCaseDetail) -> EnrichedCase:
        """단일 물건 처리 (이미 상세 조회된 경우)"""
        enriched = self._enricher.enrich(case_detail)
        enriched.filter_result = self._filter.evaluate(enriched)

        # 가격 매력도 점수 (1단 데이터만으로 산출)
        enriched.price_score = self._price_scorer.score(
            case=enriched.case,
            market_price=enriched.market_price,
        )

        # 2단: 1단 필터 통과 건만
        if (
            self._registry_pipeline
            and enriched.filter_result
            and enriched.filter_result.passed
        ):
            self._run_registry_analysis(enriched)

        # 통합 점수 (가용 pillar 가중 합산)
        enriched.total_score = self._total_scorer.score(
            property_type=enriched.case.property_type,
            legal_score=enriched.legal_score.score if enriched.legal_score else None,
            price_score=enriched.price_score.score if enriched.price_score else None,
            needs_expert_review=(
                enriched.legal_score.needs_expert_review
                if enriched.legal_score else False
            ),
        )

        return enriched

    def _run_registry_analysis(self, enriched: EnrichedCase) -> None:
        """2단 등기부 분석. 실패해도 1단 결과 유지 (fail-open)."""
        assert self._registry_pipeline is not None

        case = enriched.case
        case_id = case.case_number

        try:
            # 1. 주소 파싱 → CODEF 파라미터
            lot_number = ""
            building_name = ""
            if case.property_objects:
                lot_number = case.property_objects[0].lot_number
                building_name = case.property_objects[0].building_name

            params = extract_codef_params(
                address=case.address,
                lot_number=lot_number,
                building_name=building_name,
            )

            # 2. CODEF 주소 검색
            search_results = self._registry_pipeline._provider.search_by_address(
                sido=params.sido,
                sigungu=params.sigungu,
                addr_dong=params.dong,
                addr_lot_number=params.lot_number,
                building_name=params.building_name,
                address=params.address_text,
                addr_road_name=params.road_name,
                addr_building_number=params.building_number,
            )

            if not search_results:
                enriched.registry_error = "CODEF 검색 결과 없음"
                logger.warning("2단: CODEF 검색 결과 없음 [%s]", case_id)
                return

            # 3. 매칭 — 정확한 물건 특정
            match = self._matcher.match(search_results, params)

            # 4. 등기부 조회 + 분석
            reg_result = self._registry_pipeline.analyze_by_unique_no(
                unique_no=match.unique_no,
                addr_sido=params.sido,
                addr_sigungu=params.sigungu,
                addr_dong=params.dong,
                addr_lot_number=params.lot_number,
                addr_road_name=params.road_name,
                addr_building_number=params.building_number,
            )

            # 5. 결과 기록
            enriched.registry_analysis = reg_result.analysis
            enriched.registry_unique_no = match.unique_no
            enriched.registry_match_confidence = match.confidence

            # 6. 법률 리스크 점수 산출
            from app.services.rules.legal_scorer import LegalScorer
            legal_scorer = LegalScorer()
            enriched.legal_score = legal_scorer.score(
                case=enriched.case,
                registry_analysis=enriched.registry_analysis,
            )

            logger.info(
                "2단 완료 [%s]: unique_no=%s, hard_stop=%s, match=%s(%.1f), legal_score=%.1f",
                case_id, match.unique_no, reg_result.has_hard_stop,
                match.match_method, match.confidence,
                enriched.legal_score.score,
            )

        except AddressParseError as e:
            enriched.registry_error = f"주소 파싱 실패: {e}"
            logger.warning("2단: 주소 파싱 실패 [%s]: %s", case_id, e)

        except NoMatchError as e:
            enriched.registry_error = f"고유번호 매칭 실패: {e}"
            logger.warning("2단: 매칭 실패 [%s]: %s", case_id, e)

        except Exception as e:
            enriched.registry_error = f"2단 분석 실패: {e}"
            logger.warning("2단: 분석 실패 [%s]: %s", case_id, e)
