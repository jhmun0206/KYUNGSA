"""WinningBidCollector 단위 테스트 (Phase 6.5a 재설계)

DB는 SQLite in-memory, 크롤러는 MagicMock.
대법원 API 미호출 — 순수 mock 전용.

=== 변경 요약 (Phase 6.5a 재설계) ===
- 쿼리: WHERE status='매각' → WHERE winning_bid IS NULL
- 업데이트: Score만 → Auction (winning_bid/date/ratio/source + status) + Score
- Score outerjoin: Score 없는 Auction도 처리 가능
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.models.auction import AuctionCaseDetail, AuctionCaseHistory, AuctionDocuments, AuctionRound
from app.models.db.auction import Auction
from app.models.db.score import Score
from app.services.crawler.court_auction import CourtAuctionClient
from app.services.winning_bid_collector import WinningBidCollector


# ─────────────────────────────────────────────
# Fixtures & 헬퍼
# ─────────────────────────────────────────────


def _make_auction(
    case_number: str = "2026타경10001",
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
        winning_bid=winning_bid,  # None이면 수집 대상
        detail={
            "internal_case_number": case_number,
            "court_office_code": court_office_code,
            "property_sequence": "1",
        },
    )


def _make_score(
    auction_id: str,
    predicted_winning_ratio: float | None = 0.85,
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


def _make_detail_with_rounds(
    winning_bid: int | None = 420_000_000,
    has_winning_round: bool = True,
    round_date: date | None = None,
) -> AuctionCaseDetail:
    """AuctionCaseDetail with auction_rounds"""
    rounds = []
    if has_winning_round:
        rounds.append(
            AuctionRound(
                round_number=2,
                minimum_bid=400_000_000,
                result="매각",
                result_code="001",
                winning_bid=winning_bid,
                round_date=round_date,
            )
        )
    else:
        rounds.append(
            AuctionRound(
                round_number=1,
                minimum_bid=500_000_000,
                result="유찰",
                result_code="002",
            )
        )
    return AuctionCaseDetail(
        case_number="2026타경10001",
        court="서울중앙지방법원",
        property_type="아파트",
        address="서울특별시 강남구 역삼동 123",
        appraised_value=500_000_000,
        minimum_bid=400_000_000,
        auction_rounds=rounds,
    )


def _mock_crawler(detail: AuctionCaseDetail) -> MagicMock:
    """collect_full_case()를 stubbing한 mock 크롤러"""
    crawler = MagicMock(spec=CourtAuctionClient)
    crawler.collect_full_case.return_value = (
        detail,
        AuctionCaseHistory(case_number="2026타경10001", court="서울중앙지방법원", auction_rounds=[]),
        AuctionDocuments(case_number="2026타경10001"),
    )
    return crawler


def _setup(db_session, auction: Auction, score: Score | None = None):
    """Auction (+ Score) DB에 삽입"""
    db_session.add(auction)
    db_session.flush()
    if score is not None:
        score.auction_id = auction.id
        db_session.add(score)
    db_session.commit()


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────


class TestWinningBidCollectorBasic:
    def test_basic_update(self, db_session):
        """낙찰 물건 1건 → Auction.winning_bid + Score.actual_winning_bid 모두 업데이트"""
        auction = _make_auction(appraised_value=500_000_000, status="진행")
        score = _make_score(auction.id, predicted_winning_ratio=0.80)
        _setup(db_session, auction, score)

        detail = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        assert result.total_queried == 1
        assert result.updated == 1
        assert result.skipped == 0
        assert result.errors == 0

        db_session.expire_all()
        auction_row = db_session.query(Auction).first()
        score_row = db_session.query(Score).first()

        # Auction 업데이트 검증
        assert auction_row.winning_bid == 420_000_000
        assert auction_row.winning_ratio == pytest.approx(0.84, abs=0.001)
        assert auction_row.winning_source == "court_api"
        assert auction_row.status == "매각"

        # Score 업데이트 검증
        assert score_row.actual_winning_bid == 420_000_000
        assert score_row.actual_winning_ratio == pytest.approx(0.84, abs=0.001)
        # prediction_error = 0.84 - 0.80
        assert score_row.prediction_error == pytest.approx(0.04, abs=0.001)

    def test_skip_no_winning_round(self, db_session):
        """auction_rounds에 result='매각' 없음 → skipped += 1"""
        auction = _make_auction()
        score = _make_score(auction.id)
        _setup(db_session, auction, score)

        detail = _make_detail_with_rounds(has_winning_round=False)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        assert result.updated == 0
        assert result.skipped == 1

    def test_skip_winning_bid_none(self, db_session):
        """winning_bid=None → skipped += 1"""
        auction = _make_auction()
        score = _make_score(auction.id)
        _setup(db_session, auction, score)

        detail = _make_detail_with_rounds(winning_bid=None)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        assert result.updated == 0
        assert result.skipped == 1

    def test_skip_appraised_value_zero(self, db_session):
        """appraised_value=0 → skipped (division-by-zero 방지)"""
        auction = _make_auction(appraised_value=0)
        score = _make_score(auction.id)
        _setup(db_session, auction, score)

        detail = _make_detail_with_rounds(winning_bid=400_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        assert result.updated == 0
        assert result.skipped == 1


class TestPredictionError:
    def test_prediction_error_computed_correctly(self, db_session):
        """predicted_winning_ratio 있을 때 prediction_error = ratio - predicted"""
        auction = _make_auction(appraised_value=1_000_000_000)
        score = _make_score(auction.id, predicted_winning_ratio=0.70)
        _setup(db_session, auction, score)

        # winning_bid=800_000_000 → ratio=0.80
        detail = _make_detail_with_rounds(winning_bid=800_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        collector.collect()

        db_session.expire_all()
        score_row = db_session.query(Score).first()
        assert score_row.actual_winning_ratio == pytest.approx(0.80, abs=0.001)
        # error = 0.80 - 0.70 = 0.10
        assert score_row.prediction_error == pytest.approx(0.10, abs=0.001)

    def test_prediction_error_none_when_no_prediction(self, db_session):
        """predicted_winning_ratio=None → prediction_error는 None"""
        auction = _make_auction(appraised_value=500_000_000)
        score = _make_score(auction.id, predicted_winning_ratio=None)
        _setup(db_session, auction, score)

        detail = _make_detail_with_rounds(winning_bid=400_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        collector.collect()

        db_session.expire_all()
        score_row = db_session.query(Score).first()
        assert score_row.actual_winning_bid == 400_000_000
        assert score_row.prediction_error is None


class TestFailOpen:
    def test_api_failure_continues_to_next(self, db_session):
        """collect_full_case 예외 → errors += 1, 다음 건 계속 진행"""
        # 2건 삽입
        a1 = _make_auction(case_number="2026타경10001")
        s1 = _make_score(a1.id)
        _setup(db_session, a1, s1)

        a2 = _make_auction(case_number="2026타경10002")
        a2.id = str(uuid.uuid4())
        s2 = _make_score(a2.id)
        s2.auction_id = a2.id
        db_session.add(a2)
        db_session.flush()
        db_session.add(s2)
        db_session.commit()

        # 1번째 API 실패, 2번째 성공
        detail_ok = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = MagicMock(spec=CourtAuctionClient)
        crawler.collect_full_case.side_effect = [
            Exception("API 오류"),
            (
                detail_ok,
                AuctionCaseHistory(case_number="2026타경10002", court="서울중앙지방법원", auction_rounds=[]),
                AuctionDocuments(case_number="2026타경10002"),
            ),
        ]

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        assert result.total_queried == 2
        assert result.errors == 1
        assert result.updated == 1

    def test_dry_run_no_db_write(self, db_session):
        """dry_run=True → DB 변경 없음"""
        auction = _make_auction()
        score = _make_score(auction.id)
        _setup(db_session, auction, score)

        detail = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect(dry_run=True)

        assert result.updated == 1  # updated 카운트는 올라감

        db_session.expire_all()
        auction_row = db_session.query(Auction).first()
        score_row = db_session.query(Score).first()
        # DB는 변경되지 않음
        assert auction_row.winning_bid is None
        assert score_row.actual_winning_bid is None


class TestFiltering:
    def test_court_filter(self, db_session):
        """court_office_code 필터 → 해당 법원만 처리"""
        a1 = _make_auction(case_number="2026타경10001", court_office_code="B000210")
        s1 = _make_score(a1.id)
        _setup(db_session, a1, s1)

        a2 = _make_auction(case_number="2026타경20001", court_office_code="B000214")
        a2.id = str(uuid.uuid4())
        s2 = _make_score(a2.id)
        s2.auction_id = a2.id
        db_session.add(a2)
        db_session.flush()
        db_session.add(s2)
        db_session.commit()

        detail = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        # B000210만 처리
        result = collector.collect(court_office_code="B000210")

        assert result.total_queried == 1
        assert result.updated == 1
        # B000214는 건드리지 않음
        s2_row = db_session.query(Score).filter(Score.auction_id == a2.id).first()
        assert s2_row.actual_winning_bid is None

    def test_limit_respected(self, db_session):
        """limit=1 → 1건만 처리"""
        for i in range(3):
            a = _make_auction(case_number=f"2026타경1000{i}")
            a.id = str(uuid.uuid4())
            s = _make_score(a.id)
            s.auction_id = a.id
            db_session.add(a)
            db_session.flush()
            db_session.add(s)
        db_session.commit()

        detail = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect(limit=1)

        assert result.total_queried == 1
        assert result.updated == 1

    def test_skip_already_updated_auction(self, db_session):
        """winning_bid 이미 있으면 조회 대상 제외 (WHERE winning_bid IS NULL)"""
        # winning_bid가 이미 설정된 auction
        auction = _make_auction(winning_bid=400_000_000, status="매각")
        score = _make_score(auction.id, actual_winning_bid=400_000_000)
        _setup(db_session, auction, score)

        crawler = MagicMock(spec=CourtAuctionClient)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        # 조회 자체가 안됨 (WHERE winning_bid IS NULL)
        assert result.total_queried == 0
        assert result.updated == 0
        crawler.collect_full_case.assert_not_called()

    def test_exclude_cancelled_status(self, db_session):
        """status='취하' or '변경' → 조회 대상 제외"""
        a1 = _make_auction(case_number="2026타경10001", status="취하")
        a1.id = str(uuid.uuid4())
        db_session.add(a1)

        a2 = _make_auction(case_number="2026타경10002", status="변경")
        a2.id = str(uuid.uuid4())
        db_session.add(a2)

        a3 = _make_auction(case_number="2026타경10003", status="진행")
        a3.id = str(uuid.uuid4())
        db_session.add(a3)
        db_session.flush()
        db_session.commit()

        detail = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        # 취하/변경 제외, 진행만 조회
        assert result.total_queried == 1

    def test_update_auction_without_score(self, db_session):
        """Score 없는 Auction도 winning_bid 업데이트 가능"""
        auction = _make_auction()
        # Score 없이 Auction만 삽입
        _setup(db_session, auction)

        detail = _make_detail_with_rounds(winning_bid=420_000_000)
        crawler = _mock_crawler(detail)

        collector = WinningBidCollector(db=db_session, crawler=crawler)
        result = collector.collect()

        assert result.updated == 1

        db_session.expire_all()
        auction_row = db_session.query(Auction).first()
        assert auction_row.winning_bid == 420_000_000
        assert auction_row.status == "매각"
