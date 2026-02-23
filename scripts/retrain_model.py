"""월간 모델 재학습 스크립트

기존 모델 대비 개선 시에만 교체. cron으로 월 1회 실행 권장.

사용법:
    # 서버
    cd /home/eric/projects/KYUNGSA
    PYTHONPATH=backend .venv/bin/python scripts/retrain_model.py

    # Mac
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate kyungsa
    PYTHONPATH=backend python scripts/retrain_model.py

    # 옵션
    --force          개선 여부와 무관하게 교체
    --dry-run        학습만 하고 저장하지 않음
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sklearn.metrics import mean_absolute_percentage_error  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.prediction.config import PredictionConfig  # noqa: E402
from app.services.prediction.data_pipeline import PredictionDataPipeline  # noqa: E402
from app.services.prediction.feature_engineer import FeatureEngineer  # noqa: E402
from app.services.prediction.trainer import PredictionTrainer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="월간 모델 재학습")
    parser.add_argument("--force", action="store_true", help="개선 여부와 무관하게 교체")
    parser.add_argument("--dry-run", action="store_true", help="학습만 하고 저장하지 않음")
    args = parser.parse_args()

    config = PredictionConfig()
    tag = datetime.now().strftime("%Y%m%d")

    # 1. 데이터 준비
    print("\n=== 1. 데이터 준비 ===")
    db = SessionLocal()
    try:
        pipeline = PredictionDataPipeline(db)
        raw_df = pipeline.extract_training_data()
    finally:
        db.close()

    if raw_df.empty:
        print("  데이터 없음. 종료.")
        return

    fe = FeatureEngineer(config)
    df = fe.transform(raw_df)
    print(f"  전체: {len(df):,}건")

    features = config.NUMERIC_FEATURES + config.CATEGORICAL_FEATURES

    # 2. CV 실행
    print(f"\n=== 2. CV (TimeSeriesSplit {config.CV_N_SPLITS}-fold) ===")
    trainer = PredictionTrainer(config)
    cv_results = trainer.cross_validate(df)

    for r in cv_results:
        print(
            f"  Fold {r['fold']}: MAPE={r['mape']:.1%}, "
            f"MAE={r['mae']:.4f} (train={r['n_train']:,}, val={r['n_val']:,})"
        )

    new_mape = sum(r["mape"] for r in cv_results) / len(cv_results)
    print(f"  New CV MAPE: {new_mape:.1%}")

    # 3. 기존 모델과 비교
    model_dir = Path(config.MODEL_DIR)
    old_model_path = model_dir / "model_v1.cbm"

    old_mape = None
    if old_model_path.exists():
        print("\n=== 3. 기존 모델 비교 ===")
        try:
            old_model = PredictionTrainer.load_model(old_model_path)

            # 테스트셋 (마지막 20%)
            split_idx = int(len(df) * 0.8)
            df_test = df.iloc[split_idx:]
            X_test = df_test[features].copy()
            for col in config.CATEGORICAL_FEATURES:
                X_test[col] = X_test[col].astype(str)
            y_test = df_test["target"].values

            old_preds = old_model.predict(X_test)
            old_mape = mean_absolute_percentage_error(y_test, old_preds)
            print(f"  기존 MAPE: {old_mape:.1%}")
            print(f"  신규 MAPE: {new_mape:.1%}")
            diff = old_mape - new_mape
            print(f"  개선: {diff:+.1%}p")
        except Exception as e:
            print(f"  기존 모델 비교 실패: {e}")
            old_mape = None
    else:
        print("\n=== 3. 기존 모델 없음 (신규 생성) ===")

    # 4. 교체 판단
    should_replace = args.force or old_mape is None or new_mape < old_mape
    reason = "force" if args.force else ("신규" if old_mape is None else f"개선 {old_mape - new_mape:+.4f}")

    if not should_replace:
        print(f"\n  기존 모델이 동등 이상 → 교체 안 함 (new={new_mape:.1%} >= old={old_mape:.1%})")
        return

    if args.dry_run:
        print(f"\n  --dry-run: 교체 스킵 (교체 사유: {reason})")
        return

    # 5. 전체 데이터로 학습 + 저장
    print(f"\n=== 4. 전체 학습 + 저장 (사유: {reason}) ===")
    trainer.train(df)

    # 기존 v1 백업
    if old_model_path.exists():
        backup_path = model_dir / f"model_v1_backup_{tag}.cbm"
        shutil.copy2(old_model_path, backup_path)
        print(f"  백업: {backup_path}")

    # 새 모델을 v1으로 저장 (항상 v1 이름 유지)
    model_path = trainer.save_model(tag="v1")
    print(f"  저장: {model_path}")

    # 6. 싱글턴 리셋 안내
    print("\n=== 완료 ===")
    print("  서버 반영: sudo systemctl restart kyungsa")
    print("  (WinningBidPredictor 싱글턴이 새 모델을 자동 로드)")


if __name__ == "__main__":
    main()
