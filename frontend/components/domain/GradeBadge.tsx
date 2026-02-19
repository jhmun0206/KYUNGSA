import { cn } from "@/lib/utils"
import { GRADE_BG } from "@/lib/constants"

interface Props {
  grade: string | null
  size?: "sm" | "md" | "lg"
  provisional?: boolean
  className?: string
}

/** 등급 배지 — lg 사이즈에서 "정량평가" 서브텍스트 노출 */
export function GradeBadge({ grade, size = "md", provisional = false, className }: Props) {
  if (!grade) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full bg-gray-100 text-gray-400 ring-1 ring-gray-200",
          size === "sm" && "px-1.5 py-0.5 text-xs",
          size === "md" && "px-2 py-0.5 text-sm font-semibold",
          size === "lg" && "px-3 py-1 text-base font-bold",
          className
        )}
      >
        -
      </span>
    )
  }

  const bg = GRADE_BG[grade] ?? "bg-gray-100 text-gray-600 ring-gray-200"

  if (size === "lg") {
    return (
      <div className={cn("flex flex-col items-center gap-0.5", className)}>
        <span
          className={cn(
            "inline-flex items-center rounded-lg px-4 py-1.5 text-xl font-black ring-1",
            bg
          )}
        >
          {grade}등급{provisional && <span className="ml-1 text-xs font-normal opacity-70">*</span>}
        </span>
        <span className="text-xs text-text-weak">정량평가</span>
      </div>
    )
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-semibold ring-1",
        size === "sm" && "px-1.5 py-0.5 text-xs",
        size === "md" && "px-2.5 py-1 text-sm",
        bg,
        className
      )}
    >
      {grade}{provisional && <span className="ml-0.5 text-xs opacity-70">*</span>}
    </span>
  )
}
