"""점수 산출 결과 모델

각 점수 pillar의 결과를 담는 Pydantic DTO 모델.
5C: 법률 리스크 점수 (LegalScoreResult)
5D: 가격 매력도 점수 (PriceScoreResult)
5E: 통합 점수 (TotalScoreResult)
향후: LocationScoreResult (6), OccupancyScoreResult (7)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LegalSubScores(BaseModel):
    """법률 리스크 세부 점수 (각 0~100, 높을수록 안전)"""

    mortgage_ratio_score: float = 0.0   # 근저당/감정가 비율
    seizure_score: float = 0.0          # 가압류/가처분 건수·금액
    surviving_rights_score: float = 0.0  # 인수 권리 부담


class LegalScoreResult(BaseModel):
    """법률 리스크 점수 최종 결과 (0~100, 높을수록 안전)"""

    score: float                          # 최종 점수 (신뢰도 적용 후)
    base_score: float                     # 3축 가중 합산 (신뢰도 적용 전)
    sub_scores: LegalSubScores
    confidence_multiplier: float = 1.0    # HIGH=1.0, MEDIUM=0.8, LOW=0.6
    has_hard_stop: bool = False
    needs_expert_review: bool = False     # 가처분/인수 과다 시 True
    confidence: str = "HIGH"              # HIGH / MEDIUM / LOW
    warnings: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)  # 디버깅용 (ratio, amounts 등)


class PriceSubScores(BaseModel):
    """가격 매력도 세부 점수 (각 0~100, 높을수록 매력적)"""

    discount_score: float = 0.0             # 할인율 (감정가 대비)
    market_compare_score: float = 0.0       # 시세 대비 매입 비율
    appraisal_accuracy_score: float = 0.0   # 감정가 신뢰도


class PriceScoreResult(BaseModel):
    """가격 매력도 점수 최종 결과 (0~100, 높을수록 좋은 거래)"""

    score: float                          # 최종 점수 (신뢰도 적용 후)
    base_score: float                     # 가중 합산 (신뢰도 적용 전)
    sub_scores: PriceSubScores
    confidence_multiplier: float = 1.0    # HIGH=1.0, MEDIUM=0.85, LOW=0.7
    confidence: str = "HIGH"              # HIGH / MEDIUM / LOW
    has_market_data: bool = True          # 시세 데이터 유무 (가중치 전환 기준)
    is_residential: bool = True           # 아파트/꼬마빌딩 (곡선 선택 기준)
    warnings: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


class TotalScoreResult(BaseModel):
    """통합 점수 최종 결과 (0~100, 높을수록 좋은 물건)"""

    total_score: float                          # 가중 합산 최종 점수
    score_coverage: float                       # 가용 가중치 합 (0~1.0)
    missing_pillars: list[str] = Field(default_factory=list)  # 미산출 pillar 이름
    grade: str = "D"                            # A(80+) / B(60~80) / C(40~60) / D(<40)
    property_category: str = "꼬마빌딩"         # 아파트 / 꼬마빌딩 / 토지
    weights_used: dict[str, float] = Field(default_factory=dict)  # 재정규화된 가중치
    legal_score: float | None = None
    price_score: float | None = None
    location_score: float | None = None
    occupancy_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    needs_expert_review: bool = False
    scorer_version: str = "v1.0"
    # 5.5: 낙찰가율 예측 (rule_v1: 유찰 횟수 기반 통계값)
    predicted_winning_ratio: float | None = None  # 예측 낙찰가율 (0~1.0)
    prediction_method: str = "rule_v1"            # 'rule_v1' | 'model_v1' (Phase 9)



# EvaluationResult는 순환 참조 방지를 위해 engine.py에 정의
