import type { RoundItem } from "@/lib/types"

interface Props {
  rounds: RoundItem[]
}

function formatDate(d: string | null): string {
  if (!d) return '-'
  return String(d).replace(/-/g, '.')
}

function formatAmount(v: number | null | undefined): string {
  if (!v) return '-'
  const uk = Math.floor(Math.abs(v) / 100000000)
  const man = Math.floor((Math.abs(v) % 100000000) / 10000)
  if (uk > 0 && man > 0) return `${uk}억 ${man.toLocaleString()}만`
  if (uk > 0) return `${uk}억`
  if (man > 0) return `${man.toLocaleString()}만`
  return '-'
}

function getResultStyle(result: string | null): string {
  if (!result) return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
  if (result.includes('매각') || result.includes('낙찰'))
    return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
  if (result.includes('유찰'))
    return 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300'
  return 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
}

export function RoundTimeline({ rounds }: Props) {
  if (!rounds || rounds.length === 0) {
    return (
      <p className="text-sm text-slate-400 dark:text-slate-500 py-4 text-center">
        기일 내역 없음
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {rounds.map((round, i) => {
        const isLatest = i === rounds.length - 1
        return (
          <div
            key={round.round_number}
            className={`flex items-center gap-4 px-4 py-3 rounded-xl border text-sm ${
              isLatest
                ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800'
                : 'bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700'
            }`}
          >
            {/* 회차 번호 */}
            <span
              className={`shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-xs font-bold border-2 ${
                isLatest
                  ? 'border-blue-400 text-blue-600 dark:text-blue-300 bg-white dark:bg-slate-900'
                  : 'border-slate-300 dark:border-slate-600 text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-900'
              }`}
            >
              {round.round_number}
            </span>

            {/* 날짜 */}
            <span className="text-slate-600 dark:text-slate-300 tabular-nums">
              {formatDate(round.round_date)}
            </span>

            {/* 최저입찰가 */}
            <span className="text-slate-700 dark:text-slate-200 font-medium tabular-nums">
              {formatAmount(round.minimum_bid)}
            </span>

            {/* 결과 배지 */}
            <span
              className={`ml-auto px-2.5 py-0.5 rounded-full text-xs font-semibold ${getResultStyle(round.result)}`}
            >
              {round.result || '진행중'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
