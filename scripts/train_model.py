"""낙찰가율 예측 모델 학습

사용법:
    # 서버
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/train_model.py
    PYTHONPATH=backend .venv/bin/python scripts/train_model.py --cv-only
    PYTHONPATH=backend .venv/bin/python scripts/train_model.py --tag v1

    # Mac
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate kyungsa
    PYTHONPATH=backend python scripts/train_model.py --cv-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal  # noqa: E402
from app.services.prediction.config import PredictionConfig  # noqa: E402
from app.services.prediction.data_pipeline import PredictionDataPipeline  # noqa: E402
from app.services.prediction.feature_engineer import FeatureEngineer  # noqa: E402
from app.services.prediction.trainer import PredictionTrainer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="낙찰가율 예측 모델 학습")
    parser.add_argument("--cv-only", action="store_true", help="CV만 실행, 모델 저장 안 함")
    parser.add_argument("--tag", type=str, default=None, help="모델 태그 (기본: YYYYMMDD)")
    args = parser.parse_args()

    config = PredictionConfig()

    # 1. 데이터 추출
    print("\n=== Data ===")
    db = SessionLocal()
    try:
        pipeline = PredictionDataPipeline(db)
        raw_df = pipeline.extract_training_data()
    finally:
        db.close()

    if raw_df.empty:
        print("  데이터 없음. 종료.")
        return

    print(f"  추출: {len(raw_df):,}건")

    # 2. 피처 엔지니어링
    fe = FeatureEngineer(config)
    df = fe.transform(raw_df)
    features = config.NUMERIC_FEATURES + config.CATEGORICAL_FEATURES
    print(f"  피처: 수치형 {len(config.NUMERIC_FEATURES)}개 "
          f"+ 범주형 {len(config.CATEGORICAL_FEATURES)}개 = {len(features)}개")

    # 3. Cross-Validation
    print(f"\n=== Cross-Validation (TimeSeriesSplit {config.CV_N_SPLITS}-fold) ===")
    trainer = PredictionTrainer(config)
    cv_results = trainer.cross_validate(df)

    for r in cv_results:
        print(
            f"  Fold {r['fold']}: MAPE={r['mape']:.1%}, "
            f"MAE={r['mae']:.4f}, RMSE={r['rmse']:.4f} "
            f"(train={r['n_train']:,}, val={r['n_val']:,}) "
            f"[{r['val_period']}]"
        )

    avg_mape = sum(r["mape"] for r in cv_results) / len(cv_results)
    avg_mae = sum(r["mae"] for r in cv_results) / len(cv_results)
    avg_rmse = sum(r["rmse"] for r in cv_results) / len(cv_results)
    print(f"  {'─' * 50}")
    print(f"  Average: MAPE={avg_mape:.1%}, MAE={avg_mae:.4f}, RMSE={avg_rmse:.4f}")

    if args.cv_only:
        print("\n  --cv-only: 모델 저장 스킵")
        return

    # 4. 전체 데이터로 학습
    print("\n=== Training (full data) ===")
    trainer.train(df)

    # 5. 피처 중요도
    print("\n=== Feature Importance (Top 10) ===")
    sorted_imp = sorted(
        trainer.feature_importances.items(),
        key=lambda x: x[1], reverse=True,
    )
    for i, (feat, imp) in enumerate(sorted_imp[:10], 1):
        print(f"  {i:2d}. {feat:<28s} {imp:.1f}%")

    # 6. 저장
    model_path = trainer.save_model(tag=args.tag)
    meta_name = f"metadata_{args.tag or model_path.stem.replace('model_', '')}.json"
    print(f"\n=== Model Saved ===")
    print(f"  Path: {model_path}")
    print(f"  Meta: {model_path.parent / meta_name}")


if __name__ == "__main__":
    main()
