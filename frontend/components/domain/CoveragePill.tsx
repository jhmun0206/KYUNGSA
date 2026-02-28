import { cn } from "@/lib/utils"

const THRESHOLDS = {
  card:   { high: 60, mid: 40 },
  detail: { high: 70, mid: 40 },
} as const

type CoverageVariant = keyof typeof THRESHOLDS

interface Props {
  coverage: number | null | undefined
  variant?: CoverageVariant
  className?: string
}

/** 분석 커버리지 프로그레스 바 — variant별 임계값 적용 */
export function CoveragePill({ coverage, variant = "card", className }: Props) {
  if (coverage == null) {
    return (
      <span className={cn("text-xs text-text-weak", className)}>커버리지 -</span>
    )
  }

  const pct = Math.round(coverage * 100)
  const { high, mid } = THRESHOLDS[variant]
  const barColor =
    pct >= high ? "bg-primary" : pct >= mid ? "bg-amber-400" : "bg-red-400"
  const textColor =
    pct >= high ? "text-primary" : pct >= mid ? "text-amber-600" : "text-red-500"

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-border">
        <div
          className={cn("h-full rounded-full transition-all", barColor)}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className={cn("text-xs font-medium tabular-nums", textColor)}>
        {pct}%
      </span>
    </div>
  )
}
