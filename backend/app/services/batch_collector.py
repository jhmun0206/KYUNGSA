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
from datetime import date as date_type, datetime, timezone

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
from app.services.property_normalizer import normalize_property_type
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

        # 배치 시작 시 기일경과 상태 자동 처리
        if not dry_run:
            self._update_overdue_status()

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

    def _update_overdue_status(self) -> None:
        """매각기일이 지났는데 진행 상태인 물건을 기일경과로 변경"""
        try:
            overdue = self._db.query(Auction).filter(
                Auction.status == "진행",
                Auction.auction_date < date_type.today(),
                Auction.auction_date.isnot(None),
            ).all()
            for a in overdue:
                a.status = "기일경과"
            if overdue:
                self._db.commit()
                logger.info("기일경과 처리: %d건", len(overdue))
        except Exception as e:
            logger.error("기일경과 처리 실패: %s", e)
            try:
                self._db.rollback()
            except Exception:
                pass

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
        status_filter: str | None = None,
        missing_location_only: bool = False,
        missing_building_info_only: bool = False,
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
            status_filter: 특정 status 물건만 처리 (예: "진행", None=전체)
            missing_location_only: True면 location_data IS NULL AND lat IS NOT NULL 인 물건만

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
                status_filter=status_filter,
                missing_location_only=missing_location_only,
                missing_building_info_only=missing_building_info_only,
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
        status_filter: str | None = None,
        missing_location_only: bool = False,
        missing_building_info_only: bool = False,
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
        if status_filter:
            query = query.filter(Auction.status == status_filter)
        if missing_location_only:
            # location_data IS NULL AND lat IS NOT NULL (좌표 있는데 입지 데이터 없는 건만)
            query = query.filter(
                Auction.location_data.is_(None),
                Auction.lat.isnot(None),
            )
        if missing_building_info_only:
            from sqlalchemy import func, text as sa_text
            # building_info IS NULL OR jsonb_typeof(building_info) != 'object'
            query = query.filter(
                Auction.status == "진행",
            ).filter(
                (Auction.building_info.is_(None)) |
                (func.jsonb_typeof(Auction.building_info) != "object")
            )

        total = query.count()
        result.total_searched = total
        result.total_pages = 1  # DB 모드에서는 페이지 없음

        logger.info(
            "DB 재채점 대상: %d건 (coverage < %.2f%s%s%s%s)",
            total,
            coverage_below,
            f", court={court_code}" if court_code else "",
            ", score_exists=True" if score_exists else "",
            ", missing_location=True" if missing_location_only else "",
            ", missing_building_info=True" if missing_building_info_only else "",
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
                # JSONB + 정규화 컬럼 업데이트 (DB-REBUILD: BUG-01/BUG-02 fix)
                if enriched.coordinates is not None:
                    auction_orm.coordinates = enriched.coordinates
                    coords = enriched.coordinates
                    if isinstance(coords, dict):
                        try:
                            lng_val = coords.get("x") or coords.get("lng")
                            lat_val = coords.get("y") or coords.get("lat")
                            if lng_val is not None:
                                auction_orm.lng = float(lng_val)
                            if lat_val is not None:
                                auction_orm.lat = float(lat_val)
                        except (ValueError, TypeError):
                            pass
                if enriched.building is not None:
                    auction_orm.building_info = enriched.building.model_dump()
                    b = enriched.building
                    if b.building_type is not None:
                        auction_orm.building_type = b.building_type
                    if b.build_year is not None:
                        auction_orm.build_year = b.build_year
                    if b.exclusive_area_m2_real is not None:
                        auction_orm.exclusive_area_m2_real = b.exclusive_area_m2_real
                    if b.ground_floors is not None:
                        auction_orm.floor_count = b.ground_floors
                    if b.units_count is not None:
                        auction_orm.units_count_real = b.units_count
                if enriched.land_use is not None:
                    auction_orm.land_use_info = enriched.land_use.model_dump()
                if enriched.market_price is not None:
                    auction_orm.market_price_info = enriched.market_price.model_dump()
                if enriched.rent_price is not None:
                    auction_orm.rent_price_info = enriched.rent_price.model_dump()
                if enriched.location_data is not None:
                    auction_orm.location_data = enriched.location_data.model_dump()
                    if enriched.location_data.nearest_station_m is not None:
                        auction_orm.station_distance_m = enriched.location_data.nearest_station_m
                else:
                    # geocode 실패해도 기존 lat/lng 있으면 location_data 수집 시도
                    if auction_orm.lat and auction_orm.lng:
                        try:
                            loc = self._enricher._fetch_location_data(
                                str(auction_orm.lng),  # x = 경도
                                str(auction_orm.lat),  # y = 위도
                            )
                            if loc is not None:
                                auction_orm.location_data = loc.model_dump()
                                if loc.nearest_station_m is not None:
                                    auction_orm.station_distance_m = loc.nearest_station_m
                        except Exception as e:
                            logger.debug(
                                "location_data fallback 실패 [%s]: %s",
                                auction_orm.case_number, e,
                            )
                # property_category + current_round 동기화
                if enriched.case.property_type:
                    auction_orm.property_category = normalize_property_type(
                        enriched.case.property_type
                    )
                if enriched.case.bid_count is not None:
                    auction_orm.current_round = enriched.case.bid_count

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

    # ──────────────────────────────────────────
    # 역 이름/호선 보완 모드
    # ──────────────────────────────────────────

    def update_station_names(
        self,
        *,
        max_items: int = 0,
        delay: float = 0.3,
        dry_run: bool = False,
        court_code: str | None = None,
    ) -> dict:
        """기존 DB 물건의 역 이름/호선 정보 보완

        location_data에 nearest_station_m 있지만 nearest_station_name 없는 물건을
        Kakao SW8 API 재호출로 이름/호선 채운다.

        Args:
            max_items: 최대 처리 건수 (0=전체)
            delay: 물건 간 대기 시간 (초, 카카오 API rate limit 방지)
            dry_run: True면 DB 저장 없이 결과만 출력
            court_code: 특정 법원만 처리 (None=전체)
        """
        from sqlalchemy import func, text

        query = self._db.query(Auction).filter(
            Auction.station_distance_m.isnot(None),
            Auction.lat.isnot(None),
            Auction.lng.isnot(None),
        )
        if court_code:
            query = query.filter(Auction.court_office_code == court_code)

        auctions = query.all()

        # nearest_station_name 없는 것만 필터 (JSONB key 부재)
        targets = [
            a for a in auctions
            if isinstance(a.location_data, dict)
            and a.location_data.get("nearest_station_name") is None
        ]

        total = len(targets)
        if max_items > 0:
            targets = targets[:max_items]

        logger.info("역 이름 보완 대상: %d건 (전체 후보 %d건)%s", len(targets), total, " [dry-run]" if dry_run else "")

        updated = 0
        skipped = 0
        errors = 0

        for i, auction in enumerate(targets, 1):
            try:
                # x=경도(lng), y=위도(lat) — Kakao 좌표계
                stations = self._enricher._geo.search_nearby_category(
                    str(auction.lng), str(auction.lat), "SW8", radius=2000
                )
                if not stations:
                    skipped += 1
                    continue

                nearest = min(stations, key=lambda p: int(p.get("distance", 0)))
                name = nearest.get("place_name") or None
                category = nearest.get("category_name", "")
                line = category.split(">")[-1].strip() if ">" in category else None
                line = line or None

                if not dry_run:
                    new_loc = {**(auction.location_data or {}), "nearest_station_name": name, "nearest_station_line": line}
                    auction.location_data = new_loc
                    if (i % 50) == 0:
                        self._db.commit()

                updated += 1
                logger.info("[%d/%d] %s → %s (%s)", i, len(targets), auction.case_number, name, line)

                if delay > 0:
                    time.sleep(delay)

            except Exception as e:
                errors += 1
                logger.warning("역 이름 보완 실패 [%s]: %s", auction.case_number, e)

        if not dry_run and (updated % 50) != 0:
            try:
                self._db.commit()
            except Exception as e:
                self._db.rollback()
                logger.error("최종 commit 실패: %s", e)

        result = {"updated": updated, "skipped": skipped, "errors": errors, "dry_run": dry_run}
        logger.info("역 이름 보완 완료: %s", result)
        return result

    def fix_duplicate_units(
        self,
        court_code: str | None = None,
        max_items: int = 0,
        dry_run: bool = False,
    ) -> dict:
        """building_info.units 중복 제거 (floor=0 전유부 행 제거, ho 기준 중복 dedup).

        getBrExposPubuseAreaInfo API가 전유/공용 두 행씩 반환하는 버그로
        수집된 floor=0 중복 데이터를 in-place 정리한다.
        ho_nm 기준 중복은 area_m2가 큰 행(공용/층정보 있는 행)만 남긴다.
        """
        from sqlalchemy import text

        # floor=0 인 units 행이 있는 물건 조회 (PostgreSQL JSONB)
        sql = text("""
            SELECT id FROM auctions
            WHERE building_info IS NOT NULL
              AND building_info->'units' IS NOT NULL
              AND jsonb_array_length(building_info->'units') > 0
              AND EXISTS (
                  SELECT 1 FROM jsonb_array_elements(building_info->'units') u
                  WHERE (u->>'floor')::int = 0
              )
            {}
            {}
        """.format(
            "AND court_office_code = :court_code" if court_code else "",
            f"LIMIT {max_items}" if max_items > 0 else "",
        ))
        params = {"court_code": court_code} if court_code else {}
        rows = self._db.execute(sql, params).fetchall()
        ids = [r[0] for r in rows]

        total = len(ids)
        logger.info(
            "중복 units 대상: %d건%s%s",
            total,
            f" (court={court_code})" if court_code else "",
            " [dry-run]" if dry_run else "",
        )

        updated = 0
        skipped = 0
        errors = 0

        for auction_id in ids:
            try:
                auction = self._db.query(Auction).filter(Auction.id == auction_id).one()
                building_info = auction.building_info
                if not building_info or not building_info.get("units"):
                    skipped += 1
                    continue

                units: list[dict] = building_info["units"]
                # ho 기준 중복 제거: area_m2 큰 행 유지
                seen: dict[str, dict] = {}
                for u in units:
                    ho = str(u.get("ho") or "").strip()
                    area = u.get("area_m2") or 0.0
                    if not ho:
                        continue
                    existing = seen.get(ho)
                    if existing is None or area > existing.get("area_m2", 0):
                        seen[ho] = u

                deduped = sorted(seen.values(), key=lambda x: (x.get("floor", 0), x.get("ho", "")))

                if len(deduped) == len(units):
                    skipped += 1
                    continue

                logger.info(
                    "%s: units %d → %d건",
                    auction.case_number, len(units), len(deduped),
                )

                if not dry_run:
                    new_building_info = {**building_info, "units": deduped}
                    auction.building_info = new_building_info
                    self._db.commit()

                updated += 1

            except Exception as e:
                try:
                    self._db.rollback()
                except Exception:
                    pass
                logger.error("중복 units 수정 실패 [%s]: %s", auction_id, e)
                errors += 1

        result = {"total": total, "updated": updated, "skipped": skipped, "errors": errors, "dry_run": dry_run}
        logger.info("중복 units 수정 완료: %s", result)
        return result
