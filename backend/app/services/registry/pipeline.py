"""등기부등본 2단 파이프라인 — 주소 → 등기부 조회 → 리스크 분석

CODEF 주소검색 → 등기부 열람 → RegistryDocument → RegistryAnalyzer 를
하나의 호출로 연결한다.

사용:
    provider = CodefRegistryProvider()
    analyzer = RegistryAnalyzer()
    pipeline = RegistryPipeline(provider, analyzer)

    # 주소로 조회
    result = pipeline.analyze_by_address(
        sido="서울특별시", sigungu="강남구",
        addr_dong="삼성동", address="삼성동 아이파크",
        dong="101", ho="101",
    )

    # 고유번호로 직접 조회 (inquiryType=0: addr_* 불필요)
    result = pipeline.analyze_by_unique_no(
        unique_no="11012022002636",
    )
"""

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.registry import RegistryAnalysisResult, RegistryDocument
from app.services.parser.registry_analyzer import RegistryAnalyzer
from app.services.registry.codef_provider import CodefRegistryProvider

logger = logging.getLogger(__name__)


# ── 예외 ──────────────────────────────────────────────────────


class NoRegistryFoundError(Exception):
    """주소 검색 결과가 없을 때 발생"""

    def __init__(self, message: str = "등기부 검색 결과가 없습니다") -> None:
        super().__init__(message)


class RegistryPipelineError(Exception):
    """파이프라인 내부 처리 오류 (mapper/analyzer 단계)"""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        self.cause = cause
        super().__init__(message)


# ── 결과 모델 ─────────────────────────────────────────────────


class RegistryPipelineResult(BaseModel):
    """파이프라인 실행 결과"""

    unique_no: str
    address: str = ""
    registry_document: RegistryDocument
    analysis: RegistryAnalysisResult
    search_results: list[dict] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.now)

    @property
    def has_hard_stop(self) -> bool:
        """치명적 리스크가 있는지"""
        return self.analysis.has_hard_stop

    @property
    def summary(self) -> str:
        """분석 요약 텍스트"""
        return self.analysis.summary


# ── 파이프라인 ────────────────────────────────────────────────


class RegistryPipeline:
    """주소 → 등기부 조회 → 리스크 분석 자동화 파이프라인"""

    def __init__(
        self,
        provider: CodefRegistryProvider,
        analyzer: RegistryAnalyzer | None = None,
    ) -> None:
        self._provider = provider
        self._analyzer = analyzer or RegistryAnalyzer()

    def analyze_by_address(
        self,
        sido: str,
        sigungu: str = "",
        addr_dong: str = "",
        addr_lot_number: str = "",
        building_name: str = "",
        dong: str = "",
        ho: str = "",
        address: str = "",
        realty_type: str = "3",
        addr_road_name: str = "",
        addr_building_number: str = "",
    ) -> RegistryPipelineResult:
        """주소 검색 → 등기부 조회 → 리스크 분석

        1. CODEF 주소검색으로 고유번호 목록 확보
        2. 첫 번째 결과의 고유번호로 등기부 열람
        3. RegistryAnalyzer로 리스크 분석
        4. RegistryPipelineResult 반환

        Args:
            sido: 시/도 (예: "서울특별시")
            sigungu: 시/군/구 (예: "강남구")
            addr_dong: 법정동 (예: "삼성동")
            addr_lot_number: 지번 (예: "123-45")
            building_name: 건물명 (예: "아이파크")
            dong: 건물 동 (예: "101")
            ho: 호 (예: "501")
            address: 검색어 (예: "삼성동 아이파크")
            realty_type: 부동산유형 (1: 토지, 2: 건물, 3: 집합건물)
            addr_road_name: 도로명
            addr_building_number: 건물번호

        Returns:
            RegistryPipelineResult

        Raises:
            NoRegistryFoundError: 검색 결과가 없을 때
            RegistryTwoWayAuthRequired: CODEF 추가인증 필요 시
            CodefApiError: CODEF API 오류 시
            RegistryPipelineError: 매퍼/분석기 내부 오류 시
        """
        # 1. 주소 검색
        logger.info(
            "파이프라인: 주소검색 시작 — %s %s %s",
            sido, addr_dong or sigungu, building_name or address,
        )
        search_results = self._provider.search_by_address(
            sido=sido,
            sigungu=sigungu,
            addr_dong=addr_dong,
            addr_lot_number=addr_lot_number,
            building_name=building_name,
            dong=dong,
            ho=ho,
            address=address,
            realty_type=realty_type,
            addr_road_name=addr_road_name,
            addr_building_number=addr_building_number,
        )

        if not search_results:
            raise NoRegistryFoundError(
                f"주소 검색 결과가 없습니다: {sido} {sigungu} {addr_dong} {address}"
            )

        # 2. 첫 번째 결과 선택
        chosen = search_results[0]
        unique_no = chosen.get("commUniqueNo", "")
        result_address = chosen.get("commAddrLotNumber", "")
        logger.info(
            "파이프라인: 고유번호 %s 선택 (%d건 중 1번째)",
            unique_no, len(search_results),
        )

        # 3. 등기부 조회 + 분석 (inquiryType=0: addr_* 불필요)
        return self._fetch_and_analyze(
            unique_no=unique_no,
            realty_type=realty_type,
            address=result_address,
            search_results=search_results,
        )

    def analyze_by_unique_no(
        self,
        unique_no: str,
        realty_type: str = "3",
        **kwargs: Any,
    ) -> RegistryPipelineResult:
        """고유번호 직접 입력 → 등기부 조회 → 리스크 분석

        주소 검색 단계를 건너뛰고 바로 등기부를 열람한다.
        inquiryType=0 사용으로 addr_* 파라미터 불필요 (kwargs로 받되 무시).

        Args:
            unique_no: 부동산 고유번호 (14자리)
            realty_type: 부동산유형 (1: 토지, 2: 건물, 3: 집합건물)
            **kwargs: 기존 호환용 (addr_sido 등 — fetch_registry에서 무시됨)

        Returns:
            RegistryPipelineResult

        Raises:
            RegistryTwoWayAuthRequired: CODEF 추가인증 필요 시
            CodefApiError: CODEF API 오류 시
            RegistryPipelineError: 매퍼/분석기 내부 오류 시
        """
        logger.info("파이프라인: 고유번호 직접 조회 — %s", unique_no)
        return self._fetch_and_analyze(
            unique_no=unique_no,
            realty_type=realty_type,
        )

    def _fetch_and_analyze(
        self,
        unique_no: str,
        realty_type: str = "3",
        address: str = "",
        search_results: list[dict] | None = None,
    ) -> RegistryPipelineResult:
        """등기부 열람 → 분석 공통 로직

        inquiryType=0 사용: unique_no만으로 열람 (addr_* 불필요)
        """
        # 등기부 열람 (CODEF API 호출, inquiryType=0)
        doc = self._provider.fetch_registry(
            unique_no=unique_no,
            realty_type=realty_type,
        )

        # 주소: 등기부 표제부에서 추출 (fallback: 검색 결과)
        resolved_address = address
        if doc.title and doc.title.address:
            resolved_address = doc.title.address

        # 분석
        try:
            analysis = self._analyzer.analyze(doc)
        except Exception as e:
            raise RegistryPipelineError(
                f"등기부 분석 실패 (unique_no={unique_no}): {e}",
                cause=e,
            ) from e

        logger.info(
            "파이프라인 완료: unique_no=%s, hard_stop=%s, confidence=%s",
            unique_no, analysis.has_hard_stop, analysis.confidence.value,
        )

        return RegistryPipelineResult(
            unique_no=unique_no,
            address=resolved_address,
            registry_document=doc,
            analysis=analysis,
            search_results=search_results or [],
        )
