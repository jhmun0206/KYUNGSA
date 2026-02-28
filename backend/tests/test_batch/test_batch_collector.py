"""BatchCollector 단위 테스트

크롤러/보강기는 MagicMock, DB는 SQLite in-memory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.auction import AuctionCaseDetail, AuctionCaseListItem
from app.models.db.auction import Auction
from app.models.db.filter_result import FilterResultORM
from app.models.db.pipeline_run import PipelineRun
from app.models.db.score import Score
from app.models.enriched_case import (
    EnrichedCase,
    FilterColor,
    FilterResult,
)
from app.services.batch_collector import BatchCollector, BatchResult
from app.services.crawler.court_auction import CourtAuctionClient


# --- 테스트 헬퍼 ---


def _make_list_item(
    case_number: str = "2026타경10001",
    internal: str = "20260130010001",
) -> AuctionCaseListItem:
    return AuctionCaseListItem(
        case_number=case_number,
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123-4",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
        court_office_code="B000210",
        internal_case_number=internal,
        property_sequence="1",
    )


def _make_detail(case_number: str = "2026타경10001") -> AuctionCaseDetail:
    return AuctionCaseDetail(
        case_number=case_number,
        court="서울중앙지방법원",
        court_office_code="B000210",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123-4",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
    )


def _make_enriched(case_number: str = "2026타경10001") -> EnrichedCase:
    return EnrichedCase(case=_make_detail(case_number))


def _setup_mocks(
    items: list[AuctionCaseListItem] | None = None,
    total: int = 0,
) -> tuple[MagicMock, MagicMock]:
    """mock crawler + enricher 생성"""
    if items is None:
        items = [_make_list_item()]
        total = 1

    crawler = MagicMock(spec=CourtAuctionClient)
    crawler.search_cases_with_total.return_value = (items, total)
    crawler.fetch_case_detail.side_effect = lambda case_number, **kw: _make_detail(
        # case_number는 internal_case_number가 전달됨
        # 실제로는 detail에서 case_number가 원래 값으로 돌아옴
        next(
            (i.case_number for i in items if i.internal_case_number == case_number),
            case_number,
        )
    )

    enricher = MagicMock()
    enricher.enrich.side_effect = lambda detail: EnrichedCase(case=detail)

    return crawler, enricher


# === 테스트 ===


class TestCollectBasic:
    """기본 수집 흐름"""

    def test_collect_single_item(self, db_session):
        """1건 수집 → DB 저장 확인"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", enrich_delay=0)

        assert result.total_searched == 1
        assert result.processed == 1
        assert result.new_count == 1
        assert result.green_count + result.yellow_count + result.red_count == 1
        assert len(result.errors) == 0

        # DB 확인
        auction = db_session.query(Auction).first()
        assert auction is not None
        assert auction.case_number == "2026타경10001"

    def test_collect_multiple_items(self, db_session):
        """3건 수집"""
        items = [
            _make_list_item(f"2026타경1000{i}", f"2026013001000{i}")
            for i in range(1, 4)
        ]
        crawler, enricher = _setup_mocks(items, total=3)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", enrich_delay=0)

        assert result.processed == 3
        assert result.new_count == 3
        assert db_session.query(Auction).count() == 3

    def test_filter_result_saved(self, db_session):
        """필터 결과가 DB에 저장되는지 확인"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        collector.collect("B000210", enrich_delay=0)

        fr = db_session.query(FilterResultORM).first()
        assert fr is not None
        assert fr.color in ("RED", "YELLOW", "GREEN")


class TestSkipExisting:
    """skip-existing 동작"""

    def test_skip_existing_case(self, db_session):
        """DB에 이미 있으면 스킵"""
        # 먼저 1건 저장
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)
        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        collector.collect("B000210", enrich_delay=0)

        # 같은 건으로 다시 수집 시도
        crawler2, enricher2 = _setup_mocks(items, total=1)
        collector2 = BatchCollector(
            db=db_session, crawler=crawler2, enricher=enricher2,
        )
        result = collector2.collect("B000210", enrich_delay=0)

        assert result.skipped == 1
        assert result.processed == 0
        assert result.new_count == 0


class TestForceUpdate:
    """force_update 동작"""

    def test_force_update_overwrites(self, db_session):
        """force=True면 기존 건 업데이트"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)
        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        collector.collect("B000210", enrich_delay=0)

        # force로 다시 수집
        crawler2, enricher2 = _setup_mocks(items, total=1)
        collector2 = BatchCollector(
            db=db_session, crawler=crawler2, enricher=enricher2,
        )
        result = collector2.collect(
            "B000210", force_update=True, enrich_delay=0,
        )

        assert result.skipped == 0
        assert result.processed == 1
        assert result.updated_count == 1
        # DB에 1건만 존재 (upsert)
        assert db_session.query(Auction).count() == 1


class TestPagination:
    """다중 페이지 순회"""

    def test_multi_page_collection(self, db_session):
        """total=5, page_size=2 → 3페이지 순회"""
        page1_items = [
            _make_list_item("2026타경10001", "20260130010001"),
            _make_list_item("2026타경10002", "20260130010002"),
        ]
        page2_items = [
            _make_list_item("2026타경10003", "20260130010003"),
            _make_list_item("2026타경10004", "20260130010004"),
        ]
        page3_items = [
            _make_list_item("2026타경10005", "20260130010005"),
        ]

        crawler = MagicMock(spec=CourtAuctionClient)
        # 페이지별 다른 응답
        crawler.search_cases_with_total.side_effect = [
            (page1_items, 5),
            (page2_items, 5),
            (page3_items, 5),
        ]
        crawler.fetch_case_detail.side_effect = lambda case_number, **kw: _make_detail(
            # internal → case_number 매핑
            {
                "20260130010001": "2026타경10001",
                "20260130010002": "2026타경10002",
                "20260130010003": "2026타경10003",
                "20260130010004": "2026타경10004",
                "20260130010005": "2026타경10005",
            }.get(case_number, case_number)
        )

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda detail: EnrichedCase(case=detail)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )

        # PAGE_SIZE를 패치하여 작은 값으로 테스트
        with patch("app.services.batch_collector.PAGE_SIZE", 2):
            result = collector.collect("B000210", enrich_delay=0)

        assert result.total_searched == 5
        assert result.total_pages == 3
        assert result.processed == 5
        assert db_session.query(Auction).count() == 5


class TestPerCaseCommit:
    """건별 DB 저장 확인"""

    def test_items_saved_incrementally(self, db_session):
        """각 건이 개별적으로 커밋되는지 확인"""
        items = [
            _make_list_item(f"2026타경1000{i}", f"2026013001000{i}")
            for i in range(1, 4)
        ]
        crawler, enricher = _setup_mocks(items, total=3)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        collector.collect("B000210", enrich_delay=0)

        # 3건 모두 저장됨
        assert db_session.query(Auction).count() == 3


class TestPipelineRunTracking:
    """PipelineRun RUNNING→COMPLETED 전이"""

    def test_pipeline_run_created_and_completed(self, db_session):
        """PipelineRun이 RUNNING→COMPLETED으로 전이"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", enrich_delay=0)

        run = db_session.query(PipelineRun).first()
        assert run is not None
        assert run.run_id == result.run_id
        assert run.status == "COMPLETED"
        assert run.total_searched == 1
        assert run.finished_at is not None


class TestErrorResilience:
    """에러 복원력"""

    def test_continue_after_detail_failure(self, db_session):
        """상세조회 실패해도 다른 건은 계속 처리"""
        items = [
            _make_list_item("2026타경10001", "20260130010001"),
            _make_list_item("2026타경10002", "20260130010002"),
            _make_list_item("2026타경10003", "20260130010003"),
        ]

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.search_cases_with_total.return_value = (items, 3)

        # 2번째 건만 실패
        def fetch_detail_side_effect(case_number, **kw):
            mapping = {
                "20260130010001": "2026타경10001",
                "20260130010002": "2026타경10002",
                "20260130010003": "2026타경10003",
            }
            if case_number == "20260130010002":
                raise Exception("상세조회 타임아웃")
            return _make_detail(mapping.get(case_number, case_number))

        crawler.fetch_case_detail.side_effect = fetch_detail_side_effect

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda detail: EnrichedCase(case=detail)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", enrich_delay=0)

        assert len(result.errors) == 1
        assert "2026타경10002" in result.errors[0]
        # 나머지 2건은 저장됨
        assert db_session.query(Auction).count() == 2


class TestSearchWithTotal:
    """search_cases_with_total + parser"""

    def test_parse_list_with_total(self):
        """parse_list_with_total이 (items, total) 반환"""
        from app.services.crawler.court_auction_parser import CourtAuctionParser

        parser = CourtAuctionParser()
        response_data = {
            "dlt_srchResult": [],
            "dma_pageInfo": {"totalCnt": "42"},
        }
        items, total = parser.parse_list_with_total(response_data)
        assert items == []
        assert total == 42

    def test_parse_total_fallback(self):
        """totalCnt 파싱 실패 시 items 길이 fallback"""
        from app.services.crawler.court_auction_parser import CourtAuctionParser

        parser = CourtAuctionParser()
        response_data = {
            "dlt_srchResult": [],
            "dma_pageInfo": {"totalCnt": "invalid"},
        }
        items, total = parser.parse_list_with_total(response_data)
        assert total == 0  # len(items) == 0


class TestDryRun:
    """dry-run 모드"""

    def test_dry_run_no_db_save(self, db_session):
        """dry_run=True면 DB에 아무것도 저장 안 됨"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", dry_run=True, enrich_delay=0)

        assert result.processed == 1
        assert db_session.query(Auction).count() == 0
        assert db_session.query(PipelineRun).count() == 0


class TestMaxItems:
    """max_items 제한"""

    def test_max_items_limit(self, db_session):
        """max_items=2면 2건만 처리"""
        items = [
            _make_list_item(f"2026타경1000{i}", f"2026013001000{i}")
            for i in range(1, 6)
        ]
        crawler, enricher = _setup_mocks(items, total=5)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", max_items=2, enrich_delay=0)

        assert result.processed <= 2
        assert db_session.query(Auction).count() <= 2


class TestPropertyTypeFallback:
    """property_type fallback: 상세 API에 없으면 리스트 값 사용"""

    def test_fallback_from_list_item(self, db_session):
        """상세 API가 property_type=""이면 리스트 아이템 값으로 대체"""
        item = _make_list_item()  # property_type="아파트"

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.search_cases_with_total.return_value = ([item], 1)
        # 상세 API는 property_type이 빈 문자열
        detail = _make_detail()
        detail.property_type = ""
        crawler.fetch_case_detail.return_value = detail

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda d: EnrichedCase(case=d)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        collector.collect("B000210", enrich_delay=0)

        auction = db_session.query(Auction).first()
        assert auction is not None
        assert auction.property_type == "아파트"

    def test_detail_value_preserved(self, db_session):
        """상세 API에 이미 property_type이 있으면 그 값 유지"""
        item = _make_list_item()  # property_type="아파트"

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.search_cases_with_total.return_value = ([item], 1)
        # 상세 API가 자체 값을 갖고 있음
        detail = _make_detail()
        detail.property_type = "다세대"
        crawler.fetch_case_detail.return_value = detail

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda d: EnrichedCase(case=d)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        collector.collect("B000210", enrich_delay=0)

        auction = db_session.query(Auction).first()
        assert auction is not None
        assert auction.property_type == "다세대"


class TestDuplicateCaseNumber:
    """같은 case_number, 다른 property_sequence 중복 방지"""

    def test_same_case_different_seq_processed_once(self, db_session):
        """같은 사건번호의 물건순서 1,2,3 → 1건만 처리"""
        items = [
            AuctionCaseListItem(
                case_number="2026타경10001",
                court="서울중앙지방법원",
                property_type="아파트",
                address="서울특별시 강남구 역삼동 123-4",
                appraised_value=500_000_000,
                minimum_bid=400_000_000,
                court_office_code="B000210",
                internal_case_number="20260130010001",
                property_sequence=str(seq),
            )
            for seq in range(1, 4)
        ]

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.search_cases_with_total.return_value = (items, 3)
        crawler.fetch_case_detail.return_value = _make_detail("2026타경10001")

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda d: EnrichedCase(case=d)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", enrich_delay=0)

        assert result.processed == 1
        assert result.skipped == 2
        assert db_session.query(Auction).count() == 1
        # fetch_case_detail은 1번만 호출
        assert crawler.fetch_case_detail.call_count == 1

    def test_force_mode_dedup(self, db_session):
        """--force 모드에서도 같은 사건번호 중복 처리 안 함"""
        items = [
            AuctionCaseListItem(
                case_number="2026타경10001",
                court="서울중앙지방법원",
                property_type="아파트",
                address="서울특별시 강남구 역삼동 123-4",
                appraised_value=500_000_000,
                minimum_bid=400_000_000,
                court_office_code="B000210",
                internal_case_number="20260130010001",
                property_sequence=str(seq),
            )
            for seq in range(1, 3)
        ]

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.search_cases_with_total.return_value = (items, 2)
        crawler.fetch_case_detail.return_value = _make_detail("2026타경10001")

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda d: EnrichedCase(case=d)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", force_update=True, enrich_delay=0)

        assert result.processed == 1
        assert result.skipped == 1
        assert crawler.fetch_case_detail.call_count == 1

    def test_different_cases_all_processed(self, db_session):
        """다른 사건번호는 모두 정상 처리"""
        items = [
            _make_list_item(f"2026타경1000{i}", f"2026013001000{i}")
            for i in range(1, 4)
        ]
        crawler, enricher = _setup_mocks(items, total=3)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", force_update=True, enrich_delay=0)

        assert result.processed == 3
        assert result.skipped == 0


class TestSkipOccupancy:
    """skip_occupancy 옵션"""

    def test_skip_occupancy_no_fetch(self, db_session):
        """skip_occupancy=True면 현황조사서 조회 안 함"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect(
            "B000210", skip_occupancy=True, enrich_delay=0,
        )

        assert result.processed == 1
        # fetch_occupancy_report는 호출되지 않아야 함
        crawler.fetch_occupancy_report.assert_not_called()

    def test_no_skip_occupancy_fetches(self, db_session):
        """skip_occupancy=False(기본)면 현황조사서 조회 시도"""
        items = [_make_list_item()]
        crawler, enricher = _setup_mocks(items, total=1)

        collector = BatchCollector(
            db=db_session, crawler=crawler, enricher=enricher,
        )
        result = collector.collect("B000210", enrich_delay=0)

        assert result.processed == 1
        # fetch_occupancy_report가 호출되어야 함
        crawler.fetch_occupancy_report.assert_called_once()


# --- DB 재채점 테스트 헬퍼 ---


def _insert_auction(
    db_session,
    case_number: str = "2026타경10001",
    court_office_code: str = "B000210",
) -> Auction:
    """테스트용 Auction ORM 직접 삽입"""
    auction = Auction(
        case_number=case_number,
        court="서울중앙지방법원",
        court_office_code=court_office_code,
        address="서울특별시 강남구 역삼동 123-4",
        property_type="아파트",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
        detail={
            "case_number": case_number,
            "court": "서울중앙지방법원",
            "court_office_code": court_office_code,
            "property_type": "아파트",
            "address": "서울특별시 강남구 역삼동 123-4",
            "appraised_value": 500_000_000,
            "minimum_bid": 400_000_000,
            "internal_case_number": "20260130010001",
        },
    )
    db_session.add(auction)
    db_session.flush()
    return auction


def _insert_score(db_session, auction_id: str, coverage: float = 0.20) -> Score:
    """테스트용 Score ORM 직접 삽입"""
    score = Score(
        auction_id=auction_id,
        score_coverage=coverage,
        total_score=50.0,
        property_category="아파트",
    )
    db_session.add(score)
    db_session.flush()
    return score


class TestRescoreDb:
    """DB 기반 재채점 모드"""

    def _make_collector(self, db_session) -> tuple[BatchCollector, MagicMock, MagicMock]:
        """재채점 전용 컬렉터 — fetch_case_detail 성공 mock"""
        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.fetch_case_detail.return_value = _make_detail()

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda detail: EnrichedCase(case=detail)

        collector = BatchCollector(db=db_session, crawler=crawler, enricher=enricher)
        return collector, crawler, enricher

    def test_rescore_basic(self, db_session):
        """DB에서 물건 로드 → 재채점 후 Score 업데이트"""
        auction = _insert_auction(db_session, "2026타경10001")
        _insert_score(db_session, auction.id, coverage=0.20)
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            coverage_below=0.30, enrich_delay=0, skip_occupancy=True,
        )

        assert result.total_searched == 1
        assert result.processed == 1
        assert result.updated_count == 1
        assert len(result.errors) == 0

    def test_rescore_coverage_filter(self, db_session):
        """coverage_below 필터: 낮은 coverage만 재채점"""
        a1 = _insert_auction(db_session, "2026타경10001")
        a2 = _insert_auction(db_session, "2026타경10002")
        _insert_score(db_session, a1.id, coverage=0.20)   # 재채점 대상
        _insert_score(db_session, a2.id, coverage=0.80)   # coverage 충분 → 스킵
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            coverage_below=0.30, enrich_delay=0, skip_occupancy=True,
        )

        assert result.total_searched == 1   # a1만 해당
        assert result.processed == 1

    def test_rescore_no_score(self, db_session):
        """Score 없는 물건도 재채점 대상에 포함"""
        _insert_auction(db_session, "2026타경10001")
        # Score 삽입 안 함
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            coverage_below=0.30, enrich_delay=0, skip_occupancy=True,
        )

        assert result.total_searched == 1
        assert result.processed == 1

    def test_rescore_court_filter(self, db_session):
        """court_code 필터: 해당 법원만 처리"""
        a1 = _insert_auction(db_session, "2026타경10001", court_office_code="B000210")
        a2 = _insert_auction(db_session, "2026타경10002", court_office_code="B000211")
        _insert_score(db_session, a1.id, coverage=0.20)
        _insert_score(db_session, a2.id, coverage=0.20)
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            court_code="B000210", coverage_below=0.30,
            enrich_delay=0, skip_occupancy=True,
        )

        assert result.total_searched == 1   # B000210만
        assert result.processed == 1

    def test_rescore_api_failure_fallback(self, db_session):
        """대법원 API 갱신 실패해도 DB 데이터로 재채점 계속 (fail-open)"""
        auction = _insert_auction(db_session, "2026타경10001")
        _insert_score(db_session, auction.id, coverage=0.20)
        db_session.commit()

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.fetch_case_detail.side_effect = Exception("API 연결 실패")

        enricher = MagicMock()
        enricher.enrich.side_effect = lambda detail: EnrichedCase(case=detail)

        collector = BatchCollector(db=db_session, crawler=crawler, enricher=enricher)
        result = collector.rescore_db(
            coverage_below=0.30, enrich_delay=0, skip_occupancy=True,
        )

        # API 실패는 에러가 아님 (fail-open → DB 데이터로 계속)
        assert result.processed == 1
        assert len(result.errors) == 0

    def test_rescore_dry_run(self, db_session):
        """dry_run=True면 Score 업데이트 없음"""
        auction = _insert_auction(db_session, "2026타경10001")
        _insert_score(db_session, auction.id, coverage=0.20)
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            coverage_below=0.30, dry_run=True,
            enrich_delay=0, skip_occupancy=True,
        )

        assert result.processed == 1
        assert result.updated_count == 0   # dry_run이면 업데이트 없음

        # Score는 여전히 원래 coverage 유지
        score = db_session.query(Score).first()
        assert abs(score.score_coverage - 0.20) < 0.01

    def test_rescore_max_items(self, db_session):
        """max_items 제한"""
        for i in range(1, 6):
            a = _insert_auction(db_session, f"2026타경1000{i}")
            _insert_score(db_session, a.id, coverage=0.20)
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            coverage_below=0.30, max_items=3,
            enrich_delay=0, skip_occupancy=True,
        )

        assert result.total_searched == 5   # 전체 대상은 5건
        assert result.processed <= 3        # max_items=3 제한

    def test_rescore_pipeline_run_created(self, db_session):
        """재채점 시 PipelineRun이 RUNNING→COMPLETED으로 전이"""
        auction = _insert_auction(db_session, "2026타경10001")
        _insert_score(db_session, auction.id, coverage=0.20)
        db_session.commit()

        collector, _, _ = self._make_collector(db_session)
        result = collector.rescore_db(
            coverage_below=0.30, enrich_delay=0, skip_occupancy=True,
        )

        run = db_session.query(PipelineRun).first()
        assert run is not None
        assert "RESCORE" in run.run_id
        assert run.status == "COMPLETED"
        assert result.run_id == run.run_id
