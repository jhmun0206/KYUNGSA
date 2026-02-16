"""PriceScorer 단위 테스트

가격 매력도 점수 엔진의 각 세부 점수 계산과 통합 산출을 검증한다.
"""

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import MarketPriceInfo
from app.services.rules.price_scorer import PriceScorer


# ──────────────────────────────────────
# 테스트 헬퍼
# ──────────────────────────────────────


def _make_case(
    appraised_value: int = 500_000_000,
    minimum_bid: int = 400_000_000,
    property_type: str = "아파트",
    area_m2: float | None = 84.0,
    **kwargs,
) -> AuctionCaseDetail:
    """테스트용 경매 물건 생성"""
    defaults = {
        "case_number": "2024타경12345",
        "court": "서울중앙지방법원",
        "address": "서울특별시 강남구 역삼동 123-4",
    }
    defaults.update(kwargs)
    return AuctionCaseDetail(
        appraised_value=appraised_value,
        minimum_bid=minimum_bid,
        property_type=property_type,
        area_m2=area_m2,
        **defaults,
    )


def _make_market_price(
    avg_price_per_m2: float = 5_000_000.0,
    trade_count: int = 15,
    **kwargs,
) -> MarketPriceInfo:
    """테스트용 시세 정보 생성"""
    return MarketPriceInfo(
        avg_price_per_m2=avg_price_per_m2,
        trade_count=trade_count,
        **kwargs,
    )


scorer = PriceScorer()


# ──────────────────────────────────────
# 할인율 점수 테스트
# ──────────────────────────────────────


class TestDiscountScore:
    """할인율 점수 테스트"""

    def test_first_round_20pct(self):
        """1회차 (discount_rate=0.20) → 경계점 55"""
        # minimum_bid = 500M * 0.80 = 400M → rate = 0.20
        score, detail, _ = scorer._calc_discount_score(400_000_000, 500_000_000)
        assert score == 55.0
        assert detail["discount_rate"] == 0.2

    def test_second_round_36pct(self):
        """2회차 (discount_rate=0.36) → 경계점 68"""
        # minimum_bid = 500M * 0.64 = 320M → rate = 0.36
        score, detail, _ = scorer._calc_discount_score(320_000_000, 500_000_000)
        assert score == 68.0

    def test_third_round_49pct(self):
        """3회차 (discount_rate=0.49) → 경계점 82"""
        # minimum_bid = 500M * 0.51 = 255M → rate = 0.49
        score, detail, _ = scorer._calc_discount_score(255_000_000, 500_000_000)
        assert score == 82.0

    def test_fifth_round_67pct(self):
        """5회차 (discount_rate=0.67) → 93~96 구간"""
        # minimum_bid = 500M * 0.33 = 165M → rate = 0.67
        score, _, _ = scorer._calc_discount_score(165_000_000, 500_000_000)
        assert 93.0 <= score <= 96.0

    def test_zero_appraised(self):
        """감정가 0 → score=0, warning"""
        score, detail, warnings = scorer._calc_discount_score(100_000_000, 0)
        assert score == 0.0
        assert len(warnings) > 0
        assert any("감정가" in w for w in warnings)


# ──────────────────────────────────────
# 시세 대비 점수 테스트 (아파트)
# ──────────────────────────────────────


class TestMarketCompareResidential:
    """아파트 시세 대비 점수 테스트"""

    def test_apt_ratio_40pct(self):
        """시세 40% → 95 (캡)"""
        score, detail = scorer._calc_market_compare_score(
            200_000_000, 500_000_000, True
        )
        assert score == 95.0

    def test_apt_ratio_70pct(self):
        """시세 70% → 경계점 75"""
        score, _ = scorer._calc_market_compare_score(
            350_000_000, 500_000_000, True
        )
        assert score == 75.0

    def test_apt_ratio_90pct(self):
        """시세 90% → 경계점 40"""
        score, _ = scorer._calc_market_compare_score(
            450_000_000, 500_000_000, True
        )
        assert score == 40.0

    def test_apt_ratio_150pct(self):
        """시세 150% → 10 (시세 초과)"""
        # lerp(1.50, 1.00, 2.00, 20, 0) = 10
        score, _ = scorer._calc_market_compare_score(
            750_000_000, 500_000_000, True
        )
        assert score == 10.0


# ──────────────────────────────────────
# 시세 대비 점수 테스트 (꼬마빌딩)
# ──────────────────────────────────────


class TestMarketCompareCommercial:
    """꼬마빌딩 시세 대비 점수 테스트"""

    def test_bldg_ratio_60pct(self):
        """시세 60% → 경계점 85"""
        score, _ = scorer._calc_market_compare_score(
            300_000_000, 500_000_000, False
        )
        assert score == 85.0

    def test_bldg_ratio_80pct(self):
        """시세 80% → 경계점 50"""
        score, _ = scorer._calc_market_compare_score(
            400_000_000, 500_000_000, False
        )
        assert score == 50.0

    def test_bldg_ratio_90pct(self):
        """시세 90% → 경계점 30"""
        score, _ = scorer._calc_market_compare_score(
            450_000_000, 500_000_000, False
        )
        assert score == 30.0


# ──────────────────────────────────────
# 감정가 신뢰도 점수 테스트
# ──────────────────────────────────────


class TestAppraisalAccuracy:
    """감정가 신뢰도 점수 테스트"""

    def test_gap_8pct_undervalued(self):
        """gap=8% 저평가 → raw=100, 보정 없음 → 100"""
        # appraised=460M, estimated=500M → gap=40/500=0.08, 저평가
        score, detail = scorer._calc_appraisal_accuracy_score(
            460_000_000, 500_000_000
        )
        assert score == 100.0
        assert detail["gap_direction"] == "undervalued"

    def test_gap_25pct_overvalued(self):
        """gap=25% 고평가 → raw=60 × 0.8 = 48"""
        # appraised=625M, estimated=500M → gap=125/500=0.25
        # lerp(0.25, 0.20, 0.30, 75, 45) = 75 + 0.5*(-30) = 60
        # overvalued: 60 * 0.8 = 48
        score, detail = scorer._calc_appraisal_accuracy_score(
            625_000_000, 500_000_000
        )
        assert score == 48.0
        assert detail["gap_direction"] == "overvalued"
        assert detail["raw_score"] == 60.0

    def test_gap_25pct_undervalued(self):
        """gap=25% 저평가 → raw=60, 보정 없음 → 60"""
        # appraised=375M, estimated=500M → gap=125/500=0.25
        score, detail = scorer._calc_appraisal_accuracy_score(
            375_000_000, 500_000_000
        )
        assert score == 60.0
        assert detail["gap_direction"] == "undervalued"


# ──────────────────────────────────────
# 동적 가중치 테스트
# ──────────────────────────────────────


class TestDynamicWeights:
    """시세 유무에 따른 동적 가중치 전환 테스트"""

    def test_with_market_data(self):
        """시세 있을 때 → 가중치 0.15/0.55/0.30"""
        case = _make_case(
            appraised_value=400_000_000,
            minimum_bid=204_000_000,  # discount_rate ≈ 0.49
            area_m2=100.0,
        )
        market = _make_market_price(avg_price_per_m2=4_000_000.0, trade_count=15)
        result = scorer.score(case, market)

        assert result.has_market_data is True
        assert result.details["weights_used"]["discount"] == 0.15
        assert result.details["weights_used"]["market"] == 0.55
        assert result.details["weights_used"]["appraisal"] == 0.30

    def test_without_market_data(self):
        """시세 없을 때 → 가중치 0.60/0.40, market_compare 제외"""
        case = _make_case(
            appraised_value=500_000_000,
            minimum_bid=400_000_000,
        )
        result = scorer.score(case, market_price=None)

        assert result.has_market_data is False
        assert result.details["weights_used"]["discount"] == 0.60
        assert result.details["weights_used"]["appraisal"] == 0.40
        assert "market" not in result.details["weights_used"]
        assert any("시세" in w for w in result.warnings)


# ──────────────────────────────────────
# 신뢰도 테스트
# ──────────────────────────────────────


class TestConfidence:
    """신뢰도 계수 테스트"""

    def test_confidence_levels(self):
        """HIGH/MEDIUM/LOW 신뢰도 구분"""
        # HIGH: trade_count ≥ 10, area_m2 존재
        assert scorer._determine_confidence(
            _make_market_price(trade_count=15), 84.0
        ) == "HIGH"

        # MEDIUM: trade_count ≥ 5
        assert scorer._determine_confidence(
            _make_market_price(trade_count=7), 84.0
        ) == "MEDIUM"

        # LOW: trade_count < 5
        assert scorer._determine_confidence(
            _make_market_price(trade_count=3), 84.0
        ) == "LOW"

        # LOW: market_price 없음
        assert scorer._determine_confidence(None, 84.0) == "LOW"

        # LOW: area_m2 없음
        assert scorer._determine_confidence(
            _make_market_price(trade_count=15), None
        ) == "LOW"


# ──────────────────────────────────────
# 엣지케이스 테스트
# ──────────────────────────────────────


class TestEdgeCases:
    """엣지케이스 테스트"""

    def test_min_bid_exceeds_appraised(self):
        """최저가 > 감정가 → discount_score=20, warning"""
        score, detail, warnings = scorer._calc_discount_score(
            600_000_000, 500_000_000
        )
        assert score == 20.0
        assert detail["discount_rate"] == 0.0
        assert any("초과" in w for w in warnings)

    def test_market_ratio_above_2(self):
        """market_ratio > 2.0 → market_compare=0 (클램프)"""
        # minimum_bid = 1200M, estimated = 500M → ratio = 2.4
        score, detail = scorer._calc_market_compare_score(
            1_200_000_000, 500_000_000, True
        )
        assert score == 0.0


# ──────────────────────────────────────
# 통합 테스트
# ──────────────────────────────────────


class TestIntegration:
    """PriceScorer 통합 테스트"""

    def test_attractive_apt(self):
        """매력적 아파트: 3회차 + 시세 51% + 감정가 정확 → 높은 점수"""
        case = _make_case(
            appraised_value=400_000_000,
            minimum_bid=204_000_000,  # discount_rate ≈ 0.49 → 82.0
            property_type="아파트",
            area_m2=100.0,
        )
        # estimated = 4M * 100 = 400M → market_ratio = 204/400 = 0.51
        # gap = |400-400|/400 = 0 → appraisal = 100
        market = _make_market_price(avg_price_per_m2=4_000_000.0, trade_count=15)

        result = scorer.score(case, market)
        # base = 82*0.15 + 89.5*0.55 + 100*0.30 ≈ 91.5
        assert result.score >= 80.0
        assert result.has_market_data is True
        assert result.confidence == "HIGH"
        assert result.confidence_multiplier == 1.0

    def test_unattractive_building(self):
        """비매력적 상가: 1회차 + 시세 95% + 감정가 고평가 → 낮은 점수"""
        case = _make_case(
            appraised_value=500_000_000,
            minimum_bid=400_000_000,  # discount_rate = 0.20 → 55
            property_type="상가",
            area_m2=100.0,
        )
        # estimated = 4.2M * 100 = 420M
        # market_ratio = 400/420 ≈ 0.952 (상가 곡선: ~19.5)
        # gap = |500-420|/420 ≈ 0.19, overvalued → raw~77.6 × 0.8 ≈ 62.1
        market = _make_market_price(avg_price_per_m2=4_200_000.0, trade_count=15)

        result = scorer.score(case, market)
        # base ≈ 55*0.15 + 19.5*0.55 + 62.1*0.30 ≈ 37.6
        assert result.score <= 45.0
        assert result.is_residential is False
