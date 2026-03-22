"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { CompareButton } from "@/components/domain/CompareButton"
import { normalizePropertyType } from "@/lib/property-category"
import { SIGNAL_EMOJI, calcListSignal, getSignalLabel } from "@/lib/risk-signals"
import { formatPrice, calcDday, getDdayColor, formatStation } from "@/lib/utils"
import type { AuctionListItem } from "@/lib/types"

const SORTABLE_COLUMNS = [
  { key: "appraised_value", label: "감정가" },
  { key: "minimum_bid", label: "최저가/할인" },
  { key: "auction_date", label: "매각기일" },
  { key: "bid_count", label: "유찰" },
] as const

function calcDiscountRate(appraised: number | null, minBid: number | null): string | null {
  if (!appraised || !minBid || appraised === 0) return null
  return Math.round((1 - minBid / appraised) * 100).toString()
}

function getCoverageColor(coverage: number): string {
  if (coverage >= 0.8) return "bg-green-500"
  if (coverage >= 0.5) return "bg-blue-500"
  return "bg-amber-400"
}

interface Props {
  items: AuctionListItem[]
  total: number
}

export function AuctionTable({ items, total }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const currentSort = searchParams.get("sort") ?? "auction_date"

  function handleSort(key: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("sort", key)
    params.delete("page")
    router.push(`${pathname}?${params.toString()}`)
  }

  function navigateToDetail(caseNumber: string) {
    router.push(`/auction/${encodeURIComponent(caseNumber)}`)
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400">
        <p className="text-sm">조건에 맞는 물건이 없습니다</p>
        <p className="mt-1 text-xs">필터 조건을 변경해 보세요</p>
      </div>
    )
  }

  return (
    <div>
      {/* 데스크탑 테이블 */}
      <div className="hidden lg:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700 text-[11px] font-medium text-slate-500 dark:text-slate-400">
              <th className="w-[90px] px-3 py-2.5 text-left font-medium">유형</th>
              <th className="px-3 py-2.5 text-left font-medium">주소</th>
              {SORTABLE_COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2.5 text-right font-medium cursor-pointer select-none hover:text-slate-700 dark:hover:text-slate-200 transition-colors ${
                    col.key === "bid_count" ? "w-[50px]" :
                    col.key === "auction_date" ? "w-[110px]" :
                    col.key === "minimum_bid" ? "w-[130px]" : "w-[100px]"
                  } ${currentSort === col.key ? "text-blue-600 dark:text-blue-400" : ""}`}
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}
                  {currentSort === col.key ? " ↓" : ""}
                </th>
              ))}
              <th className="w-[50px] px-3 py-2.5 text-center font-medium">상태</th>
              <th className="w-[80px] px-3 py-2.5 text-center font-medium">완성도</th>
              <th className="w-[90px] px-3 py-2.5 text-center font-medium">관심/비교</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <DesktopRow
                key={item.case_number}
                item={item}
                onClick={() => navigateToDetail(item.case_number)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* 모바일 카드 리스트 */}
      <div className="lg:hidden divide-y divide-slate-100 dark:divide-slate-800">
        {items.map((item) => (
          <MobileRow
            key={item.case_number}
            item={item}
            onClick={() => navigateToDetail(item.case_number)}
          />
        ))}
      </div>

      {/* 하단 건수 */}
      {total > 0 && (
        <p className="px-3 py-2 text-xs text-slate-400">
          총 {total.toLocaleString()}건
        </p>
      )}
    </div>
  )
}

function DesktopRow({ item, onClick }: { item: AuctionListItem; onClick: () => void }) {
  const signal = calcListSignal(item)
  const discountRate = calcDiscountRate(item.appraised_value, item.minimum_bid)
  const coverage = item.score_coverage ?? 0

  return (
    <tr
      className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer transition-colors"
      onClick={onClick}
    >
      {/* 유형 */}
      <td className="w-[90px] px-3 py-3 text-[13px] font-medium text-slate-700 dark:text-slate-300 whitespace-nowrap">
        {normalizePropertyType(item.property_type) ?? '미분류'}
      </td>

      {/* 주소 */}
      <td className="px-3 py-3">
        <div className="text-[13px] font-medium text-slate-900 dark:text-slate-100 truncate max-w-xs">
          {item.address}
        </div>
        <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
          {item.court} · {item.case_number}
        </div>
        {formatStation(item.nearest_station_name, item.nearest_station_line, item.station_distance_m) && (
          <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
            🚇 {formatStation(item.nearest_station_name, item.nearest_station_line, item.station_distance_m)}
          </div>
        )}
      </td>

      {/* 감정가 */}
      <td className="w-[100px] px-3 py-3 text-[13px] text-right text-slate-600 dark:text-slate-400 whitespace-nowrap">
        {formatPrice(item.appraised_value)}
      </td>

      {/* 최저가 + 할인율 */}
      <td className="w-[130px] px-3 py-3 text-right whitespace-nowrap">
        <div className="text-[13px] font-medium text-slate-900 dark:text-slate-100">
          {formatPrice(item.minimum_bid)}
        </div>
        {discountRate && (
          <div className="text-[11px] text-blue-600 dark:text-blue-400 font-medium mt-0.5">
            {discountRate}% ↓
          </div>
        )}
      </td>

      {/* 매각기일 + D-day */}
      <td className="w-[110px] px-3 py-3 text-center whitespace-nowrap">
        <div className="text-[13px] text-slate-700 dark:text-slate-300">
          {item.auction_date ? item.auction_date.replace(/-/g, ".") : "-"}
        </div>
        <div className={`text-[11px] font-bold mt-0.5 ${getDdayColor(item.auction_date)}`}>
          {calcDday(item.auction_date, item.status)}
        </div>
      </td>

      {/* 유찰횟수 */}
      <td className="w-[50px] px-3 py-3 text-center text-[13px]">
        {item.bid_count > 1 ? (
          <span className="text-orange-600 dark:text-orange-400 font-medium">
            {item.bid_count - 1}회
          </span>
        ) : (
          <span className="text-slate-400">신건</span>
        )}
      </td>

      {/* 신호등 */}
      <td className="w-[50px] px-3 py-3 text-center">
        <span className="text-base" title={getSignalLabel(signal)}>
          {SIGNAL_EMOJI[signal]}
        </span>
      </td>

      {/* 데이터 완성도 */}
      <td className="w-[80px] px-3 py-3">
        <div className="flex items-center gap-1">
          <div className="flex-1 bg-slate-200 dark:bg-slate-700 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all ${getCoverageColor(coverage)}`}
              style={{ width: `${Math.round(coverage * 100)}%` }}
            />
          </div>
          <span className="text-[10px] text-slate-400 w-7 text-right tabular-nums">
            {Math.round(coverage * 100)}%
          </span>
        </div>
      </td>

      {/* 관심/비교 */}
      <td className="w-[90px] px-3 py-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex gap-0.5 justify-center">
          <FavoriteButton caseNumber={item.case_number} />
          <CompareButton caseNumber={item.case_number} />
        </div>
      </td>
    </tr>
  )
}

function MobileRow({ item, onClick }: { item: AuctionListItem; onClick: () => void }) {
  const signal = calcListSignal(item)
  const discountRate = calcDiscountRate(item.appraised_value, item.minimum_bid)
  const failCount = Math.max(0, item.bid_count - 1)

  return (
    <div
      className="px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer active:bg-slate-100 transition-colors"
      onClick={onClick}
    >
      {/* 상단: 유형 + 신호등 + 액션 */}
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
          {normalizePropertyType(item.property_type) ?? '미분류'}
        </span>
        <span className="text-sm" title={getSignalLabel(signal)}>
          {SIGNAL_EMOJI[signal]}
        </span>
        {failCount > 0 && (
          <span className="text-[10px] text-orange-600 dark:text-orange-400 font-medium">
            {failCount}회유찰
          </span>
        )}
        <div className="ml-auto flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
          <FavoriteButton caseNumber={item.case_number} />
          <CompareButton caseNumber={item.case_number} />
        </div>
      </div>

      {/* 주소 */}
      <p className="text-[13px] font-medium text-slate-900 dark:text-slate-100 truncate">
        {item.address}
      </p>
      <p className="text-[11px] text-slate-400 mt-0.5">
        {item.court}
        {formatStation(item.nearest_station_name, item.nearest_station_line, item.station_distance_m) && (
          <> · 🚇 {formatStation(item.nearest_station_name, item.nearest_station_line, item.station_distance_m)}</>
        )}
      </p>

      {/* 가격 + 기일 */}
      <div className="flex items-baseline gap-3 mt-2">
        <span className="text-[13px] font-semibold text-slate-900 dark:text-slate-100">
          {formatPrice(item.minimum_bid)}
        </span>
        {discountRate && (
          <span className="text-[11px] text-blue-600 dark:text-blue-400 font-medium">
            {discountRate}%↓
          </span>
        )}
        <span className="text-[11px] text-slate-400">
          감정 {formatPrice(item.appraised_value)}
        </span>
        <span className={`ml-auto text-[12px] font-semibold ${getDdayColor(item.auction_date)}`}>
          {calcDday(item.auction_date, item.status)}
        </span>
      </div>
    </div>
  )
}
