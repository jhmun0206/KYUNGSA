import type { RoundItem } from "@/lib/types"

interface Props {
  rounds: RoundItem[]
}

function formatAmount(v: number): string {
  const uk = Math.round(v / 10000)
  if (uk >= 10000) return `${(uk / 10000).toFixed(1)}억`
  return `${uk.toLocaleString()}만`
}

function formatDate(d: string | null): string {
  if (!d) return "-"
  return d.replace(/-/g, ".")
}

function getResultStyle(result: string): string {
  if (result.includes("매각") || result.includes("낙찰"))
    return "bg-emerald-100 text-emerald-700"
  if (result.includes("유찰"))
    return "bg-red-50 text-red-600"
  return "bg-blue-50 text-blue-600"
}

export function RoundTimeline({ rounds }: Props) {
  if (rounds.length === 0) {
    return <p className="text-sm text-gray-400">기일 내역 없음</p>
  }

  return (
    <ol className="relative ml-3 border-l border-gray-200">
      {rounds.map((r, i) => (
        <li key={i} className="mb-6 ml-6">
          <span className="absolute -left-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-white border-2 border-indigo-400 text-xs font-bold text-indigo-600">
            {r.round_number}
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-gray-500">{formatDate(r.round_date)}</span>
            <span
              className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${getResultStyle(r.result)}`}
            >
              {r.result || "진행"}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-gray-700">
            최저입찰가:{" "}
            <span className="font-semibold tabular-nums">{formatAmount(r.minimum_bid)}</span>
          </p>
        </li>
      ))}
    </ol>
  )
}
