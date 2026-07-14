import { SIGNAL_EMOJI, getSignalLabel, type SignalColor } from "@/lib/risk-signals"
import { cn } from "@/lib/utils"

/**
 * 리스크 신호등 뱃지 — 목록/비교 화면의 유일한 1차 평가 지표.
 * 등급(A~D)·종합점수는 상세 페이지의 보조 지표로만 사용한다.
 */
export function SignalBadge({
  color,
  size = "sm",
  className,
}: {
  color: SignalColor
  size?: "sm" | "md"
  className?: string
}) {
  return (
    <span
      title={`리스크 ${getSignalLabel(color)}`}
      className={cn("inline-flex flex-col items-center leading-none", className)}
    >
      <span className={size === "md" ? "text-xl" : "text-base"}>
        {SIGNAL_EMOJI[color]}
      </span>
      <span className="mt-0.5 text-[9px] font-medium text-muted-foreground">
        {getSignalLabel(color)}
      </span>
    </span>
  )
}
