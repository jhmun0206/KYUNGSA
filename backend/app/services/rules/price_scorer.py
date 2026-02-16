"""가격 매력도 점수 엔진 (5D)

경매 물건 정보(AuctionCaseDetail)와 시세 데이터(MarketPriceInfo)를
입력받아 가격 매력도 점수(0~100, 높을수록 좋은 거래)를 산출한다.

구조: 3축 가중 합산 × 신뢰도 계수 (동적 가중치)
  시세 있을 때: base = discount*0.15 + market*0.55 + appraisal*0.30
  시세 없을 때: base = discount*0.60 + appraisal*0.40
  final_score = base_score × confidence_multiplier

근거:
  - 할인율과 시세대비는 감정가≈시세일 때 double counting → 동적 가중치로 해소.
  - 아파트/꼬마빌딩 낙찰가율 차이 반영 (아파트 90%, 꼬마빌딩 70~80%).
  - 감정가 고평가 시 할인율 과대 계상 함정 → 비대칭 보정(×0.8).
"""

from __future__ import annotations

import logging

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import MarketPriceInfo
from app.models.scores import PriceScoreResult, PriceSubScores

logger = logging.getLogger(__name__)


class PriceScorer:
    """가격 매력도 점수 산출기"""

    # 시세 있을 때 가중치
    W_DISCOUNT_WITH_MARKET = 0.15
    W_MARKET = 0.55
    W_APPRAISAL_WITH_MARKET = 0.30

    # 시세 없을 때 가중치
    W_DISCOUNT_NO_MARKET = 0.60
    W_APPRAISAL_NO_MARKET = 0.40

    # 신뢰도 계수
    CONFIDENCE_MULTIPLIER: dict[str, float] = {
        "HIGH": 1.0,
        "MEDIUM": 0.85,
        "LOW": 0.7,
    }

    # 주거용 property_type 키워드 (LegalScorer와 동일)
    RESIDENTIAL_TYPES = frozenset(
        {"아파트", "오피스텔", "주상복합", "연립", "빌라", "주택"}
    )

    # 감정가 고평가 보정 계수
    OVERVALUED_PENALTY = 0.8

    def score(
        self,
        case: AuctionCaseDetail,
        market_price: MarketPriceInfo | None = None,
    ) -> PriceScoreResult:
        """가격 매력도 점수 산출

        Args:
            case: 경매 물건 상세 정보
            market_price: 실거래가 시세 정보 (없을 수 있음)

        Returns:
            PriceScoreResult (0~100, 높을수록 좋은 거래)
        """
        warnings: list[str] = []
        details: dict = {}

        appraised = case.appraised_value
        minimum_bid = case.minimum_bid
        area_m2 = case.area_m2
        is_residential = self._is_residential(case.property_type)

        details["property_type"] = case.property_type
        details["is_residential"] = is_residential
        details["appraised_value"] = appraised
        details["minimum_bid"] = minimum_bid

        # 엣지케이스: 감정가/최저가 0 또는 음수
        if appraised <= 0 or minimum_bid <= 0:
            reason = (
                "감정가 미확인"
                if appraised <= 0
                else "최저가 0원 — 데이터 이상"
            )
            warnings.append(reason)
            return PriceScoreResult(
                score=0.0,
                base_score=0.0,
                sub_scores=PriceSubScores(),
                confidence_multiplier=0.7,
                confidence="LOW",
                has_market_data=False,
                is_residential=is_residential,
                warnings=warnings,
                details=details,
            )

        # --- (1) 할인율 점수 ---
        discount_score, discount_detail, discount_warnings = (
            self._calc_discount_score(minimum_bid, appraised)
        )
        warnings.extend(discount_warnings)
        details["discount"] = discount_detail

        # --- 시세 추정 ---
        estimated_market = self._estimate_market_value(market_price, area_m2)
        has_market_data = (
            estimated_market is not None and estimated_market > 0
        )
        details["estimated_market"] = estimated_market
        details["has_market_data"] = has_market_data

        # --- (2) 시세 대비 점수 ---
        if has_market_data:
            market_score, market_detail = self._calc_market_compare_score(
                minimum_bid, estimated_market, is_residential
            )
        else:
            market_score = 0.0
            market_detail = {"reason": "시세 데이터 없음"}
            warnings.append("시세 데이터 없음 — 시세 대비 점수 산출 불가")
        details["market_compare"] = market_detail

        # --- (3) 감정가 신뢰도 점수 ---
        if has_market_data:
            appraisal_score, appraisal_detail = (
                self._calc_appraisal_accuracy_score(appraised, estimated_market)
            )
        else:
            appraisal_score = 50.0  # 중립
            appraisal_detail = {"reason": "시세 데이터 없음", "score": 50.0}
        details["appraisal_accuracy"] = appraisal_detail

        # --- 동적 가중치 합산 ---
        if has_market_data:
            base_score = (
                discount_score * self.W_DISCOUNT_WITH_MARKET
                + market_score * self.W_MARKET
                + appraisal_score * self.W_APPRAISAL_WITH_MARKET
            )
            weights_used = {
                "discount": self.W_DISCOUNT_WITH_MARKET,
                "market": self.W_MARKET,
                "appraisal": self.W_APPRAISAL_WITH_MARKET,
            }
        else:
            base_score = (
                discount_score * self.W_DISCOUNT_NO_MARKET
                + appraisal_score * self.W_APPRAISAL_NO_MARKET
            )
            weights_used = {
                "discount": self.W_DISCOUNT_NO_MARKET,
                "appraisal": self.W_APPRAISAL_NO_MARKET,
            }
        details["weights_used"] = weights_used
        base_score = round(base_score, 1)

        # --- 신뢰도 계수 ---
        confidence = self._determine_confidence(market_price, area_m2)
        multiplier = self.CONFIDENCE_MULTIPLIER[confidence]

        final_score = round(base_score * multiplier, 1)
        final_score = max(0.0, min(100.0, final_score))

        return PriceScoreResult(
            score=final_score,
            base_score=base_score,
            sub_scores=PriceSubScores(
                discount_score=discount_score,
                market_compare_score=market_score,
                appraisal_accuracy_score=appraisal_score,
            ),
            confidence_multiplier=multiplier,
            confidence=confidence,
            has_market_data=has_market_data,
            is_residential=is_residential,
            warnings=warnings,
            details=details,
        )

    # ──────────────────────────────────────
    # 세부 점수 계산
    # ──────────────────────────────────────

    @staticmethod
    def _calc_discount_score(
        minimum_bid: int,
        appraised_value: int,
    ) -> tuple[float, dict, list[str]]:
        """할인율 점수 (0~100)

        discount_rate = 1 - (minimum_bid / appraised_value)

        ≤ 0.00: 20
        0.00 → 0.20: 20 → 55
        0.20 → 0.36: 55 → 68
        0.36 → 0.49: 68 → 82
        0.49 → 0.60: 82 → 93
        0.60 → 1.00: 93 → 100
        """
        warnings: list[str] = []
        detail: dict = {}

        if appraised_value <= 0:
            detail["reason"] = "감정가 0 이하"
            return 0.0, detail, ["감정가 미확인"]

        if minimum_bid <= 0:
            detail["reason"] = "최저가 0 이하"
            return 0.0, detail, ["최저가 0원 — 데이터 이상"]

        discount_rate = 1.0 - (minimum_bid / appraised_value)

        if discount_rate < 0:
            discount_rate = 0.0
            warnings.append("최저가가 감정가 초과")

        detail["discount_rate"] = round(discount_rate, 4)

        score = _lerp_discount(discount_rate)
        score = round(score, 1)
        detail["score"] = score

        return score, detail, warnings

    @staticmethod
    def _calc_market_compare_score(
        minimum_bid: int,
        estimated_market: float,
        is_residential: bool,
    ) -> tuple[float, dict]:
        """시세 대비 점수 (0~100)

        market_ratio = minimum_bid / estimated_market
        아파트/꼬마빌딩 곡선 분리.
        """
        detail: dict = {}

        market_ratio = minimum_bid / estimated_market
        detail["market_ratio"] = round(market_ratio, 4)
        detail["is_residential"] = is_residential

        if is_residential:
            score = _lerp_market_residential(market_ratio)
        else:
            score = _lerp_market_commercial(market_ratio)

        score = max(0.0, min(100.0, round(score, 1)))
        detail["score"] = score

        return score, detail

    @staticmethod
    def _calc_appraisal_accuracy_score(
        appraised_value: int,
        estimated_market: float,
    ) -> tuple[float, dict]:
        """감정가 신뢰도 점수 (0~100)

        gap_ratio = |appraised - estimated_market| / estimated_market
        고평가(감정가 > 시세) × 0.8 비대칭 보정.
        """
        detail: dict = {}

        gap_ratio = abs(appraised_value - estimated_market) / estimated_market
        detail["gap_ratio"] = round(gap_ratio, 4)

        is_overvalued = appraised_value > estimated_market
        detail["gap_direction"] = (
            "overvalued" if is_overvalued else "undervalued"
        )

        raw_score = _lerp_appraisal_gap(gap_ratio)

        if is_overvalued:
            adjusted_score = raw_score * 0.8
        else:
            adjusted_score = raw_score

        adjusted_score = max(0.0, min(100.0, round(adjusted_score, 1)))
        detail["raw_score"] = round(raw_score, 1)
        detail["score"] = adjusted_score

        return adjusted_score, detail

    @staticmethod
    def _determine_confidence(
        market_price: MarketPriceInfo | None,
        area_m2: float | None,
    ) -> str:
        """신뢰도 결정

        HIGH:   market_price + trade_count ≥ 10 + area_m2
        MEDIUM: market_price + trade_count ≥ 5  + area_m2
        LOW:    그 외
        """
        if market_price is None:
            return "LOW"
        if market_price.avg_price_per_m2 is None:
            return "LOW"
        if area_m2 is None or area_m2 <= 0:
            return "LOW"
        if market_price.trade_count >= 10:
            return "HIGH"
        if market_price.trade_count >= 5:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _estimate_market_value(
        market_price: MarketPriceInfo | None,
        area_m2: float | None,
    ) -> float | None:
        """추정 시세 = avg_price_per_m2 × area_m2"""
        if market_price is None:
            return None
        if market_price.avg_price_per_m2 is None:
            return None
        if area_m2 is None or area_m2 <= 0:
            return None
        return market_price.avg_price_per_m2 * area_m2

    @classmethod
    def _is_residential(cls, property_type: str) -> bool:
        """주거용 물건 여부 판별

        판별 불가 시 False (보수적으로 꼬마빌딩 곡선 적용).
        """
        if not property_type:
            return False
        for rtype in cls.RESIDENTIAL_TYPES:
            if rtype in property_type:
                return True
        return False


# ──────────────────────────────────────
# 선형 보간 헬퍼 (모듈 내부)
# ──────────────────────────────────────


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """선형 보간: x가 [x0, x1] 구간에서 y를 [y0, y1] 사이로 보간"""
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def _lerp_discount(discount_rate: float) -> float:
    """할인율 곡선

    ≤ 0.00: 20
    0.00 → 0.20: 20 → 55
    0.20 → 0.36: 55 → 68
    0.36 → 0.49: 68 → 82
    0.49 → 0.60: 82 → 93
    0.60 → 1.00: 93 → 100
    """
    if discount_rate <= 0.0:
        return 20.0
    if discount_rate <= 0.20:
        return _lerp(discount_rate, 0.0, 0.20, 20.0, 55.0)
    if discount_rate <= 0.36:
        return _lerp(discount_rate, 0.20, 0.36, 55.0, 68.0)
    if discount_rate <= 0.49:
        return _lerp(discount_rate, 0.36, 0.49, 68.0, 82.0)
    if discount_rate <= 0.60:
        return _lerp(discount_rate, 0.49, 0.60, 82.0, 93.0)
    # 0.60 → 1.00: 93 → 100
    return min(100.0, _lerp(discount_rate, 0.60, 1.00, 93.0, 100.0))


def _lerp_market_residential(market_ratio: float) -> float:
    """아파트 시세대비 곡선

    ≤ 0.40: 95 (캡 — 하자 가능성)
    0.40 → 0.60: 95 → 85
    0.60 → 0.70: 85 → 75
    0.70 → 0.80: 75 → 60
    0.80 → 0.90: 60 → 40
    0.90 → 1.00: 40 → 20
    1.00 → 2.00: 20 → 0
    ≥ 2.00: 0
    """
    if market_ratio <= 0.40:
        return 95.0
    if market_ratio <= 0.60:
        return _lerp(market_ratio, 0.40, 0.60, 95.0, 85.0)
    if market_ratio <= 0.70:
        return _lerp(market_ratio, 0.60, 0.70, 85.0, 75.0)
    if market_ratio <= 0.80:
        return _lerp(market_ratio, 0.70, 0.80, 75.0, 60.0)
    if market_ratio <= 0.90:
        return _lerp(market_ratio, 0.80, 0.90, 60.0, 40.0)
    if market_ratio <= 1.00:
        return _lerp(market_ratio, 0.90, 1.00, 40.0, 20.0)
    if market_ratio <= 2.00:
        return _lerp(market_ratio, 1.00, 2.00, 20.0, 0.0)
    return 0.0


def _lerp_market_commercial(market_ratio: float) -> float:
    """꼬마빌딩 시세대비 곡선

    ≤ 0.40: 95 (캡)
    0.40 → 0.60: 95 → 85
    0.60 → 0.70: 85 → 70
    0.70 → 0.80: 70 → 50
    0.80 → 0.90: 50 → 30
    0.90 → 1.00: 30 → 10
    1.00 → 2.00: 10 → 0
    ≥ 2.00: 0
    """
    if market_ratio <= 0.40:
        return 95.0
    if market_ratio <= 0.60:
        return _lerp(market_ratio, 0.40, 0.60, 95.0, 85.0)
    if market_ratio <= 0.70:
        return _lerp(market_ratio, 0.60, 0.70, 85.0, 70.0)
    if market_ratio <= 0.80:
        return _lerp(market_ratio, 0.70, 0.80, 70.0, 50.0)
    if market_ratio <= 0.90:
        return _lerp(market_ratio, 0.80, 0.90, 50.0, 30.0)
    if market_ratio <= 1.00:
        return _lerp(market_ratio, 0.90, 1.00, 30.0, 10.0)
    if market_ratio <= 2.00:
        return _lerp(market_ratio, 1.00, 2.00, 10.0, 0.0)
    return 0.0


def _lerp_appraisal_gap(gap_ratio: float) -> float:
    """감정가 괴리율 곡선 (비대칭 보정 전 raw score)

    ≤ 0.10: 100
    0.10 → 0.20: 100 → 75
    0.20 → 0.30: 75 → 45
    0.30 → 0.50: 45 → 15
    0.50 → 1.00: 15 → 0
    ≥ 1.00: 0
    """
    if gap_ratio <= 0.10:
        return 100.0
    if gap_ratio <= 0.20:
        return _lerp(gap_ratio, 0.10, 0.20, 100.0, 75.0)
    if gap_ratio <= 0.30:
        return _lerp(gap_ratio, 0.20, 0.30, 75.0, 45.0)
    if gap_ratio <= 0.50:
        return _lerp(gap_ratio, 0.30, 0.50, 45.0, 15.0)
    if gap_ratio <= 1.00:
        return _lerp(gap_ratio, 0.50, 1.00, 15.0, 0.0)
    return 0.0
