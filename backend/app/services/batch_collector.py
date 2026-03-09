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
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.db.auction import Auction
from app.models.db.converters import auction_orm_to_detail, save_enriched_case
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
    new_grade_a: int = 0
    new_grade_b: int = 0
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
        skip_occupancy: bool = False,
    ) -> BatchResult:
        """배치 수집 실행

        Args:
            court_code: 법원코드 (예: "B000210")
            max_items: 최대 처리 건수 (0=전체)
            force_update: True면 기존 데이터 덮어쓰기
            enrich_delay: 물건 간 대기 시간 (초)
            dry_run: True면 DB 저장 없이 수집만
            skip_occupancy: True면 현황조사서 조회 스킵

        Returns:
            BatchResult
        """
        self._skip_occupancy = skip_occupancy
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
            try:
                # 오염된 세션이 있으면 정리 후 재시도
                try:
                    self._db.rollback()
                except Exception:
                    pass
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
            except Exception as e:
                logger.error("PipelineRun 최종 커밋 실패 [%s]: %s", run_id, e)
                try:
                    self._db.rollback()
                except Exception:
                    pass

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
        # 같은 사건번호의 다른 물건순서(property_sequence) 중복 처리 방지
        self._seen_cases: set[str] = set()

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

            # 같은 배치 내 중복 스킵 (같은 사건번호, 다른 property_sequence)
            if case_number in self._seen_cases:
                result.skipped += 1
                logger.debug("스킵 (배치 내 중복): %s", case_number)
                continue
            self._seen_cases.add(case_number)

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
                # 세션 오염 방지: 어떤 경로로 예외가 나와도 반드시 rollback
                try:
                    self._db.rollback()
                except Exception:
                    pass
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
        """단일 물건 처리: 상세조회 → 보강 → 현황조사서 → 필터 → DB 저장"""
        # 상세 조회
        detail = self._crawler.fetch_case_detail(
            case_number=item.internal_case_number,
            court_office_code=item.court_office_code,
            property_sequence=item.property_sequence or "1",
        )

        # property_type fallback: 상세 API에 물건용도가 없으면 리스트 값 사용
        if not detail.property_type and item.property_type:
            detail.property_type = item.property_type

        # 보강 (항상 성공, partial result 가능)
        enriched = self._enricher.enrich(detail)

        # 현황조사서 수집 (Phase 7-3) — fail-open
        tenants = None
        if not self._skip_occupancy:
            tenants = self._fetch_occupancy_tenants(
                court_office_code=item.court_office_code,
                property_sequence=item.property_sequence or "1",
                formatted_case_number=detail.case_number,
            )

        # 통합 평가 (필터 + 가격 + 명도 + 통합 점수)
        eval_result = self._rule_engine.evaluate(enriched, tenants=tenants)
        enriched.filter_result = eval_result.filter_result
        enriched.price_score = eval_result.price
        enriched.occupancy_score = eval_result.occupancy
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
                    self._db.commit()

                if is_update:
                    result.updated_count += 1
                else:
                    result.new_count += 1
                    # 신규 A/B등급 카운트
                    grade = enriched.total_score.grade if enriched.total_score else None
                    if grade == "A":
                        result.new_grade_a += 1
                    elif grade == "B":
                        result.new_grade_b += 1
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

    def _fetch_occupancy_tenants(
        self,
        court_office_code: str,
        property_sequence: str,
        formatted_case_number: str,
    ) -> list | None:
        """현황조사서에서 임차인 DTO 목록 추출 (fail-open)

        Returns:
            list: 임차인 목록 (빈 리스트 = 임차인 없음 → scorer 호출됨)
            None: 현황조사서 자체가 없음 → scorer 스킵
        """
        try:
            from app.services.occupancy.parser import OccupancyParser

            raw = self._crawler.fetch_occupancy_report(
                case_number=formatted_case_number,
                court_office_code=court_office_code,
                property_sequence=property_sequence,
            )
            if not raw:
                logger.info("현황조사서 빈 응답: %s", formatted_case_number)
                return None
            # v2(실제 API): dlt_ordTsLserLtn, v1(legacy): dlt_curstExmndcDtl
            has_tenants = (
                "dlt_ordTsLserLtn" in raw or "dlt_curstExmndcDtl" in raw
            )
            if not has_tenants:
                logger.info(
                    "현황조사서 임차인 키 없음: %s (keys=%s)",
                    formatted_case_number, list(raw.keys()),
                )
                return None
            parser = OccupancyParser()
            dto = parser.parse(raw, formatted_case_number, court_office_code)
            logger.info(
                "현황조사서 파싱 완료: %s → 임차인 %d명",
                formatted_case_number, len(dto.tenants),
            )
            return dto.tenants
        except Exception as e:
            logger.warning(
                "현황조사서 수집 실패 [%s]: %s", formatted_case_number, e
            )
        return None

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
            grade_provisional=ts.grade_provisional,
            sub_scores=ts.weights_used,
            warnings=ts.warnings or None,
            needs_expert_review=ts.needs_expert_review,
            predicted_winning_ratio=ts.predicted_winning_ratio,
            prediction_method=ts.prediction_method,
            scorer_version=ts.scorer_version,
            pipeline_run_id=run_id,
        )
        self._db.add(score_orm)
        self._db.flush()

    # ──────────────────────────────────────────
    # DB 기반 재채점 모드
    # ──────────────────────────────────────────

    def rescore_db(
        self,
        *,
        court_code: str | None = None,
        coverage_below: float = 0.30,
        max_items: int = 0,
        enrich_delay: float = 2.0,
        dry_run: bool = False,
        skip_occupancy: bool = False,
        score_exists: bool = False,
        active_only: bool = True,
    ) -> BatchResult:
        """DB 기반 재채점 모드

        대법원 API 검색 없이 DB에서 직접 물건을 가져와 재채점한다.
        score_coverage < coverage_below 인 물건만 처리.

        Args:
            court_code: 특정 법원만 처리 (None=전체)
            coverage_below: 이 값 미만의 coverage를 가진 물건만 재채점 (0~1)
            max_items: 최대 처리 건수 (0=전체)
            enrich_delay: 물건 간 대기 시간 (초)
            dry_run: True면 DB 저장 없이 채점만
            skip_occupancy: True면 현황조사서 조회 스킵
            score_exists: True면 Score가 이미 있는 물건만 처리 (Score 없는 건 제외)
            active_only: True면 매각 완료 물건 제외 (기본값 True)

        Returns:
            BatchResult
        """
        self._skip_occupancy = skip_occupancy
        now = datetime.now(timezone.utc)
        short_id = uuid.uuid4().hex[:8]
        label = court_code or "ALL"
        run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_RESCORE_{label}_{short_id}"

        result = BatchResult(
            run_id=run_id,
            court_code=f"RESCORE_{label}",
            started_at=now,
        )

        # PipelineRun 생성 (RUNNING)
        pipeline_run = None
        if not dry_run:
            pipeline_run = PipelineRun(
                run_id=run_id,
                court_code=f"RESCORE_{label}",
                started_at=now,
                status="RUNNING",
            )
            self._db.add(pipeline_run)
            self._db.commit()

        try:
            self._do_rescore_db(
                court_code=court_code,
                coverage_below=coverage_below,
                result=result,
                max_items=max_items,
                enrich_delay=enrich_delay,
                dry_run=dry_run,
                score_exists=score_exists,
                active_only=active_only,
            )
        except Exception as e:
            logger.error("DB 재채점 치명적 오류: %s", e)
            result.errors.append(f"치명적 오류: {e}")

        result.finished_at = datetime.now(timezone.utc)

        if pipeline_run and not dry_run:
            try:
                try:
                    self._db.rollback()
                except Exception:
                    pass
                pipeline_run.finished_at = result.finished_at
                pipeline_run.total_searched = result.total_searched
                pipeline_run.total_enriched = result.processed
                pipeline_run.total_filtered = result.processed
                pipeline_run.red_count = result.red_count
                pipeline_run.yellow_count = result.yellow_count
                pipeline_run.green_count = result.green_count
                pipeline_run.errors = result.errors or None
                pipeline_run.status = "COMPLETED"
                self._db.commit()
            except Exception as e:
                logger.error("PipelineRun 최종 커밋 실패 [%s]: %s", run_id, e)
                try:
                    self._db.rollback()
                except Exception:
                    pass

        logger.info(
            "DB 재채점 완료 [%s]: 대상=%d, 처리=%d, 업데이트=%d, 에러=%d",
            run_id,
            result.total_searched,
            result.processed,
            result.updated_count,
            len(result.errors),
        )
        return result

    def _do_rescore_db(
        self,
        court_code: str | None,
        coverage_below: float,
        result: BatchResult,
        *,
        max_items: int,
        enrich_delay: float,
        dry_run: bool,
        score_exists: bool = False,
        active_only: bool = True,
    ) -> None:
        """DB 재채점 루프"""
        # 목록 검색 없이 바로 상세조회하면 세션 쿠키가 없어 실패하므로 워밍업
        self._crawler.warm_up_session()

        if score_exists:
            # Score가 있는 물건 중 coverage 미달만 (INNER JOIN)
            query = (
                self._db.query(Auction)
                .join(Score, Auction.id == Score.auction_id)
                .filter(Score.score_coverage < coverage_below)
            )
        else:
            # Score 없는 건 포함 (OUTER JOIN)
            query = (
                self._db.query(Auction)
                .outerjoin(Score, Auction.id == Score.auction_id)
                .filter(
                    or_(Score.auction_id.is_(None), Score.score_coverage < coverage_below)
                )
            )
        if court_code:
            query = query.filter(Auction.court_office_code == court_code)
        if active_only:
            query = query.filter(Auction.status.notin_(["매각", "취하", "기각", "변경"]))

        total = query.count()
        result.total_searched = total
        result.total_pages = 1  # DB 모드에서는 페이지 없음

        logger.info(
            "DB 재채점 대상: %d건 (coverage < %.2f%s%s)",
            total,
            coverage_below,
            f", court={court_code}" if court_code else "",
            ", score_exists=True" if score_exists else "",
        )

        if max_items > 0:
            query = query.limit(max_items)

        auctions: list[Auction] = query.all()

        for i, auction_orm in enumerate(auctions):
            if i > 0:
                time.sleep(enrich_delay)

            try:
                self._rescore_single_from_db(
                    auction_orm=auction_orm,
                    result=result,
                    dry_run=dry_run,
                )
            except Exception as e:
                try:
                    self._db.rollback()
                except Exception:
                    pass
                logger.error("재채점 실패 [%s]: %s", auction_orm.case_number, e)
                result.errors.append(f"[{auction_orm.case_number}] {e}")

    def _rescore_single_from_db(
        self,
        auction_orm: Auction,
        result: BatchResult,
        *,
        dry_run: bool,
    ) -> None:
        """DB 물건 단건 재채점: ORM → 상세 복원 → (API 갱신 시도) → 보강 → 평가 → Score 저장"""
        # 1. DB에서 상세 복원
        detail = auction_orm_to_detail(auction_orm)

        # 2. 대법원 API로 최신 상세 데이터 갱신 시도 (fail-open)
        try:
            fresh = self._crawler.fetch_case_detail(
                case_number=detail.internal_case_number or detail.case_number,
                court_office_code=auction_orm.court_office_code or detail.court_office_code or "",
                property_sequence="1",
            )
            # property_type fallback
            if not fresh.property_type and detail.property_type:
                fresh.property_type = detail.property_type
            detail = fresh
            logger.debug("API 갱신 성공: %s", auction_orm.case_number)
        except Exception as e:
            logger.info(
                "API 갱신 스킵 (fail-open) [%s]: %s", auction_orm.case_number, e
            )

        # 3. 보강 + 현황조사서 + 통합 평가
        enriched = self._enricher.enrich(detail)

        tenants = None
        if not self._skip_occupancy:
            tenants = self._fetch_occupancy_tenants(
                court_office_code=auction_orm.court_office_code or detail.court_office_code or "",
                property_sequence="1",
                formatted_case_number=auction_orm.case_number,
            )

        eval_result = self._rule_engine.evaluate(enriched, tenants=tenants)
        enriched.filter_result = eval_result.filter_result
        enriched.price_score = eval_result.price
        enriched.occupancy_score = eval_result.occupancy
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

        # 4. 보강 데이터 + Score 저장 (per-case commit)
        if not dry_run:
            try:
                # 보강 데이터를 Auction ORM에 반영 (None이면 기존 값 유지)
                if enriched.coordinates is not None:
                    auction_orm.coordinates = enriched.coordinates
                if enriched.building is not None:
                    auction_orm.building_info = enriched.building.model_dump()
                if enriched.land_use is not None:
                    auction_orm.land_use_info = enriched.land_use.model_dump()
                if enriched.market_price is not None:
                    auction_orm.market_price_info = enriched.market_price.model_dump()
                if enriched.rent_price is not None:
                    auction_orm.rent_price_info = enriched.rent_price.model_dump()

                if enriched.total_score:
                    self._save_score(auction_orm.id, enriched, result.run_id)
                    self._db.commit()
                    result.updated_count += 1
                else:
                    self._db.commit()
                    result.skipped += 1
            except Exception as e:
                self._db.rollback()
                raise RuntimeError(f"Score 저장 실패: {e}") from e
        else:
            if not enriched.total_score:
                result.skipped += 1

        logger.info(
            "재채점 완료 [%s]: coverage=%.2f grade=%s%s",
            auction_orm.case_number,
            enriched.total_score.score_coverage if enriched.total_score else 0.0,
            enriched.total_score.grade if enriched.total_score else "-",
            " (dry-run)" if dry_run else "",
        )
