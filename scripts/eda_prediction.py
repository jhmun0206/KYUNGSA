"""ML 학습 데이터 EDA (탐색적 데이터 분석)

DB에서 낙찰 데이터를 추출하고, 피처 엔지니어링 후 통계를 출력한다.

사용법:
    # 서버
    PYTHONPATH=backend .venv/bin/python scripts/eda_prediction.py
    # Mac
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate kyungsa
    PYTHONPATH=backend python scripts/eda_prediction.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.prediction.config import PredictionConfig  # noqa: E402
from app.services.prediction.data_pipeline import PredictionDataPipeline  # noqa: E402
from app.services.prediction.feature_engineer import FeatureEngineer  # noqa: E402


def _header(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def run_eda() -> None:
    config = PredictionConfig()

    # 1. 데이터 추출
    _header("1. 데이터 추출")
    db = SessionLocal()
    try:
        pipeline = PredictionDataPipeline(db)
        raw_df = pipeline.extract_training_data()
    finally:
        db.close()

    if raw_df.empty:
        print("데이터 없음. 종료.")
        return

    print(f"  추출 건수: {len(raw_df):,}건")

    # 2. 피처 엔지니어링
    _header("2. 피처 엔지니어링")
    fe = FeatureEngineer(config)
    df = fe.transform(raw_df)
    print(f"  변환 후 건수: {len(df):,}건")
    print(f"  컬럼 수: {len(df.columns)}개")

    # 3. 타겟 통계
    _header("3. 타겟(낙찰가율) 기본 통계")
    target = df["target"]
    print(f"  건수:     {len(target):,}")
    print(f"  평균:     {_pct(target.mean())}")
    print(f"  중앙값:   {_pct(target.median())}")
    print(f"  표준편차: {_pct(target.std())}")
    print(f"  범위:     {_pct(target.min())} ~ {_pct(target.max())}")

    # Winsorize 전 이상치
    if "winning_ratio" in raw_df.columns:
        raw_ratios = raw_df["winning_ratio"].dropna()
        outliers_low = (raw_ratios < config.TARGET_MIN).sum()
        outliers_high = (raw_ratios > config.TARGET_MAX).sum()
        print(f"  Winsorize 이상치: 하한({config.TARGET_MIN}) {outliers_low}건, "
              f"상한({config.TARGET_MAX}) {outliers_high}건")

    # 4. 물건유형(병합) 통계
    _header("4. 물건유형(병합) 통계")
    type_stats = (
        df.groupby("property_type_merged")["target"]
        .agg(["count", "mean", "median", "std"])
        .sort_values("count", ascending=False)
    )
    print(f"  {'유형':<12} {'건수':>6} {'평균':>8} {'중앙값':>8} {'표준편차':>8}")
    print(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
    for name, row in type_stats.iterrows():
        print(f"  {name:<12} {int(row['count']):>6} "
              f"{_pct(row['mean']):>8} {_pct(row['median']):>8} "
              f"{_pct(row['std']) if not np.isnan(row['std']) else '-':>8}")

    # 5. 유찰횟수별 통계
    _header("5. 유찰횟수별 평균 낙찰가율")
    if "fail_count" in df.columns:
        fail_stats = (
            df.groupby("fail_count")["target"]
            .agg(["count", "mean", "median"])
            .head(10)
        )
        print(f"  {'유찰':>4} {'건수':>6} {'평균':>8} {'중앙값':>8}")
        print(f"  {'-'*4} {'-'*6} {'-'*8} {'-'*8}")
        for fail_cnt, row in fail_stats.iterrows():
            print(f"  {fail_cnt:>4} {int(row['count']):>6} "
                  f"{_pct(row['mean']):>8} {_pct(row['median']):>8}")

    # 6. 피처 결측률
    _header("6. 피처 결측률")
    all_features = config.NUMERIC_FEATURES + config.CATEGORICAL_FEATURES
    missing_info = []
    for col in all_features:
        if col in df.columns:
            missing_pct = df[col].isna().mean()
            if missing_pct > 0:
                missing_info.append((col, missing_pct))
    if missing_info:
        missing_info.sort(key=lambda x: -x[1])
        for col, pct in missing_info:
            print(f"  {col:<25} {_pct(pct)}")
    else:
        print("  결측치 없음 (fill 처리 완료)")

    # 7. 피처-타겟 상관관계
    _header("7. 피처-타겟 상관관계 (Pearson, top 10)")
    numeric_cols = [c for c in config.NUMERIC_FEATURES if c in df.columns]
    if numeric_cols:
        corrs = df[numeric_cols + ["target"]].corr()["target"].drop("target")
        corrs_sorted = corrs.abs().sort_values(ascending=False).head(10)
        print(f"  {'피처':<25} {'상관계수':>8}")
        print(f"  {'-'*25} {'-'*8}")
        for feat in corrs_sorted.index:
            print(f"  {feat:<25} {corrs[feat]:>8.4f}")

    # 8. 시도별 통계
    _header("8. 시도별 통계 (상위 10)")
    if "sido" in df.columns:
        sido_stats = (
            df.groupby("sido")["target"]
            .agg(["count", "mean", "median"])
            .sort_values("count", ascending=False)
            .head(10)
        )
        print(f"  {'시도':<12} {'건수':>6} {'평균':>8} {'중앙값':>8}")
        print(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*8}")
        for name, row in sido_stats.iterrows():
            print(f"  {name:<12} {int(row['count']):>6} "
                  f"{_pct(row['mean']):>8} {_pct(row['median']):>8}")

    print(f"\n{'═' * 60}")
    print(f"  EDA 완료 — 전체 {len(df):,}건")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    run_eda()
