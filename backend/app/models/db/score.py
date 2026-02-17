"""Score ORM 모델

통합 점수 결과. Auction과 1:1 관계.
5E: legal + price. Phase 6/7에서 location + occupancy 추가.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, JSONBOrJSON, PrimaryKeyMixin


class Score(PrimaryKeyMixin, Base):
    """통합 점수"""

    __tablename__ = "scores"

    auction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("auctions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    property_category: Mapped[str] = mapped_column(String(20), nullable=False, default="꼬마빌딩")

    # pillar 점수 (개별 저장)
    legal_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_score: Mapped[float | None] = mapped_column(Float, nullable=True)     # Phase 6
    occupancy_score: Mapped[float | None] = mapped_column(Float, nullable=True)    # Phase 7

    # 통합 결과
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    missing_pillars: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=False, default=list)
    grade: Mapped[str | None] = mapped_column(String(1), nullable=True)
    grade_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Phase 6
    sub_scores: Mapped[dict | None] = mapped_column(JSONBOrJSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSONBOrJSON, nullable=True, default=list)
    needs_expert_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 5.5 낙찰가율 예측 (rule_v1: 유찰 횟수 기반 통계값)
    predicted_winning_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_method: Mapped[str] = mapped_column(String(30), nullable=False, default="rule_v1")

    # 5F 캘리브레이션용
    actual_winning_bid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_winning_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_error: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 메타
    scorer_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0")
    scored_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    pipeline_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # 관계
    auction: Mapped[Auction] = relationship("Auction", back_populates="score")

    __table_args__ = (
        Index("ix_scores_total", "total_score"),
        Index("ix_scores_grade", "grade"),
        Index("ix_scores_coverage", "score_coverage"),
        Index("ix_scores_category", "property_category"),
        Index("ix_scores_scored_at", "scored_at"),
    )

    def __repr__(self) -> str:
        return f"<Score {self.grade} total={self.total_score} auction={self.auction_id}>"


from app.models.db.auction import Auction  # noqa: E402
