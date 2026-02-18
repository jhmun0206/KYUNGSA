export const GRADE_COLORS: Record<string, string> = {
  A: "#10B981",  // 에메랄드
  B: "#3B82F6",  // 블루
  C: "#F59E0B",  // 앰버
  D: "#EF4444",  // 레드
}

export const GRADE_BG: Record<string, string> = {
  A: "bg-emerald-100 text-emerald-800",
  B: "bg-blue-100 text-blue-800",
  C: "bg-amber-100 text-amber-800",
  D: "bg-red-100 text-red-800",
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
