"""Phase 5F 백테스트 — 낙찰가율 분포 + 예측 정확도 분석

수집된 낙찰 데이터(auctions.winning_ratio)를 기반으로:
  A. 기본 통계: 전체 낙찰가율 분포, 용도별/유찰횟수별/법원별 평균
  B. 예측 정확도: predicted vs actual winning_ratio (Score 있는 물건)
  C. 상관 분석: total_score와 actual_winning_ratio의 관계

출력: 콘솔 표 형식 (외부 라이브러리 없음, stdlib만 사용)

사용법:
    # 서버
    PYTHONPATH=backend backend/.venv/bin/python scripts/backtest_scores.py
    # Mac dev
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate kyungsa
    PYTHONPATH=backend python scripts/backtest_scores.py
"""

from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# PYTHONPATH 자동 설정
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402


# ─────────────────────────────────────────────
# 헬퍼: 출력 유틸
# ─────────────────────────────────────────────


def _header(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def _table(rows: list[tuple[Any, ...]], headers: list[str]) -> None:
    """간단한 텍스트 테이블 출력"""
    widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
              for i, h in enumerate(headers)]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    sep = "  " + "  ".join("-" * w for w in widths)
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*[str(v) for v in row]))


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _stats(values: list[float]) -> dict[str, str]:
    if not values:
        return {"count": "0", "mean": "-", "median": "-", "std": "-", "min": "-", "max": "-"}
    return {
        "count": str(len(values)),
        "mean": _pct(statistics.mean(values)),
        "median": _pct(statistics.median(values)),
        "std": _pct(statistics.stdev(values) if len(values) > 1 else 0.0),
        "min": _pct(min(values)),
        "max": _pct(max(values)),
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """피어슨 상관계수 (stdlib만 사용)"""
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(
        sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)
    )
    return num / den if den else None


# ─────────────────────────────────────────────
# 분석 A: 기본 통계 (전체 낙찰 데이터)
# ─────────────────────────────────────────────


def analyze_basic(db) -> dict[str, list[float]]:
    """전체 낙찰가율 분포 분석"""
    _header("A. 기본 통계 — 전체 낙찰 데이터")

    # A-1. 전체 winning_ratio 분포
    rows = db.execute(text(
        """
        SELECT winning_ratio, property_type, bid_count, court_office_code
        FROM auctions
        WHERE winning_ratio IS NOT NULL
        ORDER BY winning_ratio
        """
    )).fetchall()

    all_ratios = [r[0] for r in rows]
    s = _stats(all_ratios)
    print(f"\n[전체] 낙찰가율 기본 통계")
    print(f"  건수:     {s['count']}건")
    print(f"  평균:     {s['mean']}")
    print(f"  중앙값:   {s['median']}")
    print(f"  표준편차: {s['std']}")
    print(f"  범위:     {s['min']} ~ {s['max']}")

    # A-2. 용도별 평균 낙찰가율
    by_type: dict[str, list[float]] = defaultdict(list)
    for ratio, ptype, _, _ in rows:
        key = ptype if ptype else "미분류"
        by_type[key].append(ratio)

    print(f"\n[용도별] 평균 낙찰가율 (건수 내림차순)")
    type_rows = sorted(
        [(k, len(v), statistics.mean(v), statistics.median(v))
         for k, v in by_type.items()],
        key=lambda x: -x[1],
    )
    _table(
        [(k, cnt, _pct(m), _pct(med)) for k, cnt, m, med in type_rows[:15]],
        ["용도", "건수", "평균", "중앙값"],
    )

    # A-3. 유찰횟수별 평균 낙찰가율 (bid_count - 1 = 유찰횟수)
    by_fail: dict[int, list[float]] = defaultdict(list)
    for ratio, _, bid_count, _ in rows:
        fail = max(0, (bid_count or 1) - 1)
        by_fail[fail].append(ratio)

    print(f"\n[유찰횟수별] 평균 낙찰가율")
    fail_rows = sorted(
        [(fail, len(v), statistics.mean(v), statistics.median(v))
         for fail, v in by_fail.items()],
        key=lambda x: x[0],
    )
    _table(
        [(f"{f}회", cnt, _pct(m), _pct(med)) for f, cnt, m, med in fail_rows],
        ["유찰횟수", "건수", "평균", "중앙값"],
    )

    # A-4. 법원별 평균 낙찰가율 (상위 10개, 건수 기준)
    by_court: dict[str, list[float]] = defaultdict(list)
    for ratio, _, _, court_code in rows:
        by_court[court_code or "미상"].append(ratio)

    print(f"\n[법원별] 평균 낙찰가율 (상위 10개)")
    court_rows = sorted(
        [(k, len(v), statistics.mean(v), statistics.median(v))
         for k, v in by_court.items()],
        key=lambda x: -x[1],
    )[:10]
    _table(
        [(k, cnt, _pct(m), _pct(med)) for k, cnt, m, med in court_rows],
        ["법원코드", "건수", "평균", "중앙값"],
    )

    # A-5. 낙찰가율 구간 분포 (히스토그램)
    print(f"\n[낙찰가율 분포] 구간별 건수")
    buckets = [
        ("~60%",  0.0, 0.60),
        ("60~70%", 0.60, 0.70),
        ("70~80%", 0.70, 0.80),
        ("80~90%", 0.80, 0.90),
        ("90~100%", 0.90, 1.00),
        ("100~110%", 1.00, 1.10),
        ("110%+",   1.10, 9.99),
    ]
    hist_rows = []
    total_n = len(all_ratios)
    for label, lo, hi in buckets:
        cnt = sum(1 for r in all_ratios if lo <= r < hi)
        bar = "█" * (cnt * 30 // max(total_n, 1))
        hist_rows.append((label, cnt, f"{cnt/total_n*100:.1f}%", bar))
    _table(hist_rows, ["구간", "건수", "비율", "분포"])

    return {"all_ratios": all_ratios}


# ─────────────────────────────────────────────
# 분석 B: 예측 정확도 (Score 있는 물건)
# ─────────────────────────────────────────────


def analyze_prediction(db) -> dict[str, list[float]]:
    """predicted vs actual winning_ratio 비교"""
    _header("B. 예측 정확도 — predicted vs actual (Score 있는 물건)")

    rows = db.execute(text(
        """
        SELECT s.predicted_winning_ratio,
               s.actual_winning_ratio,
               s.prediction_error,
               s.property_category,
               s.grade,
               s.total_score
        FROM scores s
        WHERE s.predicted_winning_ratio IS NOT NULL
          AND s.actual_winning_ratio IS NOT NULL
        ORDER BY s.actual_winning_ratio
        """
    )).fetchall()

    if not rows:
        print("\n  ⚠ 예측 + 실제 낙찰가율이 모두 있는 물건이 없습니다.")
        print("    (배치 수집 → 낙찰 → SaleResultCollector/WinningBidCollector 실행 후 재분석)")
        return {}

    predicted = [r[0] for r in rows]
    actual    = [r[1] for r in rows]
    errors    = [abs(r[1] - r[0]) for r in rows]  # MAE용 절댓값 오차
    raw_errs  = [r[2] for r in rows if r[2] is not None]

    print(f"\n[예측 정확도] 전체 {len(rows)}건")
    print(f"  MAE (절댓값평균오차): {_pct(statistics.mean(errors))}")
    print(f"  중앙값 오차:          {_pct(statistics.median(errors))}")
    print(f"  표준편차:             {_pct(statistics.stdev(errors) if len(errors) > 1 else 0.0)}")

    # 오차 방향 (예측이 낙관적이었는지 비관적이었는지)
    if raw_errs:
        mean_err = statistics.mean(raw_errs)
        bias = "낙관적 예측 (예측 > 실제)" if mean_err < 0 else "보수적 예측 (예측 < 실제)"
        print(f"  평균 부호 오차:       {_pct(abs(mean_err))} ({bias})")

    # B-1. 용도(property_category)별 예측 정확도
    by_cat: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_cat[r[3] or "미분류"].append(abs(r[1] - r[0]))

    print(f"\n[용도별] MAE")
    _table(
        [(k, len(v), _pct(statistics.mean(v)), _pct(statistics.median(v)))
         for k, v in sorted(by_cat.items(), key=lambda x: -len(x[1]))],
        ["용도", "건수", "MAE", "중앙값"],
    )

    # B-2. 등급별 예측 정확도
    by_grade: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by_grade[r[4] or "?"].append(abs(r[1] - r[0]))

    if len(by_grade) > 1:
        print(f"\n[등급별] MAE")
        _table(
            [(k, len(v), _pct(statistics.mean(v)))
             for k, v in sorted(by_grade.items())],
            ["등급", "건수", "MAE"],
        )

    return {"predicted": predicted, "actual": actual}


# ─────────────────────────────────────────────
# 분석 C: 상관 분석
# ─────────────────────────────────────────────


def analyze_correlation(db) -> None:
    """total_score와 actual_winning_ratio의 상관관계"""
    _header("C. 상관 분석 — total_score vs actual_winning_ratio")

    rows = db.execute(text(
        """
        SELECT s.total_score, s.actual_winning_ratio, s.grade
        FROM scores s
        WHERE s.actual_winning_ratio IS NOT NULL
          AND s.total_score IS NOT NULL
        """
    )).fetchall()

    if not rows:
        print("\n  ⚠ total_score + actual_winning_ratio 쌍이 없습니다.")
        print("    (배치 수집 물건이 낙찰된 후 재분석 필요)")
        return

    scores = [r[0] for r in rows]
    actuals = [r[1] for r in rows]

    corr = _pearson(scores, actuals)
    print(f"\n[상관계수] 피어슨 r = {corr:.4f if corr is not None else 'N/A'}")
    if corr is not None:
        strength = (
            "강한 양의 상관" if corr > 0.7
            else "중간 양의 상관" if corr > 0.4
            else "약한 양의 상관" if corr > 0.2
            else "상관 없음 또는 음의 상관"
        )
        print(f"           해석: {strength}")

    # 점수 구간별 평균 낙찰가율
    print(f"\n[점수 구간별] 평균 낙찰가율")
    buckets = [(0, 40), (40, 60), (60, 80), (80, 101)]
    bucket_rows = []
    for lo, hi in buckets:
        vals = [r[1] for r in rows if lo <= r[0] < hi]
        if vals:
            bucket_rows.append((
                f"{lo}~{hi}점",
                len(vals),
                _pct(statistics.mean(vals)),
                _pct(statistics.median(vals)),
            ))
    if bucket_rows:
        _table(bucket_rows, ["점수 구간", "건수", "평균 낙찰가율", "중앙값"])
    else:
        print("  데이터 없음")


# ─────────────────────────────────────────────
# 분석 D: _PREDICTED_RATIO_TABLE 캘리브레이션 제안
# ─────────────────────────────────────────────


def analyze_calibration(db) -> None:
    """유찰횟수별 실제 낙찰가율 → _PREDICTED_RATIO_TABLE 캘리브레이션 제안"""
    _header("D. 캘리브레이션 제안 — 유찰횟수별 실제 낙찰가율 (전체 데이터)")

    # 현재 rule_v1 테이블 (참고용)
    current_table = {
        "아파트":  {0: 0.975, 1: 0.90, 2: 0.80, 3: 0.70, "4+": 0.60},
        "꼬마빌딩": {0: 0.90,  1: 0.80, 2: 0.70, 3: 0.60, "4+": 0.50},
        "토지":    {0: 0.85,  1: 0.75, 2: 0.65, 3: 0.55, "4+": 0.45},
    }

    # bid_count - 1 = 유찰횟수 그룹별 실제 낙찰가율
    rows = db.execute(text(
        """
        SELECT a.bid_count, a.property_type, a.winning_ratio
        FROM auctions a
        WHERE a.winning_ratio IS NOT NULL
          AND a.bid_count IS NOT NULL
        """
    )).fetchall()

    if not rows:
        print("\n  데이터 없음")
        return

    # 용도 정규화
    def _normalize_type(pt: str) -> str:
        pt = (pt or "").strip()
        if "아파트" in pt:
            return "아파트"
        if any(k in pt for k in ["단독", "다가구", "다세대", "빌라", "연립", "오피스텔", "상가", "근린", "공장", "창고"]):
            return "꼬마빌딩"
        if "토지" in pt or "임야" in pt or "농지" in pt:
            return "토지"
        return "꼬마빌딩"  # 기본값

    by_fail_type: dict[tuple[str, int], list[float]] = defaultdict(list)
    for bid_count, ptype, ratio in rows:
        fail = max(0, (bid_count or 1) - 1)
        fail_key = min(fail, 4)  # 4+ 그룹화
        cat = _normalize_type(ptype)
        by_fail_type[(cat, fail_key)].append(ratio)

    print(f"\n[현재 rule_v1 테이블 vs 실제 데이터 비교]")
    print(f"  {'카테고리':<8}  {'유찰':>4}  {'현재예측':>8}  {'실제평균':>8}  {'실제중앙값':>10}  {'건수':>5}  {'차이':>7}")
    print(f"  {'-'*8}  {'-'*4}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*5}  {'-'*7}")

    for cat in ["아파트", "꼬마빌딩", "토지"]:
        for fail_key in range(5):
            vals = by_fail_type.get((cat, fail_key), [])
            cur_key = fail_key if fail_key < 4 else "4+"
            cur = current_table[cat].get(cur_key, "-")
            if vals:
                actual_mean = statistics.mean(vals)
                actual_med  = statistics.median(vals)
                diff = actual_mean - (cur if isinstance(cur, float) else 0)
                fail_label = f"{fail_key}회" if fail_key < 4 else "4+회"
                print(
                    f"  {cat:<8}  {fail_label:>4}  {_pct(cur) if isinstance(cur,float) else '-':>8}  "
                    f"{_pct(actual_mean):>8}  {_pct(actual_med):>10}  {len(vals):>5}  "
                    f"{'+' if diff > 0 else ''}{_pct(diff):>6}"
                )

    print("\n  [주의] 건수가 적을 때(<30건) 캘리브레이션 수치는 신뢰도 낮음")
    print("         충분한 데이터 축적 후 total_scorer.py _PREDICTED_RATIO_TABLE 업데이트 권장")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("  KYUNGSA Phase 5F 백테스트 분석")
    print("  낙찰가율 분포 + 예측 정확도 + 상관 분석")
    print("=" * 60)

    db = SessionLocal()
    try:
        # DB 연결 확인
        result = db.execute(text("SELECT COUNT(*) FROM auctions WHERE winning_ratio IS NOT NULL")).scalar()
        print(f"\n낙찰가율 데이터: {result}건 (auctions.winning_ratio IS NOT NULL)")

        score_result = db.execute(
            text("SELECT COUNT(*) FROM scores WHERE predicted_winning_ratio IS NOT NULL")
        ).scalar()
        print(f"예측 데이터:     {score_result}건 (scores.predicted_winning_ratio IS NOT NULL)")

        if result == 0:
            print("\n  ⚠ 낙찰가율 데이터가 없습니다. 아래 명령으로 먼저 수집하세요:")
            print("    PYTHONPATH=backend python scripts/collect_sale_results.py --all-courts")
            return

        analyze_basic(db)
        analyze_prediction(db)
        analyze_correlation(db)
        analyze_calibration(db)

        print(f"\n{'═' * 60}")
        print("  분석 완료")
        print(f"{'═' * 60}\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
