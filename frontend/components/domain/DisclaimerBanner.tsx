import { Info } from "lucide-react"
import { cn } from "@/lib/utils"

interface Props {
  className?: string
  compact?: boolean
}

/** 면책 고지 배너 */
export function DisclaimerBanner({ className, compact = false }: Props) {
  if (compact) {
    return (
      <div className={cn("flex items-start gap-1.5 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground", className)}>
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          이 서비스는 공공데이터 기반 필터링 결과를 제공하며, 투자 추천이나 법률 판단이 아닙니다.
          최종 판단은 전문가와 함께 확인하세요.
        </span>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300",
        className
      )}
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="space-y-0.5">
        <p className="font-medium">분석 결과 활용 안내</p>
        <p className="text-xs leading-relaxed">
          이 서비스는 공공데이터 기반의 자동화 필터링 결과를 제공합니다.
          투자 추천·법률 판단·입찰 조언이 아니며, 개별 물건에 대한 전문가 검토를 반드시 거치세요.
          데이터 기준일 이후의 변동사항은 반영되지 않을 수 있습니다.
        </p>
      </div>
    </div>
  )
}
