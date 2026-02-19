export const GRADE_COLORS: Record<string, string> = {
  A: "#10B981",  // emerald
  B: "#2563EB",  // blue
  C: "#D97706",  // amber
  D: "#DC2626",  // red
}

export const GRADE_BG: Record<string, string> = {
  A: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  B: "bg-blue-50 text-blue-700 ring-blue-200",
  C: "bg-amber-50 text-amber-700 ring-amber-200",
  D: "bg-red-50 text-red-700 ring-red-200",
}

export const GRADE_LABEL: Record<string, string> = {
  A: "A등급",
  B: "B등급",
  C: "C등급",
  D: "D등급",
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

// 서울 5개 법원
export const COURT_LABELS: Record<string, string> = {
  B000210: "서울중앙",
  B000211: "서울남부",
  B000212: "서울서부",
  B000213: "서울북부",
  B000214: "서울동부",
}

export const COURT_OPTIONS = Object.entries(COURT_LABELS).map(
  ([code, label]) => ({ code, label })
)

export const PROPERTY_TYPE_OPTIONS = [
  "아파트",
  "오피스텔",
  "상가",
  "꼬마빌딩",
  "토지",
  "임야",
  "다세대",
  "연립",
]

export const GRADE_OPTIONS = ["A", "B", "C", "D"]
