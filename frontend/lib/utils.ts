import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
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
export function calcDday(dateStr: string | null | undefined): string {
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
