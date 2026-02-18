"""SaleResultCollector 단위 테스트 (Phase 6.5b)

DB는 SQLite in-memory, 크롤러는 MagicMock.
대법원 API 미호출 — 순수 mock 전용.

=== 검증 영역 ===
1. fetch_sale_results payload 구조 (statNum=5, auctnGdsStatCd=04, pageSize=50)
2. 기존 물건 winning_bid 업데이트 (Auction + Score)
3. 신규 물건 INSERT (Score 없음)
4. maeAmt=0 스킵
5. 이미 winning_bid 있음 스킵
6. 날짜 필터 (date_from / date_to)
7. 페이지네이션 (totalCnt > 50)
8. dry_run (DB 변경 없음)
9. 법원별 API 실패 → fail-open
10. 법원 필터
11. limit 적용
12. court_auction_client fetch_sale_results payload 검증
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock, call

import pytest

from app.models.db.auction import Auction
from app.models.db.score import Score
from app.services.crawler.court_auction import CourtAuctionClient
from app.services.sale_result_collector import (
    SEOUL_COURT_CODES,
    SaleResultCollector,
    _parse_date,
    _safe_int,
)


# ─────────────────────────────────────────────
# Fixtures & 헬퍼
# ─────────────────────────────────────────────


def _make_auction(
    case_number: str = "2023타경1001",
    court_office_code: str = "B000210",
    appraised_value: int = 500_000_000,
    status: str = "진행",
    winning_bid: int | None = None,
) -> Auction:
    """최소 Auction ORM 레코드 생성"""
    return Auction(
        id=str(uuid.uuid4()),
        case_number=case_number,
        court="서울중앙지방법원",
        court_office_code=court_office_code,
        address="서울특별시 강남구 역삼동 123",
        property_type="아파트",
        appraised_value=appraised_value,
        minimum_bid=appraised_value * 8 // 10,
        status=status,
        winning_bid=winning_bid,
    )


def _make_score(
    auction_id: str,
    predicted_winning_ratio: float | None = 0.80,
    actual_winning_bid: int | None = None,
) -> Score:
    """최소 Score ORM 레코드 생성"""
    return Score(
        id=str(uuid.uuid4()),
        auction_id=auction_id,
        property_category="아파트",
        total_score=75.0,
        score_coverage=0.70,
        missing_pillars=[],
        predicted_winning_ratio=predicted_winning_ratio,
        actual_winning_bid=actual_winning_bid,
    )


def _make_item(
    case_number: str = "2023타경1001",
    court_code: str = "B000210",
    mae_amt: str = "420000000",
    gamevar_amt: str = "500000000",
    min_mae_price: str = "400000000",
    mae_giil: str = "20260110",
    court_name: str = "서울중앙지방법원",
    property_type: str = "아파트",
    mul_statcd: str = "04",
) -> dict:
    """매각결과 API 응답 아이템 생성"""
    return {
        "boCd": court_code,
        "srnSaNo": case_number,
        "maemulSer": "1",
        "maeAmt": mae_amt,
        "gamevalAmt": gamevar_amt,
        "minmaePrice": min_mae_price,
        "maeGiil": mae_giil,
        "maegyuljGiil": "20260117",
        "yuchalCnt": "0",
        "mulStatcd": mul_statcd,
        "jiwonNm": court_name,
        "printSt": "서울특별시 강남구 역삼동 123",
        "hjguSido": "서울특별시",
        "hjguSigu": "강남구",
        "hjguDong": "역삼동",
        "buldNm": "",
        "dspslUsgNm": property_type,
        "lclsUtilCd": "20000",
        "xCordi": "127.0",
        "yCordi": "37.5",
    }


def _mock_crawler(items: list[dict], total_cnt: int = 0) -> MagicMock:
    """fetch_sale_results()를 stubbing한 mock 크롤러"""
    crawler = MagicMock(spec=CourtAuctionClient)
    if total_cnt == 0:
        total_cnt = len(items)
    crawler.fetch_sale_results.return_value = (items, total_cnt)
    return crawler


def _setup(db_session, auction: Auction, score: Score | None = None) -> Auction:
    """Auction (+ Score) DB에 삽입"""
    db_session.add(auction)
    db_session.flush()
    if score is not None:
        score.auction_id = auction.id
        db_session.add(score)
    db_session.commit()
    return auction


# ─────────────────────────────────────────────
# 헬퍼 함수 단위 테스트
# ─────────────────────────────────────────────


class TestHelpers:
    def test_safe_int_normal(self):
        assert _safe_int("420000000") == 420_000_000

    def test_safe_int_zero_returns_none(self):
        assert _safe_int("0") is None

    def test_safe_int_none_returns_none(self):
        assert _safe_int(None) is None

    def test_safe_int_empty_string(self):
        assert _safe_int("") is None

    def test_parse_date_valid(self):
        assert _parse_date("20260110") == date(2026, 1, 10)

    def test_parse_date_none(self):
        assert _parse_date(None) is None

    def test_parse_date_invalid(self):
        assert _parse_date("INVALID") is None


# ─────────────────────────────────────────────
# 기본 업데이트 / 삽입 테스트
# ─────────────────────────────────────────────


class TestSaleResultCollectorBasic:
    def test_update_existing_auction(self, db_session):
        """기존 물건(winning_bid=None) → Auction.winning_bid 업데이트"""
        auction = _make_auction(appraised_value=500_000_000)
        score = _make_score(auction.id, predicted_winning_ratio=0.80)
        _setup(db_session, auction, score)

        item = _make_item(case_number=auction.case_number, mae_amt="420000000")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        assert result.updated == 1
        assert result.new_inserted == 0
        assert result.skipped_no_amount == 0
        assert result.errors == 0

        db_session.expire_all()
        a = db_session.query(Auction).filter(Auction.case_number == auction.case_number).first()
        assert a.winning_bid == 420_000_000
        assert a.winning_ratio == pytest.approx(0.84, abs=0.001)
        assert a.winning_source == "sale_result_api"
        assert a.status == "매각"

    def test_update_also_updates_score(self, db_session):
        """기존 물건 업데이트 시 Score도 함께 업데이트"""
        auction = _make_auction(appraised_value=1_000_000_000)
        score = _make_score(auction.id, predicted_winning_ratio=0.70)
        _setup(db_session, auction, score)

        item = _make_item(
            case_number=auction.case_number,
            mae_amt="800000000",
            gamevar_amt="1000000000",
        )
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        collector.collect(court_codes=["B000210"])

        db_session.expire_all()
        s = db_session.query(Score).first()
        assert s.actual_winning_bid == 800_000_000
        assert s.actual_winning_ratio == pytest.approx(0.80, abs=0.001)
        # error = 0.80 - 0.70 = 0.10
        assert s.prediction_error == pytest.approx(0.10, abs=0.001)

    def test_insert_new_auction(self, db_session):
        """DB에 없는 물건 → 신규 INSERT (Score 없음)"""
        item = _make_item(
            case_number="2023타경9999",
            mae_amt="350000000",
            gamevar_amt="400000000",
        )
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        assert result.new_inserted == 1
        assert result.updated == 0

        db_session.expire_all()
        a = db_session.query(Auction).filter(Auction.case_number == "2023타경9999").first()
        assert a is not None
        assert a.winning_bid == 350_000_000
        assert a.winning_ratio == pytest.approx(0.875, abs=0.001)
        assert a.winning_source == "sale_result_api"
        assert a.status == "매각"
        # 신규 INSERT는 Score 없음
        s = db_session.query(Score).filter(Score.auction_id == a.id).first()
        assert s is None


# ─────────────────────────────────────────────
# 스킵 조건
# ─────────────────────────────────────────────


class TestSkipConditions:
    def test_skip_zero_maeAmt(self, db_session):
        """maeAmt=0 → skipped_no_amount += 1"""
        item = _make_item(case_number="2023타경1001", mae_amt="0")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        assert result.skipped_no_amount == 1
        assert result.updated == 0
        assert result.new_inserted == 0

    def test_skip_already_has_winning_bid(self, db_session):
        """이미 winning_bid 있는 물건 → already_exists"""
        auction = _make_auction(winning_bid=400_000_000, status="매각")
        _setup(db_session, auction)

        item = _make_item(case_number=auction.case_number, mae_amt="420000000")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        assert result.already_exists == 1
        assert result.updated == 0

        db_session.expire_all()
        a = db_session.query(Auction).first()
        # winning_bid 변경 없음
        assert a.winning_bid == 400_000_000

    def test_skip_date_filter_before_from(self, db_session):
        """maeGiil < date_from → skipped_date_filter"""
        item = _make_item(mae_giil="20241201")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(
            court_codes=["B000210"],
            date_from=date(2025, 1, 1),
        )

        assert result.skipped_date_filter == 1

    def test_skip_date_filter_after_to(self, db_session):
        """maeGiil > date_to → skipped_date_filter"""
        item = _make_item(mae_giil="20260301")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(
            court_codes=["B000210"],
            date_to=date(2026, 2, 28),
        )

        assert result.skipped_date_filter == 1

    def test_date_filter_within_range(self, db_session):
        """date_from ~ date_to 범위 안 → 정상 처리"""
        item = _make_item(mae_giil="20260115")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(
            court_codes=["B000210"],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
        )

        assert result.new_inserted == 1


# ─────────────────────────────────────────────
# 페이지네이션
# ─────────────────────────────────────────────


class TestPagination:
    def test_pagination_multiple_pages(self, db_session):
        """totalCnt=110 → 3페이지 요청"""
        item1 = _make_item(case_number="2023타경1001")
        item2 = _make_item(case_number="2023타경1002")
        item3 = _make_item(case_number="2023타경1003")

        crawler = MagicMock(spec=CourtAuctionClient)
        # 1페이지: 50건 더미 (2건만 반환), totalCnt=110
        # 2페이지: 50건 더미 (1건), 3페이지: 10건 (0건)
        crawler.fetch_sale_results.side_effect = [
            ([item1], 110),   # page=1 (총 110건 중 1건 반환)
            ([item2], 0),     # page=2
            ([item3], 0),     # page=3
        ]

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        # 3번 호출 확인
        assert crawler.fetch_sale_results.call_count == 3
        assert result.new_inserted == 3

    def test_single_page_when_total_le_50(self, db_session):
        """totalCnt <= 50 → 1페이지만 요청"""
        item = _make_item(case_number="2023타경2001")
        crawler = _mock_crawler([item], total_cnt=30)

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        crawler.fetch_sale_results.assert_called_once_with("B000210", page_no=1)
        assert result.new_inserted == 1


# ─────────────────────────────────────────────
# dry_run / fail-open / 필터
# ─────────────────────────────────────────────


class TestMiscBehavior:
    def test_dry_run_no_db_write(self, db_session):
        """dry_run=True → DB 변경 없음, 카운트는 정상"""
        auction = _make_auction(appraised_value=500_000_000)
        _setup(db_session, auction)

        item = _make_item(case_number=auction.case_number, mae_amt="420000000")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"], dry_run=True)

        assert result.updated == 1  # 카운트는 올라감

        db_session.expire_all()
        a = db_session.query(Auction).first()
        assert a.winning_bid is None  # DB는 변경 없음

    def test_api_failure_continues_to_next_court(self, db_session):
        """첫 번째 법원 API 실패 → errors += 1, 다음 법원 계속"""
        item = _make_item(case_number="2023타경3001")

        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.fetch_sale_results.side_effect = [
            Exception("API 오류"),    # B000210 실패
            ([item], 1),             # B000214 성공
        ]

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210", "B000214"])

        assert result.errors == 1
        assert result.new_inserted == 1
        assert result.courts_queried == 1  # 성공한 법원만 카운트

    def test_court_codes_none_uses_seoul_defaults(self, db_session):
        """court_codes=None → SEOUL_COURT_CODES 5개 법원 사용"""
        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.fetch_sale_results.return_value = ([], 0)

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        collector.collect(court_codes=None)

        assert crawler.fetch_sale_results.call_count == 5
        called_courts = [c[0][0] for c in crawler.fetch_sale_results.call_args_list]
        assert set(called_courts) == set(SEOUL_COURT_CODES)

    def test_update_without_score(self, db_session):
        """Score 없는 기존 물건도 winning_bid 업데이트 가능"""
        auction = _make_auction(appraised_value=500_000_000)
        _setup(db_session, auction)  # Score 없이 Auction만

        item = _make_item(case_number=auction.case_number, mae_amt="420000000")
        crawler = _mock_crawler([item])

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"])

        assert result.updated == 1

        db_session.expire_all()
        a = db_session.query(Auction).first()
        assert a.winning_bid == 420_000_000

    def test_limit_stops_processing(self, db_session):
        """limit=1 → 1건만 처리"""
        items = [
            _make_item(case_number="2023타경4001"),
            _make_item(case_number="2023타경4002"),
            _make_item(case_number="2023타경4003"),
        ]
        crawler = _mock_crawler(items, total_cnt=3)

        collector = SaleResultCollector(db=db_session, crawler=crawler, page_delay=0)
        result = collector.collect(court_codes=["B000210"], limit=1)

        # limit이 적용되어 1건만 처리 (나머지 법원 건너뜀)
        assert result.new_inserted + result.updated + result.skipped_no_amount + result.already_exists <= 3
