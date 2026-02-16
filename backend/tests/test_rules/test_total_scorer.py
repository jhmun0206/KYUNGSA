"""TotalScorer 단위 테스트

통합 점수 합산기의 가중치 재정규화, 유형 분류, 등급 부여, 커버리지 계산을 검증한다.
"""

import pytest

from app.services.rules.total_scorer import TotalScorer

scorer = TotalScorer()


# ──────────────────────────────────────
# 가중치 재정규화 테스트
# ──────────────────────────────────────


class TestWeightNormalization:
    """가용 pillar 수에 따른 가중치 재정규화"""

    def test_two_pillars_legal_price(self):
        """법률+가격만 (현재 MVP) → 재정규화"""
        result = scorer.score(
            "아파트", legal_score=80.0, price_score=60.0,
        )
        # 아파트: legal=0.20, price=0.25, total=0.45
        # normalized: legal=0.20/0.45≈0.4444, price=0.25/0.45≈0.5556
        assert abs(result.weights_used["legal"] - 0.4444) < 0.001
        assert abs(result.weights_used["price"] - 0.5556) < 0.001
        assert abs(sum(result.weights_used.values()) - 1.0) < 0.001

    def test_three_pillars(self):
        """법률+가격+입지 → 재정규화"""
        result = scorer.score(
            "아파트", legal_score=80.0, price_score=60.0, location_score=70.0,
        )
        # 아파트: legal=0.20, price=0.25, location=0.30, total=0.75
        assert abs(result.weights_used["legal"] - 0.2667) < 0.001
        assert abs(result.weights_used["price"] - 0.3333) < 0.001
        assert abs(result.weights_used["location"] - 0.4) < 0.001

    def test_all_four_pillars(self):
        """전체 4개 pillar → 재정규화 불필요 (가중치 합=1.0)"""
        result = scorer.score(
            "아파트",
            legal_score=80.0, price_score=60.0,
            location_score=70.0, occupancy_score=50.0,
        )
        # 아파트: legal=0.20, price=0.25, location=0.30, occupancy=0.25
        assert abs(result.weights_used["legal"] - 0.20) < 0.001
        assert abs(result.weights_used["price"] - 0.25) < 0.001
        assert abs(result.weights_used["location"] - 0.30) < 0.001
        assert abs(result.weights_used["occupancy"] - 0.25) < 0.001
        assert result.score_coverage == 1.0

    def test_price_only(self):
        """가격만 → 100% 가중치"""
        result = scorer.score("아파트", price_score=75.0)
        assert abs(result.weights_used["price"] - 1.0) < 0.001
        assert result.total_score == 75.0


# ──────────────────────────────────────
# 유형 분류 테스트
# ──────────────────────────────────────


class TestPropertyCategory:
    """property_type → 카테고리 분류"""

    def test_apartment_types(self):
        """아파트/오피스텔/연립 → 아파트"""
        for pt in ["아파트", "오피스텔", "주상복합", "연립", "빌라"]:
            result = scorer.score(pt, price_score=50.0)
            assert result.property_category == "아파트", f"{pt} → 아파트 분류 실패"

    def test_commercial_types(self):
        """상가/근린/다가구 → 꼬마빌딩"""
        for pt in ["상가", "근린생활시설", "다가구", "다세대", "건물"]:
            result = scorer.score(pt, price_score=50.0)
            assert result.property_category == "꼬마빌딩", f"{pt} → 꼬마빌딩 분류 실패"

    def test_land_types(self):
        """토지/임야/대지 → 토지"""
        for pt in ["토지", "임야", "전", "답", "대지"]:
            result = scorer.score(pt, price_score=50.0)
            assert result.property_category == "토지", f"{pt} → 토지 분류 실패"


# ──────────────────────────────────────
# 등급 테스트
# ──────────────────────────────────────


class TestGrade:
    """총점 → 등급 (A/B/C/D)"""

    def test_grade_a(self):
        """85점 → A등급"""
        result = scorer.score("아파트", legal_score=85.0, price_score=85.0)
        assert result.grade == "A"
        assert result.total_score == 85.0

    def test_grade_b(self):
        """70점 → B등급"""
        result = scorer.score("아파트", legal_score=70.0, price_score=70.0)
        assert result.grade == "B"
        assert result.total_score == 70.0

    def test_grade_c(self):
        """50점 → C등급"""
        result = scorer.score("아파트", legal_score=50.0, price_score=50.0)
        assert result.grade == "C"
        assert result.total_score == 50.0

    def test_grade_d(self):
        """30점 → D등급"""
        result = scorer.score("아파트", legal_score=30.0, price_score=30.0)
        assert result.grade == "D"
        assert result.total_score == 30.0


# ──────────────────────────────────────
# 커버리지 + missing 테스트
# ──────────────────────────────────────


class TestCoverageAndMissing:
    """score_coverage 계산 + missing_pillars 추적"""

    def test_coverage_legal_price_apt(self):
        """아파트 법률+가격 → coverage=0.45"""
        result = scorer.score("아파트", legal_score=80.0, price_score=60.0)
        assert result.score_coverage == 0.45
        assert set(result.missing_pillars) == {"location", "occupancy"}

    def test_coverage_warning(self):
        """coverage < 0.70 → 경고 생성"""
        result = scorer.score("아파트", price_score=60.0)
        # 아파트: price=0.25 → coverage=0.25
        assert result.score_coverage == 0.25
        assert any("커버리지" in w for w in result.warnings)

    def test_no_pillars(self):
        """pillar 없음 → score=0, 경고"""
        result = scorer.score("아파트")
        assert result.total_score == 0.0
        assert result.score_coverage == 0.0
        assert any("가용 pillar 없음" in w for w in result.warnings)
        assert result.grade == "D"


# ──────────────────────────────────────
# 유형별 가중치 차이 검증
# ──────────────────────────────────────


class TestCategoryWeightDifference:
    """같은 점수라도 유형에 따라 총점이 다름"""

    def test_apt_vs_building_legal_heavy(self):
        """법률 높고 가격 낮을 때: 꼬마빌딩이 아파트보다 총점 높아야 함"""
        # legal=90, price=40
        apt = scorer.score("아파트", legal_score=90.0, price_score=40.0)
        bldg = scorer.score("상가", legal_score=90.0, price_score=40.0)
        # 꼬마빌딩은 legal 가중치가 더 높으므로
        assert bldg.total_score > apt.total_score


# ──────────────────────────────────────
# 통합 테스트
# ──────────────────────────────────────


class TestIntegration:
    """현실적 시나리오 통합 테스트"""

    def test_good_apartment(self):
        """매력적 아파트: 법률 85 + 가격 80 → A등급"""
        result = scorer.score(
            "아파트",
            legal_score=85.0,
            price_score=80.0,
        )
        # normalized: legal=0.4444, price=0.5556
        # total = 85*0.4444 + 80*0.5556 = 37.78 + 44.44 = 82.2
        assert result.total_score >= 80.0
        assert result.grade == "A"
        assert result.property_category == "아파트"
        assert result.scorer_version == "v1.0"

    def test_risky_building(self):
        """위험한 꼬마빌딩: 법률 25 + 가격 35 → D등급"""
        result = scorer.score(
            "상가",
            legal_score=25.0,
            price_score=35.0,
            needs_expert_review=True,
        )
        # 꼬마빌딩: legal=0.35, price=0.20, total=0.55
        # normalized: legal=0.6364, price=0.3636
        # total = 25*0.6364 + 35*0.3636 = 15.91 + 12.73 = 28.6
        assert result.total_score < 40.0
        assert result.grade == "D"
        assert result.needs_expert_review is True
