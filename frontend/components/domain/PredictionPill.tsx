import { cn } from "@/lib/utils"
import { formatPrice } from "@/lib/utils"

interface Props {
  ratio: number | null | undefined
  minimumBid: number | null | undefined
  className?: string
}

/**
 * 모델 추정 낙찰가율 표시
 * - ratio null → 사유 라벨 표시
 * - ratio 있으면 "모델 추정 범위 (참고)" + 금액 표시
 * ⚠️ Public: "예상 낙찰가" 표현 금지. "모델 추정 범위 (참고)" 사용.
 */
export function PredictionPill({ ratio, minimumBid, className }: Props) {
  if (!ratio) {
    return (
      <span className={cn("text-xs text-text-weak", className)}>
        추정 낙찰가율: 데이터 부족
      </span>
    )
  }

  const pct = Math.round(ratio * 100)
  const estimatedAmount =
    minimumBid != null ? Math.round((minimumBid * ratio) / 10000) * 10000 : null

  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-text-weak">모델 추정 범위 (참고)</span>
        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">
          {pct}%
        </span>
      </div>
      {estimatedAmount != null && (
        <span className="text-xs text-text-mid">
          ≈ {formatPrice(estimatedAmount)} 내외
        </span>
      )}
    </div>
  )
}
