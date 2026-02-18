import { GRADE_BG } from "@/lib/constants"

interface Props {
  grade: string | null
  provisional?: boolean
  size?: "sm" | "lg"
}

export function GradeBadge({ grade, provisional = false, size = "sm" }: Props) {
  if (!grade) {
    return (
      <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500">
        미평가
      </span>
    )
  }

  const cls = GRADE_BG[grade] || "bg-gray-100 text-gray-600"
  const sizeClass = size === "lg" ? "text-2xl px-4 py-1.5 rounded-xl" : "text-xs px-2 py-0.5 rounded"

  return (
    <span className={`inline-flex items-center font-bold ${sizeClass} ${cls}`}>
      {grade}
      {provisional && <span className="ml-1 text-xs font-normal opacity-70">(잠정)</span>}
    </span>
  )
}
