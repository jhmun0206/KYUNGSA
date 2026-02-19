import { cn } from "@/lib/utils"

interface Props {
  coverage: number | null | undefined
  className?: string
}

/** 분석 커버리지 프로그레스 바 — ≥75% primary, 50~74% amber, <50% red */
export function CoveragePill({ coverage, className }: Props) {
  if (coverage == null) {
    return (
      <span className={cn("text-xs text-text-weak", className)}>커버리지 -</span>
    )
  }

  const pct = Math.round(coverage * 100)
  const barColor =
    pct >= 75 ? "bg-primary" : pct >= 50 ? "bg-amber-400" : "bg-red-400"
  const textColor =
    pct >= 75 ? "text-primary" : pct >= 50 ? "text-amber-600" : "text-red-500"

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
