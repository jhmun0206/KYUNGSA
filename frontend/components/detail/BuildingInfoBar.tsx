import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

function InfoItem({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="flex flex-col gap-0.5 min-w-[80px]">
      <span className="text-[11px] text-slate-400 dark:text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{value}</span>
    </div>
  )
}

export function BuildingInfoBar({ auction }: Props) {
  const info = auction.building_info
  if (!info) return null

  const buildYear = info.build_year
    ? `${info.build_year}년`
    : auction.building_info?.use_approve_date
    ? auction.building_info.use_approve_date.slice(0, 4) + '년'
    : null

  const buildingTypeLabel =
    auction.building_type === '일반' ? '일반건축물'
    : auction.building_type === '집합' ? '집합건물'
    : null

  const floorInfo = (() => {
    const g = info.ground_floors
    const b = info.underground_floors
    if (g && b) return `지하 ${b}층 / 지상 ${g}층`
    if (g) return `지상 ${g}층`
    return null
  })()

  return (
    <div className="flex flex-wrap gap-x-6 gap-y-3 px-4 py-3.5 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700">
      <InfoItem label="주용도" value={info.main_purpose || null} />
      <InfoItem label="건물형태" value={buildingTypeLabel} />
      <InfoItem
        label="연면적"
        value={info.total_area ? `${info.total_area.toLocaleString()}㎡` : null}
      />
      <InfoItem label="층수" value={floorInfo} />
      <InfoItem label="건축년도" value={buildYear} />
      <InfoItem
        label="세대/호실"
        value={info.units_count ? `${info.units_count}호` : null}
      />
      {info.violation && (
        <div className="flex flex-col gap-0.5 min-w-[80px]">
          <span className="text-[11px] text-slate-400 dark:text-slate-500">위반건축물</span>
          <span className="text-sm font-semibold text-red-600 dark:text-red-400">⚠ 있음</span>
        </div>
      )}
    </div>
  )
}
