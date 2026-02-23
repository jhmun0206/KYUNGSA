"""ML 예측 모델 설정 (Private)

하이퍼파라미터, 피처 목록, 물건유형 병합 매핑 등.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# 물건유형 병합 매핑 (21 → 8)
PROPERTY_TYPE_MAP: dict[str, str] = {
    # 아파트 (단독)
    "아파트": "아파트",
    # 다세대/연립
    "다세대": "다세대연립",
    "연립주택": "다세대연립",
    "연립주택,다세대,빌라": "다세대연립",
    "빌라": "다세대연립",
    # 오피스텔 (단독)
    "오피스텔": "오피스텔",
    # 단독/다가구
    "단독주택": "단독다가구",
    "단독주택다가구": "단독다가구",
    "다가구주택": "단독다가구",
    # 상업용
    "상가": "상업용",
    "상가,오피스텔,근린시설": "상업용",
    "근린시설": "상업용",
    # 토지
    "전답": "토지",
    "임야": "토지",
    "대지": "토지",
    "대지,임야,전답": "토지",
    # 차량/중기
    "자동차": "차량중기",
    "중기": "차량중기",
    "자동차,중기": "차량중기",
    # 기타
    "기타": "기타",
}


@dataclass
class PredictionConfig:
    """ML 모델 설정"""

    # ── 피처 정의 ──

    NUMERIC_FEATURES: list[str] = field(default_factory=lambda: [
        "fail_count",
        "appraised_value_log",
        "discount_rate",
        "legal_score",
        "price_score",
        "location_score",
        "occupancy_score",
        "total_score",
        "tenant_count",
        "total_deposit_ratio",
        "quarter",
        "year_month",
        "rolling_avg_3m",
        "rolling_count_3m",
    ])

    CATEGORICAL_FEATURES: list[str] = field(default_factory=lambda: [
        "property_type_merged",
        "court_office_code",
        "sido",
        "sgg",
    ])

    TARGET: str = "target"

    # ── CatBoost 하이퍼파라미터 ──

    CATBOOST_PARAMS: dict = field(default_factory=lambda: {
        "iterations": 1000,
        "learning_rate": 0.05,
        "depth": 6,
        "l2_leaf_reg": 3.0,
        "min_data_in_leaf": 20,
        "random_seed": 42,
        "verbose": 100,
        "early_stopping_rounds": 50,
        "loss_function": "RMSE",
        "eval_metric": "MAPE",
    })

    # ── Winsorize 범위 ──

    TARGET_MIN: float = 0.3
    TARGET_MAX: float = 1.5

    # ── 교차검증 ──

    CV_N_SPLITS: int = 5

    # ── 모델 저장 경로 ──

    MODEL_DIR: str = "models/prediction"

    # ── 결측치 기본값 ──

    SCORE_FILL_VALUE: float = 50.0
