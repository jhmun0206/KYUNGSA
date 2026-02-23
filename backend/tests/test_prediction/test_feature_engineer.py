"""FeatureEngineer 단위 테스트 (Phase 8-1)

mock DataFrame으로 피처 엔지니어링 정확성 검증.
DB 불필요.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.prediction.config import PROPERTY_TYPE_MAP, PredictionConfig
from app.services.prediction.feature_engineer import FeatureEngineer

fe = FeatureEngineer()


# ──────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────


def _make_df(n: int = 5, **overrides) -> pd.DataFrame:
    """테스트용 DataFrame 생성"""
    defaults = {
        "case_number": [f"2025타경{10001 + i}" for i in range(n)],
        "winning_bid": [400_000_000 + i * 10_000_000 for i in range(n)],
        "appraised_value": [500_000_000] * n,
        "minimum_bid": [255_000_000] * n,
        "property_type": ["아파트"] * n,
        "court_office_code": ["B000210"] * n,
        "address": ["서울특별시 강남구 역삼동 123-4"] * n,
        "winning_date": [date(2025, 1, 15 + i) for i in range(n)],
        "winning_ratio": [0.80 + i * 0.02 for i in range(n)],
        "bid_count": [2] * n,
        "fail_count": [1] * n,
        "legal_score": [80.0] * n,
        "price_score": [70.0] * n,
        "location_score": [60.0] * n,
        "occupancy_score": [None] * n,
        "total_score": [65.0] * n,
        "tenant_count": [1] * n,
        "total_deposit": [50_000_000] * n,
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


# ──────────────────────────────────────
# 물건유형 병합 테스트
# ──────────────────────────────────────


class TestMergePropertyTypes:
    def test_known_types(self):
        """알려진 유형 → 병합"""
        df = _make_df(3, property_type=["다세대", "전답", "상가"])
        result = fe._merge_property_types(df)
        assert list(result["property_type_merged"]) == ["다세대연립", "토지", "상업용"]

    def test_unknown_type(self):
        """미등록 유형 → 기타"""
        df = _make_df(1, property_type=["공장"])
        result = fe._merge_property_types(df)
        assert result["property_type_merged"].iloc[0] == "기타"

    def test_none_type(self):
        """None → 기타"""
        df = _make_df(1, property_type=[None])
        result = fe._merge_property_types(df)
        assert result["property_type_merged"].iloc[0] == "기타"

    def test_all_mappings_exist(self):
        """매핑 키 21개 검증"""
        assert len(PROPERTY_TYPE_MAP) >= 20


# ──────────────────────────────────────
# Winsorize 테스트
# ──────────────────────────────────────


class TestWinsorize:
    def test_clip_high(self):
        """상한 초과 → 클리핑"""
        df = _make_df(1, winning_ratio=[4.6])
        result = fe._add_target(df)
        result = fe._winsorize_target(result)
        assert result["target"].iloc[0] == 1.5

    def test_clip_low(self):
        """하한 미만 → 클리핑"""
        df = _make_df(1, winning_ratio=[0.1])
        result = fe._add_target(df)
        result = fe._winsorize_target(result)
        assert result["target"].iloc[0] == 0.3

    def test_normal_range(self):
        """정상 범위 → 그대로"""
        df = _make_df(1, winning_ratio=[0.82])
        result = fe._add_target(df)
        result = fe._winsorize_target(result)
        assert abs(result["target"].iloc[0] - 0.82) < 0.001


# ──────────────────────────────────────
# 주소 파싱 테스트
# ──────────────────────────────────────


class TestAddressParsing:
    def test_normal_address(self):
        """정상 주소 → 시도/시군구 추출"""
        assert FeatureEngineer._extract_sido("서울특별시 중구 마장로1길 22") == "서울특별시"
        assert FeatureEngineer._extract_sgg("서울특별시 중구 마장로1길 22") == "중구"

    def test_empty(self):
        """빈 문자열 → 미상"""
        assert FeatureEngineer._extract_sido("") == "미상"
        assert FeatureEngineer._extract_sgg("") == "미상"

    def test_none(self):
        """None → 미상"""
        assert FeatureEngineer._extract_sido(None) == "미상"
        assert FeatureEngineer._extract_sgg(None) == "미상"

    def test_single_word(self):
        """단어 1개 → sgg 미상"""
        assert FeatureEngineer._extract_sido("서울") == "서울"
        assert FeatureEngineer._extract_sgg("서울") == "미상"


# ──────────────────────────────────────
# 기본 피처 테스트
# ──────────────────────────────────────


class TestBasicFeatures:
    def test_discount_rate(self):
        """할인율 = minimum_bid / appraised_value"""
        df = _make_df(1, minimum_bid=[300_000_000], appraised_value=[500_000_000])
        result = fe._add_basic_features(df)
        assert abs(result["discount_rate"].iloc[0] - 0.6) < 0.001

    def test_appraised_value_log(self):
        """log1p(감정가)"""
        df = _make_df(1, appraised_value=[500_000_000])
        result = fe._add_basic_features(df)
        expected = np.log1p(500_000_000)
        assert abs(result["appraised_value_log"].iloc[0] - expected) < 0.001

    def test_discount_rate_zero_appraised(self):
        """감정가 0 → 할인율 0"""
        df = _make_df(1, appraised_value=[0], minimum_bid=[100])
        result = fe._add_basic_features(df)
        assert result["discount_rate"].iloc[0] == 0.0


# ──────────────────────────────────────
# 결측치 처리 테스트
# ──────────────────────────────────────


class TestFillMissing:
    def test_score_fill(self):
        """점수 결측 → 50.0"""
        df = _make_df(1, legal_score=[None], price_score=[None])
        result = fe._fill_missing(df)
        assert result["legal_score"].iloc[0] == 50.0
        assert result["price_score"].iloc[0] == 50.0

    def test_fail_count_fill(self):
        """fail_count 결측 → 0"""
        df = _make_df(1, fail_count=[None])
        result = fe._fill_missing(df)
        assert result["fail_count"].iloc[0] == 0


# ──────────────────────────────────────
# 시간 피처 테스트
# ──────────────────────────────────────


class TestTimeFeatures:
    def test_year_month(self):
        """winning_date → year_month 변환"""
        df = _make_df(1, winning_date=[date(2025, 3, 10)])
        result = fe._add_time_features(df)
        assert result["year_month"].iloc[0] == 202503

    def test_quarter(self):
        """winning_date → quarter 변환"""
        df = _make_df(2, winning_date=[date(2025, 1, 1), date(2025, 7, 1)])
        result = fe._add_time_features(df)
        assert result["quarter"].iloc[0] == 1
        assert result["quarter"].iloc[1] == 3


# ──────────────────────────────────────
# Rolling 시간 누수 방지 테스트
# ──────────────────────────────────────


class TestRollingFeatures:
    def test_no_leakage(self):
        """첫 번째 행의 rolling 값은 NaN (이전 데이터 없으므로)"""
        df = _make_df(
            5,
            winning_ratio=[0.80, 0.85, 0.70, 0.90, 0.75],
            winning_date=[date(2025, 1, d) for d in [1, 2, 3, 4, 5]],
            property_type=["아파트"] * 5,
            address=["서울특별시 강남구 역삼동 123"] * 5,
        )
        df = fe._add_target(df)
        df = fe._merge_property_types(df)
        df = fe._add_address_features(df)
        result = fe._add_rolling_features(df)

        # 첫 행은 이전 데이터 없으므로 NaN
        assert pd.isna(result["rolling_avg_3m"].iloc[0])
        # 두 번째 행은 첫 번째만 사용 → 0.80
        assert abs(result["rolling_avg_3m"].iloc[1] - 0.80) < 0.001


# ──────────────────────────────────────
# 전체 파이프라인 테스트
# ──────────────────────────────────────


class TestTransformPipeline:
    def test_full_pipeline(self):
        """transform() 전체 실행 → 모든 피처 생성"""
        df = _make_df(10)
        config = PredictionConfig()
        result = fe.transform(df)

        # 모든 피처가 존재하는지 확인
        all_features = config.NUMERIC_FEATURES + config.CATEGORICAL_FEATURES
        for feat in all_features:
            assert feat in result.columns, f"피처 누락: {feat}"

        # target 존재
        assert "target" in result.columns

        # 결측치 없음 (fill 처리 후)
        for feat in all_features:
            assert result[feat].isna().sum() == 0, f"결측치 존재: {feat}"

    def test_output_rows(self):
        """입력 행수 유지"""
        df = _make_df(7)
        result = fe.transform(df)
        assert len(result) == 7
