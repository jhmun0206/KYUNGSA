// frontend/lib/risk-signals.ts

import type { AuctionDetailResponse } from "@/lib/types"

export type SignalColor = 'green' | 'yellow' | 'red' | 'unknown'

export interface RiskSignal {
  category: string
  color: SignalColor
  label: string
  reason: string
  detail?: string[]
  actionUrl?: string
  actionLabel?: string
}

// 신호등 이모지
export const SIGNAL_EMOJI: Record<SignalColor, string> = {
  green: '🟢',
  yellow: '🟡',
  red: '🔴',
  unknown: '⚫',
}

// 신호등 색상 클래스 (기존 호환)
export const SIGNAL_CLASS: Record<SignalColor, string> = {
  green: 'text-green-600 bg-green-50 border-green-200',
  yellow: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  red: 'text-red-600 bg-red-50 border-red-200',
  unknown: 'text-slate-500 bg-slate-50 border-slate-200',
}

// 텍스트 색상 클래스
export const SIGNAL_TEXT_CLASS: Record<SignalColor, string> = {
  green: 'text-green-700',
  yellow: 'text-amber-700',
  red: 'text-red-700',
  unknown: 'text-slate-500',
}

// 배경 + 테두리 클래스 (체크리스트 행에 사용)
export const SIGNAL_BG_CLASS: Record<SignalColor, string> = {
  green: 'bg-green-50 border-green-200',
  yellow: 'bg-amber-50 border-amber-200',
  red: 'bg-red-50 border-red-200',
  unknown: 'bg-slate-50 border-slate-200',
}

// 리스크 수준 라벨
export const SIGNAL_LABEL: Record<SignalColor, string> = {
  green: '낮음',
  yellow: '주의',
  red: '높음',
  unknown: '미확인',
}

export function calcOverallSignal(signals: RiskSignal[]): SignalColor {
  if (signals.some(s => s.color === 'red')) return 'red'
  if (signals.some(s => s.color === 'yellow')) return 'yellow'
  if (signals.every(s => s.color === 'green')) return 'green'
  return 'unknown'
}

// 리스트에서 보여줄 대표 신호등 계산
export function calcListSignal(item: {
  price_score: number | null
  location_score: number | null
  occupancy_score: number | null
  score_coverage: number | null
}): SignalColor {
  const coverage = item.score_coverage ?? 0
  if (coverage < 0.3) return 'unknown'

  const scores = [item.price_score, item.occupancy_score].filter(s => s !== null) as number[]
  if (scores.length === 0) return 'unknown'

  const avg = scores.reduce((a, b) => a + b, 0) / scores.length
  if (avg >= 70) return 'green'
  if (avg >= 45) return 'yellow'
  return 'red'
}

// 신호등 라벨
export function getSignalLabel(color: SignalColor): string {
  switch (color) {
    case 'green': return '양호'
    case 'yellow': return '주의'
    case 'red': return '위험'
    case 'unknown': return '미분류'
  }
}

// ── 리스크 신호등 산출 함수 ────────────────────────────────────

/** 임차인 명도 신호등 */
export function calcOccupancySignal(auction: AuctionDetailResponse): RiskSignal {
  const score = auction.score?.occupancy_score
  const tenantCount = auction.occupancy_tenant_count ?? 0
  const warnings = auction.score?.warnings?.filter(w =>
    w.includes('임차') || w.includes('점유') || w.includes('명도')
  ) ?? []

  if (score == null) {
    return {
      category: '임차인 명도',
      color: 'unknown',
      label: '현황조사서 미수집',
      reason: '현황조사서 데이터 없음 — 직접 확인 필요',
    }
  }
  if (score >= 70) return {
    category: '임차인 명도',
    color: 'green',
    label: '양호',
    reason: tenantCount === 0 ? '임차인 없음 (공실)' : `임차인 ${tenantCount}명 — 명도 리스크 낮음`,
    detail: warnings.length > 0 ? warnings : undefined,
  }
  if (score >= 45) return {
    category: '임차인 명도',
    color: 'yellow',
    label: '주의',
    reason: tenantCount > 0 ? `임차인 ${tenantCount}명 — 일부 확인 필요` : '임차 관련 주의사항 있음',
    detail: warnings.length > 0 ? warnings : undefined,
  }
  return {
    category: '임차인 명도',
    color: 'red',
    label: '위험',
    reason: tenantCount > 0 ? `임차인 ${tenantCount}명 — 명도 리스크 높음` : '명도 리스크 높음',
    detail: warnings.length > 0 ? warnings : undefined,
  }
}

/** 수익성 신호등 */
export function calcPriceSignal(auction: AuctionDetailResponse): RiskSignal {
  const score = auction.score?.price_score
  const discountRate =
    auction.appraised_value && auction.minimum_bid && auction.appraised_value > 0
      ? Math.round((1 - auction.minimum_bid / auction.appraised_value) * 100)
      : null

  if (score == null) {
    return {
      category: '수익성',
      color: 'unknown',
      label: '데이터 없음',
      reason: '시세 데이터 미수집',
    }
  }
  const reasonBase = discountRate !== null ? `감정가 대비 ${discountRate}% 할인` : '가격 데이터 있음'

  if (score >= 70) return { category: '수익성', color: 'green', label: '양호', reason: reasonBase }
  if (score >= 45) return { category: '수익성', color: 'yellow', label: '주의', reason: reasonBase }
  return { category: '수익성', color: 'red', label: '위험', reason: reasonBase }
}

/** 입지 신호등 */
export function calcLocationSignal(auction: AuctionDetailResponse): RiskSignal {
  const score = auction.score?.location_score
  const stationDist = auction.station_distance_m

  if (score == null) {
    return {
      category: '입지',
      color: 'unknown',
      label: '데이터 수집 중',
      reason: '입지 데이터 미수집',
    }
  }
  const reason = stationDist != null
    ? `가장 가까운 역 ${stationDist}m`
    : '역거리 데이터 없음'

  if (score >= 70) return { category: '입지', color: 'green', label: '양호', reason }
  if (score >= 45) return { category: '입지', color: 'yellow', label: '주의', reason }
  return { category: '입지', color: 'red', label: '위험', reason }
}
