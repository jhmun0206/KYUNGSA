// frontend/lib/risk-signals.ts

export type SignalColor = 'green' | 'yellow' | 'red' | 'unknown'

export interface RiskSignal {
  category: string
  color: SignalColor
  label: string
  reason: string
  detail?: string[]
  actionUrl?: string
}

// 신호등 이모지
export const SIGNAL_EMOJI: Record<SignalColor, string> = {
  green: '🟢',
  yellow: '🟡',
  red: '🔴',
  unknown: '⚫',
}

// 신호등 색상 클래스
export const SIGNAL_CLASS: Record<SignalColor, string> = {
  green: 'text-green-600 bg-green-50 border-green-200',
  yellow: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  red: 'text-red-600 bg-red-50 border-red-200',
  unknown: 'text-slate-500 bg-slate-50 border-slate-200',
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
