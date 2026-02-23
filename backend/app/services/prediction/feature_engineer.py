"""ML 피처 엔지니어링 (Private)

DB에서 추출한 raw DataFrame을 학습/추론용 피처로 변환한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.prediction.config import PROPERTY_TYPE_MAP, PredictionConfig


class FeatureEngineer:
    """학습 데이터에 파생 피처를 추가"""

    def __init__(self, config: PredictionConfig | None = None) -> None:
        self.config = config or PredictionConfig()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """전체 피처 엔지니어링 파이프라인

        Args:
            df: PredictionDataPipeline.extract_training_data() 결과

        Returns:
            피처가 추가된 DataFrame
        """
        df = df.copy()
        df = self._add_target(df)
        df = self._winsorize_target(df)
        df = self._merge_property_types(df)
        df = self._add_basic_features(df)
        df = self._add_address_features(df)
        df = self._add_time_features(df)
        df = self._add_rolling_features(df)
        df = self._add_occupancy_features(df)
        df = self._fill_missing(df)
        return df

    # ─── 개별 변환 ───

    def _add_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """타겟 변수: 낙찰가율 (이미 계산된 winning_ratio 사용)"""
        if "winning_ratio" in df.columns:
            df["target"] = df["winning_ratio"]
        else:
            df["target"] = df["winning_bid"] / df["appraised_value"]
        return df

    def _winsorize_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """이상치 Winsorizing: TARGET_MIN~TARGET_MAX 범위로 클리핑"""
        df["target"] = df["target"].clip(
            self.config.TARGET_MIN, self.config.TARGET_MAX,
        )
        return df

    def _merge_property_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """21개 물건유형 → 8개 병합"""
        df["property_type_merged"] = (
            df["property_type"]
            .fillna("기타")
            .map(PROPERTY_TYPE_MAP)
            .fillna("기타")
        )
        return df

    def _add_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """기본 파생 피처"""
        df["appraised_value_log"] = np.log1p(
            df["appraised_value"].fillna(0).astype(float),
        )
        df["discount_rate"] = (
            df["minimum_bid"].fillna(0).astype(float)
            / df["appraised_value"].replace(0, np.nan).astype(float)
        ).fillna(0)
        return df

    def _add_address_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """소재지에서 시도/시군구 추출"""
        df["sido"] = df["address"].apply(self._extract_sido)
        df["sgg"] = df["address"].apply(self._extract_sgg)
        return df

    @staticmethod
    def _extract_sido(addr: object) -> str:
        """주소에서 시/도 추출"""
        if not addr or not isinstance(addr, str):
            return "미상"
        parts = addr.strip().split()
        return parts[0] if parts else "미상"

    @staticmethod
    def _extract_sgg(addr: object) -> str:
        """주소에서 시/군/구 추출"""
        if not addr or not isinstance(addr, str):
            return "미상"
        parts = addr.strip().split()
        return parts[1] if len(parts) > 1 else "미상"

    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """시간 피처 (winning_date 기반)"""
        date_col = "winning_date" if "winning_date" in df.columns else "auction_date"
        if date_col not in df.columns:
            df["quarter"] = 0
            df["year_month"] = 0
            return df

        dates = pd.to_datetime(df[date_col], errors="coerce")
        df["quarter"] = dates.dt.quarter.fillna(0).astype(int)
        df["year_month"] = (
            dates.dt.year * 100 + dates.dt.month
        ).fillna(0).astype(int)
        return df

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """동일 유형×시도의 rolling 평균 낙찰가율

        groupby + expanding().mean().shift(1)로 시간 누수 방지.
        정확한 3/6개월 윈도우 대신 expanding mean 사용 (성능 우선).
        """
        date_col = "winning_date" if "winning_date" in df.columns else "auction_date"

        # 날짜 기준 정렬
        if date_col in df.columns:
            dates = pd.to_datetime(df[date_col], errors="coerce")
            df = df.assign(_sort_date=dates).sort_values("_sort_date").reset_index(drop=True)
        else:
            df = df.reset_index(drop=True)

        # 그룹별 expanding mean (shift로 현재 행 제외)
        if "property_type_merged" in df.columns and "sido" in df.columns:
            grouped = df.groupby(["property_type_merged", "sido"])["target"]

            df["rolling_avg_3m"] = grouped.transform(
                lambda x: x.expanding().mean().shift(1),
            )

            df["rolling_count_3m"] = grouped.transform(
                lambda x: x.expanding().count().shift(1),
            ).fillna(0).astype(int)
        else:
            df["rolling_avg_3m"] = np.nan
            df["rolling_count_3m"] = 0

        # 정렬용 임시 컬럼 제거
        if "_sort_date" in df.columns:
            df = df.drop(columns=["_sort_date"])

        return df

    def _add_occupancy_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """명도 파생 피처"""
        if "tenant_count" not in df.columns:
            df["tenant_count"] = 0
        df["tenant_count"] = df["tenant_count"].fillna(0).astype(int)

        total_deposit = df.get("total_deposit", pd.Series(0, index=df.index))
        if total_deposit is None:
            total_deposit = pd.Series(0, index=df.index)

        df["total_deposit_ratio"] = (
            total_deposit.fillna(0).astype(float)
            / df["appraised_value"].replace(0, np.nan).astype(float)
        ).fillna(0).clip(0, 5)

        return df

    def _fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """결측치 처리"""
        # 점수 결측 → 중간값 (50.0)
        score_cols = [
            "legal_score", "price_score", "location_score",
            "occupancy_score", "total_score",
        ]
        for col in score_cols:
            if col in df.columns:
                df[col] = df[col].fillna(self.config.SCORE_FILL_VALUE)

        # fail_count 결측
        if "fail_count" in df.columns:
            df["fail_count"] = df["fail_count"].fillna(0).astype(int)

        # rolling 결측 → 전체 expanding mean
        if "rolling_avg_3m" in df.columns:
            global_expanding = df["target"].expanding().mean()
            df["rolling_avg_3m"] = df["rolling_avg_3m"].fillna(global_expanding)
            df["rolling_count_3m"] = df["rolling_count_3m"].fillna(0).astype(int)

        # 카테고리 결측
        for col in self.config.CATEGORICAL_FEATURES:
            if col in df.columns:
                df[col] = df[col].fillna("미상").astype(str)

        return df
