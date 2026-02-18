"""낙찰결과 수집기 — 기수집 물건 상태 추적 (Phase 6.5a)

=== 설계 원칙 ===

전략: 기수집 물건 상태 추적 (전략 2)
DB에 있는 물건을 직접 collect_full_case()로 조회하여 낙찰 여부를 확인한다.

배경:
  BatchCollector는 대법원 경매 검색에서 '진행' 물건만 수집한다.
  낙찰(매각) 후에는 검색 결과에서 사라지므로, DB에는 status='진행' 레코드만 남는다.
  이 서비스는 DB의 미처리 물건(winning_bid IS NULL)을 직접 상세조회하여
  낙찰 여부를 확인하고 Auction + Score 양쪽을 업데이트한다.

동작 방식:
  1. WHERE auctions.winning_bid IS NULL + 취하/변경 제외
  2. 건별 collect_full_case() → auction_rounds 탐색
  3. result='매각' 라운드 발견 시: Auction + Score 업데이트
  4. per-case commit (장애 복원력)
  5. fail-open (API 실패 → errors += 1, 다음 건 계속)

=== 주의 ===
- dry_run=True: DB 변경 없이 수집 가능 건수 확인 (updated 카운트는 올라감)
- Score JOIN은 optional outerjoin: Score 없는 Auction도 winning_bid 업데이트
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.score import Score
from app.services.crawler.court_auction import CourtAuctionClient

logger = logging.getLogger(__name__)


class WinningBidCollectorResult(BaseModel):
    """낙찰결과 수집 통계"""

    total_queried: int = 0  # DB에서 조회한 총 건수
    updated: int = 0  # 업데이트 성공 건수 (낙찰 확인)
    skipped: int = 0  # 낙찰 미확인 (아직 진행 중, 유찰, or 낙찰가 None)
    errors: int = 0  # 오류 건수 (API 실패 등)
    started_at: datetime
    finished_at: datetime | None = None


class WinningBidCollector:
    """낙찰결과 수집기

    DB에서 winning_bid IS NULL 조건의 물건을 조회하여,
    대법원 경매정보 API로 낙찰 여부를 확인하고
    Auction.winning_bid + Score.actual_winning_bid를 업데이트한다.
    """

    def __init__(self, db: Session, crawler: CourtAuctionClient) -> None:
        self._db = db
        self._crawler = crawler

    def collect(
        self,
        court_office_code: str | None = None,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> WinningBidCollectorResult:
        """낙찰결과 수집 실행

        Args:
            court_office_code: 특정 법원 코드로 필터 (None이면 전체)
            dry_run: True이면 DB 변경 없이 통계만 반환
            limit: 최대 처리 건수 (None이면 전체)

        Returns:
            WinningBidCollectorResult — 수집 통계
        """
        result = WinningBidCollectorResult(started_at=datetime.now())

        # 대상 조회: winning_bid IS NULL + 취하/변경 제외
        # outerjoin: Score 없는 Auction도 포함
        query = (
            self._db.query(Auction)
            .filter(Auction.winning_bid == None)  # noqa: E711
            .filter(Auction.status.notin_(["취하", "변경"]))
        )
        if court_office_code:
            query = query.filter(Auction.court_office_code == court_office_code)
        if limit:
            query = query.limit(limit)

        auctions = query.all()
        result.total_queried = len(auctions)

        logger.info(
            "낙찰결과 수집 시작: %d건 (court=%s, dry_run=%s)",
            result.total_queried,
            court_office_code or "전체",
            dry_run,
        )

        for auction in auctions:
            score = auction.score  # Score 없으면 None (relationship)
            try:
                updated = self._process_one(auction, score, dry_run)
                if updated:
                    result.updated += 1
                else:
                    result.skipped += 1
            except Exception as e:
                logger.error(
                    "낙찰결과 수집 실패 [%s]: %s", auction.case_number, e
                )
                result.errors += 1
                try:
                    self._db.rollback()
                except Exception:
                    pass

        result.finished_at = datetime.now()
        logger.info(
            "낙찰결과 수집 완료: updated=%d, skipped=%d, errors=%d",
            result.updated,
            result.skipped,
            result.errors,
        )
        return result

    def _process_one(
        self,
        auction: Auction,
        score: Score | None,
        dry_run: bool,
    ) -> bool:
        """단일 물건 낙찰결과 수집 및 업데이트

        Returns:
            True: 낙찰 확인 후 업데이트 성공, False: 낙찰 미확인 (skipped)
        """
        # API 호출에 필요한 식별자 추출
        detail_raw = auction.detail or {}
        internal_case_number = (
            detail_raw.get("internal_case_number") or auction.case_number
        )
        court_code = auction.court_office_code or detail_raw.get("court_office_code", "")
        property_sequence = detail_raw.get("property_sequence") or "1"

        # 대법원 상세 조회
        case_detail, _, _ = self._crawler.collect_full_case(
            case_number=internal_case_number,
            court_office_code=court_code,
            property_sequence=str(property_sequence),
        )

        # result='매각' 라운드 탐색
        winning_round = next(
            (r for r in case_detail.auction_rounds if r.result == "매각"),
            None,
        )
        if winning_round is None:
            logger.debug("낙찰 라운드 없음 [%s]", auction.case_number)
            return False

        winning_bid = winning_round.winning_bid
        if winning_bid is None:
            logger.info("낙찰가 None [%s]", auction.case_number)
            return False

        appraised_value = auction.appraised_value
        if not appraised_value:
            logger.warning(
                "감정가 0 또는 None [%s] — 낙찰가율 산출 불가", auction.case_number
            )
            return False

        # 낙찰가율 계산
        actual_winning_ratio = winning_bid / appraised_value
        winning_date = winning_round.round_date  # AuctionRound.round_date (nullable)

        logger.info(
            "낙찰결과 확인 [%s]: 낙찰가=%d, 낙찰가율=%.4f",
            auction.case_number,
            winning_bid,
            actual_winning_ratio,
        )

        if not dry_run:
            # Auction 업데이트
            auction.winning_bid = winning_bid
            auction.winning_date = winning_date
            auction.winning_ratio = round(actual_winning_ratio, 4)
            auction.winning_source = "court_api"
            auction.status = "매각"

            # Score 업데이트 (Score가 있고 actual_winning_bid 미설정 시)
            if score is not None and score.actual_winning_bid is None:
                score.actual_winning_bid = winning_bid
                score.actual_winning_ratio = round(actual_winning_ratio, 4)
                if score.predicted_winning_ratio is not None:
                    score.prediction_error = round(
                        actual_winning_ratio - score.predicted_winning_ratio, 4
                    )

            self._db.commit()

        return True
