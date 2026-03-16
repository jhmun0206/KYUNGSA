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

// v2.0 물건 유형 카테고리 (7종, DB property_type 정규화)
export const PROPERTY_CATEGORIES = [
  { value: "아파트", label: "아파트" },
  { value: "오피스텔", label: "오피스텔" },
  { value: "다세대/빌라", label: "다세대/빌라" },
  { value: "단독/다가구", label: "단독/다가구" },
  { value: "상가/근생", label: "상가/근생" },
  { value: "토지", label: "토지" },
] as const

// 서울 25개 자치구
export const SEOUL_DISTRICTS = [
  "강남구", "강동구", "강북구", "강서구",
  "관악구", "광진구", "구로구", "금천구",
  "노원구", "도봉구", "동대문구", "동작구",
  "마포구", "서대문구", "서초구", "성동구",
  "성북구", "송파구", "양천구", "영등포구",
  "용산구", "은평구", "종로구", "중구", "중랑구",
]

export const GRADE_OPTIONS = ["A", "B", "C", "D"]

export const PRICE_RANGES = [
  { label: '전체', min: null, max: null },
  { label: '3억 미만', min: null, max: 300000000 },
  { label: '3억~5억', min: 300000000, max: 500000000 },
  { label: '5억~10억', min: 500000000, max: 1000000000 },
  { label: '10억~20억', min: 1000000000, max: 2000000000 },
  { label: '20억 이상', min: 2000000000, max: null },
] as const

export const SORT_OPTIONS = [
  { value: 'auction_date', label: '매각기일순' },
  { value: 'discount_rate', label: '할인율순' },
  { value: 'bid_count', label: '유찰많은순' },
  { value: 'appraised_value', label: '감정가순' },
  { value: 'minimum_bid', label: '최저가순' },
] as const
