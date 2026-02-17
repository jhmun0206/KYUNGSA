"""낙찰결과 수집기 (Phase 6.5)

status='매각'인 Auction의 Score에 실제 낙찰가/낙찰가율/예측오차를 채워넣는다.
Phase 5F(백테스트/캘리브레이션)에서 활용할 데이터를 누적한다.

=== 설계 원칙 ===
- per-case commit: 건별 독립 저장 (중간 실패해도 이전 결과 보존)
- fail-open: API 실패 → errors += 1, 다음 건 계속 진행
- dry_run: DB 변경 없이 수집 가능 건수만 확인
- appraised_value=0 방어: division-by-zero 방지
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
    updated: int = 0  # 업데이트 성공 건수
    skipped: int = 0  # 낙찰가 미확인 (API 미반환 or None)
    errors: int = 0  # 오류 건수 (API 실패 등)
    started_at: datetime
    finished_at: datetime | None = None


class WinningBidCollector:
    """낙찰결과 수집기

    DB에서 status='매각' + scores.actual_winning_bid IS NULL 조건의
    물건을 조회하여, 대법원 경매정보 API로 실제 낙찰가를 수집하고
    Score 테이블을 업데이트한다.
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

        # 대상 조회: status='매각' + actual_winning_bid IS NULL
        query = (
            self._db.query(Auction, Score)
            .join(Score, Score.auction_id == Auction.id)
            .filter(Auction.status == "매각")
            .filter(Score.actual_winning_bid == None)  # noqa: E711
        )
        if court_office_code:
            query = query.filter(Auction.court_office_code == court_office_code)
        if limit:
            query = query.limit(limit)

        rows = query.all()
        result.total_queried = len(rows)

        logger.info(
            "낙찰결과 수집 시작: %d건 (court=%s, dry_run=%s)",
            result.total_queried,
            court_office_code or "전체",
            dry_run,
        )

        for auction, score in rows:
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
        score: Score,
        dry_run: bool,
    ) -> bool:
        """단일 물건 낙찰결과 수집 및 Score 업데이트

        Returns:
            True: 업데이트 성공, False: 낙찰가 미확인 (skipped)
        """
        # API 호출에 필요한 식별자 추출
        detail_raw = auction.detail or {}
        # internal_case_number: detail JSONB 또는 case_number로 폴백
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

        # result == "매각" 라운드 탐색
        winning_round = next(
            (r for r in case_detail.auction_rounds if r.result == "매각"),
            None,
        )
        if winning_round is None:
            logger.info("낙찰 라운드 없음 [%s]", auction.case_number)
            return False

        winning_bid = winning_round.winning_bid
        if winning_bid is None:
            logger.info("낙찰가 None [%s]", auction.case_number)
            return False

        appraised_value = auction.appraised_value
        if not appraised_value:
            logger.warning("감정가 0 또는 None [%s] — 낙찰가율 산출 불가", auction.case_number)
            return False

        # 낙찰가율 + 예측오차 산출
        actual_winning_ratio = winning_bid / appraised_value
        prediction_error: float | None = None
        if score.predicted_winning_ratio is not None:
            prediction_error = actual_winning_ratio - score.predicted_winning_ratio

        logger.info(
            "낙찰결과 확인 [%s]: 낙찰가=%d, 낙찰가율=%.4f",
            auction.case_number,
            winning_bid,
            actual_winning_ratio,
        )

        if not dry_run:
            score.actual_winning_bid = winning_bid
            score.actual_winning_ratio = round(actual_winning_ratio, 4)
            score.prediction_error = round(prediction_error, 4) if prediction_error is not None else None
            self._db.commit()

        return True
