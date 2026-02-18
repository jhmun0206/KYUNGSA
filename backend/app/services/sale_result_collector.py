"""매각결과 대량 수집기 — Phase 6.5b

=== 설계 원칙 ===

전략: 매각결과검색 엔드포인트 직접 호출 (전략 3)
대법원 PGJ158 화면의 매각결과검색 API를 통해 낙찰 완료 건을 대량 수집.
WinningBidCollector(전략 2)의 보완재.

WinningBidCollector vs SaleResultCollector 역할 분리:
  - WinningBidCollector: DB에 이미 수집된 물건의 낙찰가 사후 추적 (1건씩 상세조회)
  - SaleResultCollector: 법원별 낙찰 완료 건 일괄 수집 (paginated 배치)

동작 방식:
  1. court_codes 목록을 순회하며 법원별 페이지네이션 수집
  2. maeAmt=0 건 스킵 (낙찰가 미확정)
  3. 클라이언트 측 날짜 필터 (maeGiil 기준, date_from/date_to)
  4. 기존 Auction 조회:
     - winning_bid 있음 → already_exists (스킵)
     - winning_bid 없음 → 업데이트 (Auction + Score)
     - 신규 물건    → INSERT (낙찰 데이터만, Score 없음)
  5. per-case commit (장애 복원력)
  6. fail-open (법원별 실패 → 다음 법원 계속)

=== 주의 ===
- 신규 INSERT 물건은 Score를 생성하지 않음 (점수 없이 낙찰 데이터만 — Phase 9 훈련용)
- winning_source = "sale_result_api" (WinningBidCollector의 "court_api"와 구분)
- pageSize=50 고정 (100은 WAF 차단 확인됨)
- WAF 대응: 페이지 요청 간 page_delay(기본 2.5초) 대기
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.score import Score
from app.services.crawler.court_auction import CourtAuctionClient

logger = logging.getLogger(__name__)

# 서울 5개 법원 코드 (기본값)
SEOUL_COURT_CODES: list[str] = [
    "B000210",  # 서울중앙
    "B000211",  # 서울남부
    "B000212",  # 서울서부
    "B000213",  # 서울북부
    "B000214",  # 서울동부
]


class SaleResultCollectorResult(BaseModel):
    """매각결과 수집 통계"""

    courts_queried: int = 0       # 조회한 법원 수
    total_items: int = 0          # API에서 받은 총 아이템 수 (maeAmt=0 포함)
    updated: int = 0              # 기존 물건 winning_bid 업데이트
    new_inserted: int = 0         # 신규 물건 INSERT
    skipped_no_amount: int = 0    # maeAmt=0 건 스킵
    skipped_date_filter: int = 0  # 날짜 범위 밖 스킵
    already_exists: int = 0       # 이미 winning_bid 있음 (스킵)
    errors: int = 0               # 법원/건별 오류 수
    started_at: datetime
    finished_at: datetime | None = None


class SaleResultCollector:
    """매각결과 대량 수집기

    법원별 매각결과검색 API를 순회하여 낙찰 완료 건을
    Auction 테이블에 업데이트 또는 신규 삽입한다.
    """

    def __init__(
        self,
        db: Session,
        crawler: CourtAuctionClient,
        page_delay: float = 2.5,
    ) -> None:
        self._db = db
        self._crawler = crawler
        self._page_delay = page_delay

    def collect(
        self,
        court_codes: list[str] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> SaleResultCollectorResult:
        """매각결과 수집 실행

        Args:
            court_codes: 법원코드 목록 (None이면 SEOUL_COURT_CODES 사용)
            date_from: 수집 시작일 maeGiil 기준 클라이언트 필터 (None이면 제한 없음)
            date_to: 수집 종료일 (None이면 제한 없음)
            dry_run: True면 DB 변경 없이 통계만 반환
            limit: 전체 처리 건수 상한 (None이면 전체)

        Returns:
            SaleResultCollectorResult — 수집 통계
        """
        targets = court_codes or SEOUL_COURT_CODES
        result = SaleResultCollectorResult(started_at=datetime.now())

        logger.info(
            "매각결과 수집 시작: 법원 %d개, date_from=%s, date_to=%s, dry_run=%s",
            len(targets),
            date_from,
            date_to,
            dry_run,
        )

        total_processed = 0

        for court_code in targets:
            if limit is not None and total_processed >= limit:
                break
            try:
                processed = self._collect_court(
                    court_code=court_code,
                    result=result,
                    date_from=date_from,
                    date_to=date_to,
                    dry_run=dry_run,
                    remaining=None if limit is None else limit - total_processed,
                )
                total_processed += processed
                result.courts_queried += 1
            except Exception as e:
                logger.error("법원 수집 실패 [%s]: %s", court_code, e)
                result.errors += 1

        result.finished_at = datetime.now()
        logger.info(
            "매각결과 수집 완료: 법원=%d, 업데이트=%d, 신규=%d, 스킵(금액)=%d, "
            "스킵(날짜)=%d, 이미존재=%d, 오류=%d",
            result.courts_queried,
            result.updated,
            result.new_inserted,
            result.skipped_no_amount,
            result.skipped_date_filter,
            result.already_exists,
            result.errors,
        )
        return result

    # ─────────────────────────────────────────────
    # 내부 메서드
    # ─────────────────────────────────────────────

    def _collect_court(
        self,
        court_code: str,
        result: SaleResultCollectorResult,
        date_from: date | None,
        date_to: date | None,
        dry_run: bool,
        remaining: int | None,
    ) -> int:
        """단일 법원의 매각결과 전체 수집 (페이지네이션)

        Returns:
            해당 법원에서 처리(업데이트+신규+스킵+에러)된 총 건수
        """
        # 1페이지 요청 → totalCnt 확인
        items, total_cnt = self._crawler.fetch_sale_results(court_code, page_no=1)
        total_pages = max(1, math.ceil(total_cnt / 50)) if total_cnt else 1

        court_label = court_code if court_code else "전국"
        logger.info(
            "법원 [%s]: 전체 %d건, %d페이지", court_label, total_cnt, total_pages
        )

        court_processed = 0
        result.total_items += len(items)

        # 법원 단위 중복 추적: 같은 사건번호 여러 maemulSer 방지
        # - real-run: per-case commit으로 두 번째 건이 existing으로 잡히지만,
        #   dry-run에서는 DB write 없이 두 번째도 None → 중복 카운트 발생
        # - seen_cases로 세션 내 중복을 명시적으로 차단
        seen_cases: set[str] = set()

        court_processed += self._process_items(
            items=items,
            result=result,
            date_from=date_from,
            date_to=date_to,
            dry_run=dry_run,
            seen_cases=seen_cases,
        )

        for page_no in range(2, total_pages + 1):
            # 전체 limit 체크
            if remaining is not None and court_processed >= remaining:
                break

            time.sleep(self._page_delay)

            try:
                items, _ = self._crawler.fetch_sale_results(court_code, page_no=page_no)
            except Exception as e:
                logger.error("페이지 %d 요청 실패 [%s]: %s", page_no, court_label, e)
                result.errors += 1
                continue

            result.total_items += len(items)
            court_processed += self._process_items(
                items=items,
                result=result,
                date_from=date_from,
                date_to=date_to,
                dry_run=dry_run,
                seen_cases=seen_cases,
            )

        return court_processed

    def _process_items(
        self,
        items: list[dict[str, Any]],
        result: SaleResultCollectorResult,
        date_from: date | None,
        date_to: date | None,
        dry_run: bool,
        seen_cases: set[str],
    ) -> int:
        """아이템 목록 처리. 처리된 건수 반환."""
        count = 0
        for item in items:
            try:
                outcome = self._process_one(item, date_from, date_to, dry_run, seen_cases)
                if outcome == "updated":
                    result.updated += 1
                elif outcome == "inserted":
                    result.new_inserted += 1
                elif outcome == "no_amount":
                    result.skipped_no_amount += 1
                elif outcome == "date_filtered":
                    result.skipped_date_filter += 1
                elif outcome == "already_exists":
                    result.already_exists += 1
            except Exception as e:
                case_number = item.get("srnSaNo", "?")
                logger.error("건별 처리 실패 [%s]: %s", case_number, e)
                result.errors += 1
                try:
                    self._db.rollback()
                except Exception:
                    pass
            count += 1
        return count

    def _process_one(
        self,
        item: dict[str, Any],
        date_from: date | None,
        date_to: date | None,
        dry_run: bool,
        seen_cases: set[str],
    ) -> str:
        """단일 아이템 처리

        Returns:
            처리 결과 키:
              "no_amount"    - maeAmt=0
              "date_filtered"- 날짜 범위 밖
              "already_exists"- winning_bid 이미 있음
              "updated"      - 기존 물건 업데이트
              "inserted"     - 신규 물건 삽입
        """
        case_number: str = item.get("srnSaNo", "").strip()
        court_office_code: str = item.get("boCd", "").strip()

        # 0. 세션 내 중복 체크 (같은 사건번호의 여러 maemulSer 방지)
        #    - DB unique 제약(case_number)상 두 번째 물건은 저장 불가
        #    - dry-run에서도 통계 오염 방지
        if case_number in seen_cases:
            logger.debug("세션 내 중복 스킵 [%s]", case_number)
            return "already_exists"
        seen_cases.add(case_number)

        # 1. 낙찰가 확인
        winning_bid = _safe_int(item.get("maeAmt"))
        if not winning_bid:
            logger.debug("maeAmt=0 스킵 [%s]", case_number)
            return "no_amount"

        # 2. 날짜 필터 (클라이언트 측)
        mae_date = _parse_date(item.get("maeGiil"))
        if mae_date is not None:
            if date_from and mae_date < date_from:
                return "date_filtered"
            if date_to and mae_date > date_to:
                return "date_filtered"

        # 3. 감정가 (낙찰가율 계산용)
        appraised_value = _safe_int(item.get("gamevalAmt"))
        winning_ratio: float | None = None
        if appraised_value:
            winning_ratio = round(winning_bid / appraised_value, 4)

        # 4. DB 조회 (case_number 기준)
        existing: Auction | None = (
            self._db.query(Auction)
            .filter(Auction.case_number == case_number)
            .first()
        )

        if existing is not None:
            # 이미 winning_bid 있으면 스킵
            if existing.winning_bid is not None:
                return "already_exists"

            # winning_bid 업데이트
            logger.info(
                "기존 물건 업데이트 [%s]: 낙찰가=%d, 낙찰가율=%s",
                case_number,
                winning_bid,
                winning_ratio,
            )
            if not dry_run:
                existing.winning_bid = winning_bid
                existing.winning_date = mae_date
                existing.winning_ratio = winning_ratio
                existing.winning_source = "sale_result_api"
                existing.status = "매각"

                # Score 업데이트 (있으면, actual_winning_bid 미설정 시)
                score: Score | None = existing.score
                if score is not None and score.actual_winning_bid is None:
                    score.actual_winning_bid = winning_bid
                    if winning_ratio is not None:
                        score.actual_winning_ratio = winning_ratio
                        if score.predicted_winning_ratio is not None:
                            score.prediction_error = round(
                                winning_ratio - score.predicted_winning_ratio, 4
                            )

                self._db.commit()
            return "updated"

        else:
            # 신규 물건 INSERT (낙찰 데이터만, Score 없음)
            logger.info("신규 물건 삽입 [%s]: 낙찰가=%d", case_number, winning_bid)
            if not dry_run:
                minimum_bid = _safe_int(item.get("minmaePrice"))
                new_auction = Auction(
                    id=str(uuid.uuid4()),
                    case_number=case_number,
                    court=item.get("jiwonNm", "").strip() or "미상",
                    court_office_code=court_office_code,
                    address=item.get("printSt", "").strip(),
                    property_type=item.get("dspslUsgNm", "").strip(),
                    appraised_value=appraised_value,
                    minimum_bid=minimum_bid,
                    status="매각",
                    winning_bid=winning_bid,
                    winning_date=mae_date,
                    winning_ratio=winning_ratio,
                    winning_source="sale_result_api",
                    detail=_extract_detail(item),
                )
                self._db.add(new_auction)
                self._db.commit()
            return "inserted"


# ─────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────


def _safe_int(value: Any) -> int | None:
    """문자열/None → int (변환 실패 시 None)"""
    if value is None:
        return None
    try:
        result = int(str(value).strip() or "0")
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None


def _parse_date(value: Any) -> date | None:
    """YYYYMMDD 문자열 → date (변환 실패 시 None)"""
    if not value:
        return None
    s = str(value).strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except (ValueError, TypeError):
        return None


def _extract_detail(item: dict[str, Any]) -> dict[str, Any]:
    """응답 아이템에서 주요 필드를 뽑아 JSONB detail로 저장"""
    return {
        "maemulSer": item.get("maemulSer"),
        "mulStatcd": item.get("mulStatcd"),
        "maeGiil": item.get("maeGiil"),
        "maegyuljGiil": item.get("maegyuljGiil"),
        "yuchalCnt": item.get("yuchalCnt"),
        "lclsUtilCd": item.get("lclsUtilCd"),
        "hjguSido": item.get("hjguSido"),
        "hjguSigu": item.get("hjguSigu"),
        "hjguDong": item.get("hjguDong"),
        "buldNm": item.get("buldNm"),
        "xCordi": item.get("xCordi"),
        "yCordi": item.get("yCordi"),
        "source": "sale_result_api",
    }
