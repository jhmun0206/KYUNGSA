"""배치 수집기 — 크롤링 → 보강 → 필터링 → DB 저장

대법원 경매정보를 전 페이지 수집하여 DB에 저장한다.
1단 필터링만 수행 (2단 등기부 분석은 on-demand).
RED 포함 전 건 저장. 조회 시 WHERE color != 'RED'로 필터링.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.converters import save_enriched_case
from app.models.db.pipeline_run import PipelineRun
from app.models.db.score import Score
from app.models.enriched_case import FilterColor
from app.services.crawler.court_auction import CourtAuctionClient
from app.services.enricher import CaseEnricher
from app.services.rules.engine import RuleEngineV2

logger = logging.getLogger(__name__)

PAGE_SIZE = 40  # 대법원 최대 페이지 크기


class BatchResult(BaseModel):
    """배치 수집 결과"""

    run_id: str
    court_code: str
    total_searched: int = 0
    total_pages: int = 0
    skipped: int = 0
    processed: int = 0
    new_count: int = 0
    updated_count: int = 0
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class BatchCollector:
    """배치 수집기 — 크롤러 + 보강 + 필터 + DB 저장"""

    def __init__(
        self,
        db: Session,
        crawler: CourtAuctionClient | None = None,
        enricher: CaseEnricher | None = None,
        rule_engine: RuleEngineV2 | None = None,
    ) -> None:
        self._db = db
        self._crawler = crawler or CourtAuctionClient()
        self._enricher = enricher or CaseEnricher()
        self._rule_engine = rule_engine or RuleEngineV2()

    def collect(
        self,
        court_code: str,
        *,
        max_items: int = 0,
        force_update: bool = False,
        enrich_delay: float = 2.0,
        dry_run: bool = False,
    ) -> BatchResult:
        """배치 수집 실행

        Args:
            court_code: 법원코드 (예: "B000210")
            max_items: 최대 처리 건수 (0=전체)
            force_update: True면 기존 데이터 덮어쓰기
            enrich_delay: 물건 간 대기 시간 (초)
            dry_run: True면 DB 저장 없이 수집만

        Returns:
            BatchResult
        """
        now = datetime.now(timezone.utc)
        short_id = uuid.uuid4().hex[:8]
        run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{court_code}_{short_id}"

        result = BatchResult(
            run_id=run_id,
            court_code=court_code,
            started_at=now,
        )

        # PipelineRun 생성 (RUNNING)
        pipeline_run = None
        if not dry_run:
            pipeline_run = PipelineRun(
                run_id=run_id,
                court_code=court_code,
                started_at=now,
                status="RUNNING",
            )
            self._db.add(pipeline_run)
            self._db.commit()

        try:
            self._do_collect(
                court_code=court_code,
                result=result,
                max_items=max_items,
                force_update=force_update,
                enrich_delay=enrich_delay,
                dry_run=dry_run,
            )
        except Exception as e:
            logger.error("배치 수집 치명적 오류: %s", e)
            result.errors.append(f"치명적 오류: {e}")

        # 완료 처리
        result.finished_at = datetime.now(timezone.utc)

        if pipeline_run and not dry_run:
            pipeline_run.finished_at = result.finished_at
            pipeline_run.total_searched = result.total_searched
            pipeline_run.total_enriched = result.processed
            pipeline_run.total_filtered = result.processed
            pipeline_run.red_count = result.red_count
            pipeline_run.yellow_count = result.yellow_count
            pipeline_run.green_count = result.green_count
            pipeline_run.errors = result.errors or None
            pipeline_run.status = "COMPLETED" if not result.errors else "COMPLETED"
            self._db.commit()

        logger.info(
            "배치 완료 [%s]: 검색=%d, 처리=%d, 스킵=%d, 에러=%d "
            "(R=%d, Y=%d, G=%d)",
            run_id,
            result.total_searched,
            result.processed,
            result.skipped,
            len(result.errors),
            result.red_count,
            result.yellow_count,
            result.green_count,
        )
        return result

    def _do_collect(
        self,
        court_code: str,
        result: BatchResult,
        *,
        max_items: int,
        force_update: bool,
        enrich_delay: float,
        dry_run: bool,
    ) -> None:
        """실제 수집 루프"""
        # 1페이지 검색 → 전체 건수 파악
        items, total_count = self._crawler.search_cases_with_total(
            court_code=court_code, page_no=1, page_size=PAGE_SIZE,
        )
        result.total_searched = total_count
        result.total_pages = max(1, math.ceil(total_count / PAGE_SIZE))

        logger.info(
            "검색 결과: 전체 %d건, %d페이지",
            total_count, result.total_pages,
        )

        # 1페이지 물건 처리
        items_processed = self._process_items(
            items=items,
            result=result,
            max_items=max_items,
            force_update=force_update,
            enrich_delay=enrich_delay,
            dry_run=dry_run,
        )

        # 2페이지 이후
        if max_items > 0 and items_processed >= max_items:
            return

        for page_no in range(2, result.total_pages + 1):
            if max_items > 0 and items_processed >= max_items:
                break

            try:
                page_items, _ = self._crawler.search_cases_with_total(
                    court_code=court_code, page_no=page_no, page_size=PAGE_SIZE,
                )
            except Exception as e:
                logger.error("페이지 %d 검색 실패: %s", page_no, e)
                result.errors.append(f"페이지 {page_no} 검색 실패: {e}")
                continue

            remaining = max_items - items_processed if max_items > 0 else 0
            items_processed += self._process_items(
                items=page_items,
                result=result,
                max_items=remaining if max_items > 0 else 0,
                force_update=force_update,
                enrich_delay=enrich_delay,
                dry_run=dry_run,
            )

    def _process_items(
        self,
        items: list,
        result: BatchResult,
        *,
        max_items: int,
        force_update: bool,
        enrich_delay: float,
        dry_run: bool,
    ) -> int:
        """물건 목록 처리. 처리된 건수 반환."""
        count = 0

        for i, item in enumerate(items):
            if max_items > 0 and count >= max_items:
                break

            case_number = item.case_number
            if not case_number:
                continue

            # skip-existing
            if not force_update and not dry_run:
                existing = (
                    self._db.query(Auction.id)
                    .filter(Auction.case_number == case_number)
                    .first()
                )
                if existing:
                    result.skipped += 1
                    logger.debug("스킵 (기존): %s", case_number)
                    continue

            # 물건 간 딜레이
            if i > 0:
                time.sleep(enrich_delay)

            try:
                self._process_single_item(
                    item=item,
                    result=result,
                    force_update=force_update,
                    dry_run=dry_run,
                )
                count += 1
            except Exception as e:
                logger.error("물건 처리 실패 [%s]: %s", case_number, e)
                result.errors.append(f"[{case_number}] {e}")
                count += 1  # 에러도 처리 시도로 카운트

        return count

    def _process_single_item(
        self,
        item,
        result: BatchResult,
        *,
        force_update: bool,
        dry_run: bool,
    ) -> None:
        """단일 물건 처리: 상세조회 → 보강 → 필터 → DB 저장"""
        # 상세 조회
        detail = self._crawler.fetch_case_detail(
            case_number=item.internal_case_number,
            court_office_code=item.court_office_code,
            property_sequence=item.property_sequence or "1",
        )

        # 보강 (항상 성공, partial result 가능)
        enriched = self._enricher.enrich(detail)

        # 통합 평가 (필터 + 가격 + 통합 점수)
        eval_result = self._rule_engine.evaluate(enriched)
        enriched.filter_result = eval_result.filter_result
        enriched.price_score = eval_result.price
        enriched.total_score = eval_result.total

        # 카운트 갱신
        color = enriched.filter_result.color
        if color == FilterColor.RED:
            result.red_count += 1
        elif color == FilterColor.YELLOW:
            result.yellow_count += 1
        else:
            result.green_count += 1

        result.processed += 1

        # DB 저장 (per-case commit)
        if not dry_run:
            # upsert 여부 판단
            existing = (
                self._db.query(Auction.id)
                .filter(Auction.case_number == detail.case_number)
                .first()
            )
            is_update = existing is not None

            try:
                auction_orm = save_enriched_case(self._db, enriched)

                # Score 테이블 upsert
                if enriched.total_score:
                    self._save_score(auction_orm.id, enriched, result.run_id)

                if is_update:
                    result.updated_count += 1
                else:
                    result.new_count += 1
            except Exception as e:
                self._db.rollback()
                raise RuntimeError(f"DB 저장 실패: {e}") from e

        logger.info(
            "처리 완료 [%s]: %s grade=%s%s",
            detail.case_number,
            color.value,
            enriched.total_score.grade if enriched.total_score else "-",
            " (dry-run)" if dry_run else "",
        )

    def _save_score(
        self,
        auction_id: str,
        enriched,
        run_id: str,
    ) -> None:
        """Score 테이블 upsert"""
        ts = enriched.total_score
        if ts is None:
            return

        existing = (
            self._db.query(Score)
            .filter(Score.auction_id == auction_id)
            .first()
        )
        if existing:
            self._db.delete(existing)
            self._db.flush()

        score_orm = Score(
            auction_id=auction_id,
            property_category=ts.property_category,
            legal_score=ts.legal_score,
            price_score=ts.price_score,
            location_score=ts.location_score,
            occupancy_score=ts.occupancy_score,
            total_score=ts.total_score,
            score_coverage=ts.score_coverage,
            missing_pillars=ts.missing_pillars,
            grade=ts.grade,
            sub_scores=ts.weights_used,
            warnings=ts.warnings or None,
            needs_expert_review=ts.needs_expert_review,
            scorer_version=ts.scorer_version,
            pipeline_run_id=run_id,
        )
        self._db.add(score_orm)
        self._db.flush()
