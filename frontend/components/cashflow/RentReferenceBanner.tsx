import type { RentReference } from "@/lib/types"

interface Props {
  data: RentReference
}

/** 한국부동산원 인근 상가 임대료 레퍼런스 배너 */
export function RentReferenceBanner({ data }: Props) {
  if (!data.available || !data.rent) return null

  const { rent, vacancy, region } = data
  const period = rent.period || ""

  return (
    <div className="rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 px-4 py-3 text-sm space-y-1">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-emerald-700 dark:text-emerald-400 font-semibold text-xs uppercase tracking-wide">
          📊 인근 상가 임대료 레퍼런스
        </span>
        {period && (
          <span className="text-xs text-slate-400 dark:text-slate-500">
            ({period})
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-slate-700 dark:text-slate-300">
        <span>
          <span className="text-slate-500 dark:text-slate-400 mr-1">{region} 소규모 상가 임대료</span>
          <strong>{rent.value.toLocaleString()}원/㎡/월</strong>
        </span>
        {vacancy && (
          <span>
            <span className="text-slate-500 dark:text-slate-400 mr-1">공실률</span>
            <strong>{typeof vacancy.value === "number" ? vacancy.value.toFixed(1) : vacancy.value}%</strong>
          </span>
        )}
      </div>

      <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
        ※ {rent.source} 분기 통계 기반 참고값. 실제 시세와 다를 수 있습니다.
      </p>
    </div>
  )
}
