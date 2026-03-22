"""Phase J: 저장 검색 매칭 개인 텔레그램 알림 발송

배치 수집 완료 후 실행하거나, 매일 배치 직후 cron으로 실행.

사용법:
  # 전체 유저 알림 발송
  PYTHONPATH=backend python scripts/send_alerts.py

  # 특정 유저만 테스트
  PYTHONPATH=backend python scripts/send_alerts.py --user-id USER_ID

  # 실제 발송 없이 매칭 건수만 출력
  PYTHONPATH=backend python scripts/send_alerts.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from sqlalchemy import and_

# 프로젝트 루트 경로 추가
sys.path.insert(0, "backend")

from app.database import SessionLocal  # noqa: E402
from app.models.db.auction import Auction  # noqa: E402
from app.models.db.score import Score  # noqa: E402
from app.models.db.user import User, UserSavedSearch  # noqa: E402
from app.services.notifier import send_personal_alert  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 신규 물건 기준: 오늘 기준 N일 이내 수집된 물건
NEW_AUCTION_DAYS = 1


def query_auctions_by_params(db, params: dict) -> list[Auction]:
    """저장 검색 params_json → 매칭 물건 조회

    AuctionListItem 필터와 동일한 기준으로 적용:
      grade, court, type, district 지원.
    """
    since = date.today() - timedelta(days=NEW_AUCTION_DAYS)

    q = (
        db.query(Auction)
        .join(Score, Score.auction_id == Auction.id, isouter=True)
        .filter(
            Auction.status.in_(["진행", "예정"]),
            Auction.updated_at >= since,
        )
    )

    # grade 필터 ("A,B" 형태)
    grade_str = params.get("grade", "")
    if grade_str:
        grades = [g.strip() for g in grade_str.split(",") if g.strip()]
        if grades:
            q = q.filter(Score.grade.in_(grades))

    # court 필터
    court = params.get("court", "")
    if court:
        q = q.filter(Auction.court_office_code == court)

    # type 필터 (property_category)
    ptype = params.get("type", "")
    if ptype:
        q = q.filter(Auction.property_category == ptype)

    # district 필터 (주소에 포함)
    district = params.get("district", "")
    if district:
        q = q.filter(Auction.address.ilike(f"%{district}%"))

    return q.order_by(Score.grade.asc().nullslast(), Auction.auction_date.asc()).limit(10).all()


def auction_to_dict(a: Auction, score) -> dict:
    return {
        "case_number": a.case_number,
        "address": a.address,
        "minimum_bid": a.minimum_bid,
        "grade": score.grade if score else None,
    }


def run(user_id: str | None = None, dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        # 텔레그램 연동된 유저 조회
        q = db.query(User).filter(User.telegram_chat_id.isnot(None))
        if user_id:
            q = q.filter(User.id == user_id)
        users = q.all()

        logger.info("알림 대상 유저: %d명", len(users))

        for user in users:
            searches = (
                db.query(UserSavedSearch)
                .filter(UserSavedSearch.user_id == user.id)
                .all()
            )
            if not searches:
                continue

            for search in searches:
                auctions = query_auctions_by_params(db, search.params_json)
                if not auctions:
                    continue

                # Score join 데이터 조회
                score_map = {}
                from app.models.db.score import Score  # noqa: F811
                scores = db.query(Score).filter(
                    Score.auction_id.in_([a.id for a in auctions])
                ).all()
                for s in scores:
                    score_map[s.auction_id] = s

                matched = [auction_to_dict(a, score_map.get(a.id)) for a in auctions]

                logger.info(
                    "유저=%s 검색조건='%s' 매칭=%d건%s",
                    user.email,
                    search.name,
                    len(matched),
                    " [DRY-RUN]" if dry_run else "",
                )

                if not dry_run:
                    send_personal_alert(user.telegram_chat_id, search.name, matched)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="저장 검색 텔레그램 알림 발송")
    parser.add_argument("--user-id", help="특정 유저 ID만 처리")
    parser.add_argument("--dry-run", action="store_true", help="실제 발송 없이 매칭 건수만 출력")
    args = parser.parse_args()

    run(user_id=args.user_id, dry_run=args.dry_run)
