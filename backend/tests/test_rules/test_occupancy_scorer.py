"""OccupancyScorer 단위 테스트 (Phase 7-3)

현황조사서 임차인 데이터 기반 명도 리스크 점수 산출 검증.
"""

from datetime import date

import pytest

from app.models.auction import AuctionCaseDetail
from app.models.occupancy_dto import OccupancyTenantDTO
from app.services.rules.occupancy_scorer import OccupancyScorer

scorer = OccupancyScorer()


# ──────────────────────────────────────
# 테스트 헬퍼
# ──────────────────────────────────────


def _make_case(**overrides) -> AuctionCaseDetail:
    """테스트용 AuctionCaseDetail"""
    defaults = {
        "case_number": "2025타경10001",
        "court": "서울중앙지방법원",
        "property_type": "아파트",
        "address": "서울특별시 강남구 역삼동 123-4",
        "appraised_value": 500_000_000,
        "minimum_bid": 255_000_000,
    }
    defaults.update(overrides)
    return AuctionCaseDetail(**defaults)


def _make_tenant(**overrides) -> OccupancyTenantDTO:
    """테스트용 OccupancyTenantDTO"""
    defaults = {
        "tenant_name": "김OO",
        "party_type": "임차인",
        "deposit": 50_000_000,
        "deposit_raw": "5천만원",
        "move_in_date": date(2023, 1, 15),
        "fixed_date": date(2023, 2, 1),
        "is_unknown": False,
    }
    defaults.update(overrides)
    return OccupancyTenantDTO(**defaults)


# ──────────────────────────────────────
# 임차인 복잡도 테스트
# ──────────────────────────────────────


class TestTenantComplexity:
    """임차인 수/미상 기반 복잡도 점수"""

    def test_no_tenants_high_score(self):
        """임차인 0명 → 높은 base_score (명도 불필요), MEDIUM 신뢰도 감쇠"""
        case = _make_case()
        result = scorer.score(case, tenants=[])

        assert result.base_score > 80  # 신뢰도 감쇠 전
        assert result.score > 60       # MEDIUM(0.85) 감쇠 후
        assert result.tenant_count == 0
        assert result.sub_scores.tenant_complexity_score == 100.0

    def test_single_tenant_simple(self):
        """임차인 1명, 보증금 소액 → 복잡도 80"""
        case = _make_case()
        tenants = [_make_tenant(deposit=10_000_000)]
        result = scorer.score(case, tenants=tenants)

        assert result.sub_scores.tenant_complexity_score == 80.0
        assert result.tenant_count == 1

    def test_multiple_tenants_penalty(self):
        """임차인 3명 → 복잡도 40"""
        case = _make_case()
        tenants = [_make_tenant() for _ in range(3)]
        result = scorer.score(case, tenants=tenants)

        assert result.sub_scores.tenant_complexity_score == 40.0
        assert result.tenant_count == 3

    def test_four_plus_tenants(self):
        """임차인 4명+ → 복잡도 20"""
        case = _make_case()
        tenants = [_make_tenant() for _ in range(5)]
        result = scorer.score(case, tenants=tenants)

        assert result.sub_scores.tenant_complexity_score == 20.0

    def test_unknown_tenant_penalty(self):
        """미상 임차인 → 추가 감점"""
        case = _make_case()
        tenants = [
            _make_tenant(),
            _make_tenant(tenant_name="미상", is_unknown=True, deposit=None, move_in_date=None, fixed_date=None),
        ]
        result = scorer.score(case, tenants=tenants)

        # 2명 → 60 기본, 미상 1명 → -15 = 45
        assert result.sub_scores.tenant_complexity_score == 45.0
        assert result.unknown_count == 1
        assert "미상" in result.warnings[0]


# ──────────────────────────────────────
# 보증금 부담도 테스트
# ──────────────────────────────────────


class TestDepositBurden:
    """보증금/감정가 비율 기반 부담도 점수"""

    def test_high_deposit_ratio(self):
        """보증금/감정가 > 0.5 → 낮은 점수"""
        case = _make_case(appraised_value=500_000_000)
        tenants = [_make_tenant(deposit=300_000_000)]
        result = scorer.score(case, tenants=tenants)

        # deposit_ratio = 0.6 → 약 35점 (0.5=45, 0.7=25 사이)
        assert result.sub_scores.deposit_burden_score < 50
        assert result.total_deposit == 300_000_000

    def test_low_deposit_ratio(self):
        """보증금/감정가 < 0.1 → 높은 점수"""
        case = _make_case(appraised_value=500_000_000)
        tenants = [_make_tenant(deposit=10_000_000)]
        result = scorer.score(case, tenants=tenants)

        assert result.sub_scores.deposit_burden_score > 80

    def test_no_deposit_uncertain(self):
        """보증금 0원 → 불확실 (50)"""
        case = _make_case()
        tenants = [_make_tenant(deposit=None)]
        result = scorer.score(case, tenants=tenants)

        assert result.sub_scores.deposit_burden_score == 50.0


# ──────────────────────────────────────
# 대항력 위험도 테스트
# ──────────────────────────────────────


class TestOpposingPower:
    """전입+확정일 보유 비율 기반 대항력 위험도"""

    def test_opposing_power_high_risk(self):
        """전입+확정 100% → 낮은 점수"""
        case = _make_case()
        tenants = [
            _make_tenant(move_in_date=date(2023, 1, 1), fixed_date=date(2023, 2, 1)),
            _make_tenant(move_in_date=date(2023, 3, 1), fixed_date=date(2023, 4, 1)),
        ]
        result = scorer.score(case, tenants=tenants)

        assert result.sub_scores.opposing_power_score == 15.0

    def test_no_fixed_date_safer(self):
        """확정일 없으면 대항력 위험 낮음 → 높은 점수"""
        case = _make_case()
        tenants = [
            _make_tenant(move_in_date=date(2023, 1, 1), fixed_date=None),
            _make_tenant(move_in_date=date(2023, 3, 1), fixed_date=None),
        ]
        result = scorer.score(case, tenants=tenants)

        # fixed_ratio = 0 → 100점
        assert result.sub_scores.opposing_power_score == 100.0

    def test_no_tenants_no_risk(self):
        """임차인 0명 → 대항력 위험 없음"""
        case = _make_case()
        result = scorer.score(case, tenants=[])

        assert result.sub_scores.opposing_power_score == 100.0


# ──────────────────────────────────────
# 유형별 가중치 테스트
# ──────────────────────────────────────


class TestPropertyWeights:
    """물건 유형별 가중치 차이 검증"""

    def _score_with_type(self, property_type: str) -> float:
        """동일 임차인으로 유형별 점수 비교"""
        case = _make_case(property_type=property_type, appraised_value=500_000_000)
        tenants = [
            _make_tenant(deposit=100_000_000, move_in_date=date(2023, 1, 1), fixed_date=date(2023, 2, 1)),
            _make_tenant(deposit=100_000_000, move_in_date=date(2023, 3, 1), fixed_date=date(2023, 4, 1)),
        ]
        return scorer.score(case, tenants=tenants)

    def test_apartment_weights(self):
        """아파트: opposing_power 비중 0.40"""
        result = self._score_with_type("아파트")
        assert result.property_category == "아파트"
        # opposing_power 100% → 15, 가중치 0.40으로 크게 반영
        assert result.base_score < 50

    def test_building_weights(self):
        """꼬마빌딩: tenant_complexity 비중 0.35"""
        result = self._score_with_type("상가")  # → 꼬마빌딩
        assert result.property_category == "꼬마빌딩"

    def test_land_weights(self):
        """토지: tenant_complexity 비중 0.60"""
        result = self._score_with_type("토지")
        assert result.property_category == "토지"


# ──────────────────────────────────────
# 신뢰도 테스트
# ──────────────────────────────────────


class TestConfidence:
    """데이터 완비도 기반 신뢰도 결정"""

    def test_confidence_high(self):
        """임차인+보증금+날짜 완비 → HIGH"""
        case = _make_case()
        tenants = [_make_tenant(deposit=50_000_000, move_in_date=date(2023, 1, 1))]
        result = scorer.score(case, tenants=tenants)

        assert result.confidence == "HIGH"
        assert result.confidence_multiplier == 1.0

    def test_confidence_medium_no_deposit(self):
        """보증금 없으면 MEDIUM"""
        case = _make_case()
        tenants = [_make_tenant(deposit=None, move_in_date=date(2023, 1, 1))]
        result = scorer.score(case, tenants=tenants)

        assert result.confidence == "MEDIUM"
        assert result.confidence_multiplier == 0.85

    def test_confidence_medium_no_tenants(self):
        """임차인 0명 → MEDIUM"""
        case = _make_case()
        result = scorer.score(case, tenants=[])

        assert result.confidence == "MEDIUM"
        assert result.confidence_multiplier == 0.85

    def test_confidence_medium_no_dates(self):
        """날짜 없으면 MEDIUM"""
        case = _make_case()
        tenants = [_make_tenant(deposit=50_000_000, move_in_date=None, fixed_date=None)]
        result = scorer.score(case, tenants=tenants)

        assert result.confidence == "MEDIUM"


# ──────────────────────────────────────
# 기타 테스트
# ──────────────────────────────────────


class TestScoreRange:
    """점수 범위 및 기본 동작"""

    def test_score_range_0_100(self):
        """점수 범위 검증 (0~100 클램프)"""
        case = _make_case()
        # 최악 시나리오: 많은 임차인, 높은 보증금, 전부 대항력
        tenants = [
            _make_tenant(
                deposit=200_000_000,
                move_in_date=date(2020, 1, 1),
                fixed_date=date(2020, 2, 1),
            )
            for _ in range(5)
        ]
        # 미상 추가
        tenants.append(
            _make_tenant(
                tenant_name="미상", is_unknown=True,
                deposit=None, move_in_date=None, fixed_date=None,
            )
        )
        result = scorer.score(case, tenants=tenants)

        assert 0.0 <= result.score <= 100.0
        assert result.tenant_count == 6
        assert result.unknown_count == 1

    def test_scorer_version(self):
        """스코어러 버전 확인"""
        case = _make_case()
        result = scorer.score(case, tenants=[])
        assert result.scorer_version == "v1.0"
