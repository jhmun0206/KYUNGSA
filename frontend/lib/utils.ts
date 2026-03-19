import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** 면적(㎡) 표시 — 정수면 그대로, 소수 있으면 1자리 (예: 1012.0→"1012", 33.05→"33.1") */
export function formatArea(area: number | null | undefined): string {
  if (area == null || area === 0) return '-'
  return area % 1 === 0 ? `${area}` : `${area.toFixed(1)}`
}

/** 만원 → 억/만 표기 (cashflow 컴포넌트 전용, 예: 30000 → "3억") */
export function formatMan(manwon: number | null | undefined): string {
  if (manwon == null || isNaN(manwon)) return "-"
  if (manwon === 0) return "0만원"
  return formatPrice(manwon * 10000)
}

/** 원 → 억/만 표기 (예: 3억 2,000만) */
export function formatPrice(won: number | null | undefined): string {
  if (won == null) return "-"
  const uk = Math.floor(Math.abs(won) / 100000000)
  const man = Math.floor((Math.abs(won) % 100000000) / 10000)
  if (uk > 0 && man > 0) return `${uk}억 ${man.toLocaleString()}만`
  if (uk > 0) return `${uk}억`
  if (man > 0) return `${man.toLocaleString()}만`
  return `${(Math.abs(won) / 10000).toLocaleString()}만`
}

/** 경매일 기준 D-day 계산 (예: "D-3", "D+2", "오늘") */
export function calcDday(dateStr: string | null | undefined, status?: string | null): string {
  if (status === "기일경과") return "기일경과"
  if (status === "매각") return "매각완료"
  if (!dateStr) return "-"
  const target = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  const diff = Math.round((target.getTime() - today.getTime()) / 86400000)
  if (diff === 0) return "오늘"
  if (diff > 0) return `D-${diff}`
  return `D+${Math.abs(diff)}`
}

/** 할인율 계산 (최저가/감정가, 0~1 사이) */
export function calcDiscount(
  minBid: number | null | undefined,
  appraised: number | null | undefined
): number | null {
  if (!minBid || !appraised || appraised === 0) return null
  return 1 - minBid / appraised
}

/** 법원명 단축 (서울중앙지방법원 → 서울중앙) */
export function shortCourtName(court: string): string {
  return court.replace(/지방법원.*/, "").replace(/지원.*/, "지원").trim()
}

/** 주소 축약 (앞 20자 + ...) */
export function truncateAddress(addr: string, maxLen = 25): string {
  if (addr.length <= maxLen) return addr
  return addr.slice(0, maxLen) + "…"
}

/** 매각기일까지 남은 일수 (숫자). 음수=지남, 0=오늘, 양수=미래 */
export function calcDdayNumber(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null
  const target = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86400000)
}

/** D-day에 따른 Tailwind 색상 클래스 */
export function getDdayColor(dateStr: string | null | undefined): string {
  const dday = calcDdayNumber(dateStr)
  if (dday === null) return "text-muted-foreground"
  if (dday < 0) return "text-muted-foreground line-through"
  if (dday === 0) return "text-destructive font-bold"
  if (dday <= 3) return "text-destructive font-bold"
  if (dday <= 7) return "text-orange-500 font-semibold"
  return "text-muted-foreground"
}

/** pillar 점수 기반 간략 리스크 요약 (리스트 행에 표시)
 *  70+ → 양호, 50-69 → 보통, <50 → 주의 */
export function getPillarSummary(scores: {
  price_score: number | null
  location_score: number | null
  occupancy_score: number | null
}): { text: string; colorClass: string }[] {
  const PILLARS = [
    { key: "price_score" as const, label: "수익성" },
    { key: "location_score" as const, label: "입지" },
    { key: "occupancy_score" as const, label: "명도" },
  ]
  return PILLARS
    .filter((p) => scores[p.key] != null)
    .map((p) => {
      const v = scores[p.key]!
      if (v >= 70) return { text: `${p.label} 양호`, colorClass: "text-emerald-600 dark:text-emerald-400" }
      if (v >= 50) return { text: `${p.label} 보통`, colorClass: "text-amber-600 dark:text-amber-400" }
      return { text: `${p.label} 주의`, colorClass: "text-red-500 dark:text-red-400" }
    })
}

/** 점수 구간별 해석 텍스트 + 색상 반환 */
export function getScoreInterpretation(score: number | null): {
  text: string
  colorClass: string
} {
  if (score == null) return { text: "데이터 부족", colorClass: "text-muted-foreground" }
  if (score >= 80) return { text: "매우 양호", colorClass: "text-emerald-600 dark:text-emerald-400" }
  if (score >= 60) return { text: "양호", colorClass: "text-blue-600 dark:text-blue-400" }
  if (score >= 40) return { text: "주의 필요", colorClass: "text-amber-600 dark:text-amber-400" }
  return { text: "위험", colorClass: "text-red-600 dark:text-red-400" }
}
