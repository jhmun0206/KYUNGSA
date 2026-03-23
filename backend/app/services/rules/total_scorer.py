"""통합 점수 합산기 (5E)

개별 pillar 점수를 가중 합산하여 최종 점수와 등급을 산출한다.
I/O 없음 — 순수 계산 로직만 포함.

핵심:
  - 가용 pillar만으로 가중합 + 가중치 재정규화 (Partial Score)
  - 유형별 가중치 (아파트/꼬마빌딩/토지)
  - 등급: A(80+) / B(60~80) / C(40~60) / D(<40)
  - score_coverage: 원래 가중치 중 가용 pillar가 차지하는 비율 (0~1.0)

=== 신뢰도 설계 원칙 (Phase 5.5 명문화) ===
1. 신뢰도 감쇠(confidence_multiplier)는 각 pillar 내부에서만 적용한다.
   - LegalScorer:  HIGH=1.0, MEDIUM=0.8,  LOW=0.6
   - PriceScorer:  HIGH=1.0, MEDIUM=0.85, LOW=0.7
   - LocationScorer (Phase 6), OccupancyScorer (Phase 7): 별도 결정

2. TotalScorer는 신뢰도 감쇠를 하지 않는다. 재정규화만 수행한다.
   이유: pillar 내부에서 이미 감쇠된 점수를 TotalScorer가 또 감쇠하면
         이중 페널티가 발생한다.

3. 대신 TotalScorer는 score_coverage와 경고로만 신뢰도를 표현한다.
   - coverage < 0.70 → "점수 커버리지 낮음" 경고
   - 이 원칙은 Phase 6/7 pillar 추가 후에도 유지한다.
==="""

from __future__ import annotations

import logging

from app.models.scores import TotalScoreResult

logger = logging.getLogger(__name__)

# 유형별 4-pillar 가중치 (합=1.0)
PILLAR_WEIGHTS: dict[str, dict[str, float]] = {
    "아파트": {"legal": 0.20, "price": 0.25, "location": 0.30, "occupancy": 0.25},
    "꼬마빌딩": {"legal": 0.35, "price": 0.20, "location": 0.15, "occupancy": 0.30},
    "토지": {"legal": 0.25, "price": 0.15, "location": 0.50, "occupancy": 0.10},
}

DEFAULT_CATEGORY = "꼬마빌딩"

SCORER_VERSION = "v1.0"
PREDICTION_METHOD = "rule_v1"

# property_type → category 매핑
_APARTMENT_TYPES = frozenset({"아파트", "오피스텔", "주상복합", "연립", "빌라"})
_LAND_TYPES = frozenset({"토지", "임야", "전", "답", "대지"})

# rule_v1: 유찰 횟수별 예측 낙찰가율 (통계 중앙값 기반)
# 출처: Phase 5F 백테스트 + 2026-03-22 전체 재캘리브레이션 (서울 5개 법원 실측)
#   아파트:   0유찰 1,473건 실측 1.034 → 1.030, 1유찰 실측 0.850, 2유찰 0.681, 3유찰 0.593, 4+유찰 0.448
#   꼬마빌딩: 0유찰 5,127건 실측 1.019 → 1.020, 1유찰 실측 0.810, 2유찰 0.611, 3유찰 0.477, 4+유찰 0.289
#   토지:     0유찰 54건 실측 1.088 → 1.090  # 주의: 54건, 신뢰도 낮음 — 추후 재검토
#             1유찰 실측 0.736, 2유찰 0.564, 3유찰 0.385, 4+유찰 0.243
_PREDICTED_RATIO_TABLE: dict[str, list[float]] = {
    #            0유찰  1유찰  2유찰  3유찰  4유찰+
    "아파트":   [1.030, 0.850, 0.680, 0.590, 0.450],
    "꼬마빌딩": [1.020, 0.810, 0.610, 0.480, 0.290],
    "토지":     [1.090, 0.740, 0.560, 0.390, 0.240],  # 0유찰 54건, 신뢰도 낮음
}


class TotalScorer:
    """통합 점수 합산기"""

    def score(
        self,
        property_type: str,
        *,
        legal_score: float | None = None,
        price_score: float | None = None,
        location_score: float | None = None,
        occupancy_score: float | None = None,
        needs_expert_review: bool = False,
        fail_count: int = 0,
        # WinningBidPredictor용 선택적 파라미터 (있으면 ML 예측, 없으면 rule_v1)
        appraised_value: int | None = None,
        minimum_bid: int | None = None,
        court_office_code: str = "",
        address: str = "",
        rolling_avg: float | None = None,
        rolling_count: int | None = None,
        tenant_count: int = 0,
        total_deposit: int = 0,
    ) -> TotalScoreResult:
        """통합 점수 산출

        Args:
            property_type: 물건 유형 (예: "아파트", "상가", "토지")
            legal_score: 법률 리스크 점수 (0~100)
            price_score: 가격 매력도 점수 (0~100)
            location_score: 입지 점수 (0~100) — Phase 6
            occupancy_score: 명도 리스크 점수 (0~100) — Phase 7
            needs_expert_review: 전문가 검토 필요 여부 (pillar에서 전달)
            fail_count: 유찰 횟수 (bid_count - 1). predicted_winning_ratio 산출에 사용.
            appraised_value: 감정가 (원). WinningBidPredictor 호출 시 필수.
            minimum_bid: 최저입찰가 (원). WinningBidPredictor 호출 시 필수.
            court_office_code: 법원코드. WinningBidPredictor 선택 파라미터.
            address: 소재지 주소. WinningBidPredictor 선택 파라미터.
            rolling_avg: 유사 물건 3개월 평균 낙찰가율. WinningBidPredictor 선택 파라미터.
            rolling_count: 유사 물건 3개월 건수. WinningBidPredictor 선택 파라미터.
            tenant_count: 임차인 수. WinningBidPredictor 선택 파라미터.
            total_deposit: 총 보증금 (원). WinningBidPredictor 선택 파라미터.

        Returns:
            TotalScoreResult
        """
        warnings: list[str] = []

        # 1. 유형 분류
        category = self._classify_property(property_type)

        # 2. 가용 pillar 수집
        available: dict[str, float] = {}
        pillar_scores: dict[str, float] = {}

        if legal_score is not None:
            available["legal"] = PILLAR_WEIGHTS[category]["legal"]
            pillar_scores["legal"] = legal_score
        if price_score is not None:
            available["price"] = PILLAR_WEIGHTS[category]["price"]
            pillar_scores["price"] = price_score
        if location_score is not None:
            available["location"] = PILLAR_WEIGHTS[category]["location"]
            pillar_scores["location"] = location_score
        if occupancy_score is not None:
            available["occupancy"] = PILLAR_WEIGHTS[category]["occupancy"]
            pillar_scores["occupancy"] = occupancy_score

        # missing pillars
        all_pillars = {"legal", "price", "location", "occupancy"}
        missing = sorted(all_pillars - set(available.keys()))

        # 3. coverage 계산 (원래 가중치 합 대비 가용 가중치 합)
        score_coverage = sum(available.values())

        if score_coverage < 0.70:
            warnings.append(f"점수 커버리지 낮음 ({score_coverage:.0%}) — 해석 주의")

        # 4. 가중치 재정규화
        normalized = self._normalize_weights(available)

        # 5. 가중 합산
        if not pillar_scores:
            total_score = 0.0
            warnings.append("가용 pillar 없음 — 점수 산출 불가")
        else:
            total_score = sum(
                pillar_scores[name] * normalized[name]
                for name in pillar_scores
            )
            total_score = round(total_score, 1)

        # 6. 등급 부여 + 잠정 여부 (coverage < 0.70)
        grade = self._assign_grade(total_score)
        grade_provisional = score_coverage < 0.70

        # 7. 예측 낙찰가율: WinningBidPredictor 우선, rule_v1 fallback
        predicted_ratio, prediction_method = self._calc_predicted_ratio_with_ml(
            category=category,
            fail_count=fail_count,
            appraised_value=appraised_value,
            minimum_bid=minimum_bid,
            property_type=property_type,
            court_office_code=court_office_code,
            address=address,
            rolling_avg=rolling_avg,
            rolling_count=rolling_count,
            tenant_count=tenant_count,
            total_deposit=total_deposit,
        )

        return TotalScoreResult(
            total_score=total_score,
            score_coverage=round(score_coverage, 4),
            missing_pillars=missing,
            grade=grade,
            grade_provisional=grade_provisional,
            property_category=category,
            weights_used={k: round(v, 4) for k, v in normalized.items()},
            legal_score=legal_score,
            price_score=price_score,
            location_score=location_score,
            occupancy_score=occupancy_score,
            warnings=warnings,
            needs_expert_review=needs_expert_review,
            scorer_version=SCORER_VERSION,
            predicted_winning_ratio=predicted_ratio,
            prediction_method=prediction_method,
        )

    @staticmethod
    def _classify_property(property_type: str) -> str:
        """물건 유형 → 카테고리 (아파트/꼬마빌딩/토지)"""
        if not property_type:
            return DEFAULT_CATEGORY

        for keyword in _APARTMENT_TYPES:
            if keyword in property_type:
                return "아파트"
        for keyword in _LAND_TYPES:
            if keyword in property_type:
                return "토지"

        # 그 외 (상가, 근린, 다가구 등) → 꼬마빌딩 (보수적)
        return "꼬마빌딩"

    @staticmethod
    def _normalize_weights(available: dict[str, float]) -> dict[str, float]:
        """가용 pillar 가중치 재정규화 (합=1.0)"""
        total = sum(available.values())
        if total == 0:
            return {}
        return {name: weight / total for name, weight in available.items()}

    @staticmethod
    def _assign_grade(total_score: float) -> str:
        """총점 → 등급"""
        if total_score >= 80:
            return "A"
        if total_score >= 60:
            return "B"
        if total_score >= 40:
            return "C"
        return "D"

    @staticmethod
    def _calc_predicted_ratio(category: str, fail_count: int) -> float:
        """예측 낙찰가율 산출 (rule_v1 — 유찰 횟수 기반 통계값)

        Phase 5F 백테스트에서 실데이터 기반으로 교체될 초기값.
        4회 이상 유찰은 마지막 값(인덱스 4)으로 클램프.
        ※ predictor.py의 _predict_rule_v1에서도 호출됨. 시그니처 변경 금지.
        """
        table = _PREDICTED_RATIO_TABLE.get(category, _PREDICTED_RATIO_TABLE[DEFAULT_CATEGORY])
        idx = min(fail_count, len(table) - 1)
        return table[idx]

    @staticmethod
    def _calc_predicted_ratio_with_ml(
        *,
        category: str,
        fail_count: int,
        appraised_value: int | None,
        minimum_bid: int | None,
        property_type: str,
        court_office_code: str,
        address: str,
        rolling_avg: float | None,
        rolling_count: int | None,
        tenant_count: int,
        total_deposit: int,
    ) -> tuple[float, str]:
        """예측 낙찰가율 + prediction_method 반환.

        appraised_value/minimum_bid가 제공되면 WinningBidPredictor를 호출한다.
        ML 모델이 없으면 predictor 내부에서 rule_v1로 자동 fallback.
        파라미터 부족 또는 예외 시 rule_v1 테이블 직접 조회.
        지연 임포트(lazy import)로 순환 참조 방지.
        """
        if appraised_value is not None and minimum_bid is not None:
            try:
                from app.services.prediction.predictor import WinningBidPredictor  # noqa: PLC0415
                predictor = WinningBidPredictor.get_instance()
                result = predictor.predict(
                    appraised_value=appraised_value,
                    minimum_bid=minimum_bid,
                    fail_count=fail_count,
                    property_type=property_type,
                    court_office_code=court_office_code,
                    address=address,
                    rolling_avg=rolling_avg,
                    rolling_count=rolling_count,
                    tenant_count=tenant_count,
                    total_deposit=total_deposit,
                )
                return result.predicted_ratio, result.model_version
            except Exception as exc:
                logger.warning("WinningBidPredictor 호출 실패, rule_v1 fallback: %s", exc)

        # rule_v1 fallback: 유찰 횟수 기반 테이블 조회
        table = _PREDICTED_RATIO_TABLE.get(category, _PREDICTED_RATIO_TABLE[DEFAULT_CATEGORY])
        idx = min(fail_count, len(table) - 1)
        return table[idx], PREDICTION_METHOD
