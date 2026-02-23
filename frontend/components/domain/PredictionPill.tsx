import { cn } from "@/lib/utils"
import { formatPrice } from "@/lib/utils"
import type { MLPrediction } from "@/lib/types"

interface Props {
  /** ML 예측 데이터 (우선) */
  mlPrediction?: MLPrediction | null
  /** rule_v1 fallback용 ratio */
  ratio?: number | null
  /** 금액 계산용 감정가 */
  appraisedValue?: number | null
  className?: string
}

const CONFIDENCE_STYLES = {
  high: {
    label: "신뢰도 높음",
    dot: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
  },
  medium: {
    label: "신뢰도 보통",
    dot: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
  },
  low: {
    label: "참고용",
    dot: "bg-gray-400",
    text: "text-muted-foreground",
  },
} as const

/**
 * 모델 추정 낙찰가율 표시
 * - mlPrediction 있으면 ML 표시 (신뢰도 + 영향 요인)
 * - 없으면 ratio (rule_v1 fallback)
 * - 둘 다 없으면 "데이터 부족" 라벨
 * ⚠️ Public: "예측" 표현 금지. "모델 추정 범위 (참고)" 사용.
 */
export function PredictionPill({ mlPrediction, ratio, appraisedValue, className }: Props) {
  // ML 데이터가 있고 유효한 ratio가 있으면 ML 표시
  const mlRatio = mlPrediction?.predicted_ratio
  const effectiveRatio = mlRatio ?? ratio
  const isML = mlRatio != null

  if (!effectiveRatio) {
    return (
      <span className={cn("text-xs text-text-weak", className)}>
        추정 낙찰가율: 데이터 부족
      </span>
    )
  }

  const pct = (effectiveRatio * 100).toFixed(1)
  const estimatedPrice = isML && mlPrediction?.predicted_price
    ? mlPrediction.predicted_price
    : appraisedValue != null
      ? Math.round(appraisedValue * effectiveRatio)
      : null

  const confidence = isML ? mlPrediction!.confidence : "low"
  const style = CONFIDENCE_STYLES[confidence]
  const factors = isML ? mlPrediction!.top_factors : []

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {/* 비율 + 금액 */}
      <div className="flex items-center gap-1.5">
        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-sm font-bold tabular-nums text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800">
          {pct}%
        </span>
        {estimatedPrice != null && (
          <span className="text-xs text-muted-foreground">
            ≈ {formatPrice(estimatedPrice)}
          </span>
        )}
      </div>

      {/* 신뢰도 */}
      <div className="flex items-center gap-1">
        <span className={cn("inline-block h-1.5 w-1.5 rounded-full", style.dot)} />
        <span className={cn("text-[11px]", style.text)}>
          {style.label}
        </span>
        {!isML && (
          <span className="text-[11px] text-muted-foreground">(통계 기반)</span>
        )}
      </div>

      {/* 영향 요인 (ML일 때만, 상위 3개) */}
      {isML && factors.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          주요 영향: {factors.slice(0, 3).map((f) => f.feature).join(" · ")}
        </p>
      )}
    </div>
  )
}
