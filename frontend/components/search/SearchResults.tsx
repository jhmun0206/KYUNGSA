"use client"

import { useSearchParams } from "next/navigation"
import { useMemo } from "react"
import { AuctionTable } from "@/components/search/AuctionTable"
import { calcListSignal, type SignalColor } from "@/lib/risk-signals"
import type { AuctionListResponse } from "@/lib/types"

interface Props {
  initialData: AuctionListResponse
}

/** 서버에서 받은 데이터에 클라이언트 전용 필터만 적용 후 AuctionTable에 전달
 *
 * 서버 필터 (page.tsx → API): category(property_type), district, min_price, max_price, bid_count_min
 * 클라이언트 필터 (이 컴포넌트): cf_station, cf_build_year, cf_building_type, cf_signal
 */
export function SearchResults({ initialData }: Props) {
  const searchParams = useSearchParams()

  // 클라이언트 전용 필터 파라미터만 읽기
  const cfStation = searchParams.get("cf_station") ?? ""
  const cfBuildYear = searchParams.get("cf_build_year") ?? ""
  const cfBuildingType = searchParams.get("cf_building_type") ?? ""
  const cfSignals = (searchParams.get("cf_signal") ?? "").split(",").filter(Boolean) as SignalColor[]

  const filtered = useMemo(() => {
    let items = initialData.items

    // 역거리 필터 (DB 컬럼 커버리지 낮음 → 클라이언트 처리)
    if (cfStation) {
      const maxDist = parseInt(cfStation)
      items = items.filter((item) => {
        const dist = item.station_distance_m
        return dist != null && dist <= maxDist
      })
    }

    // 건물형태 필터 (DB 컬럼 커버리지 낮음 → 클라이언트 처리)
    if (cfBuildingType) {
      items = items.filter((item) => item.building_type === cfBuildingType)
    }

    // 사용승인연도 필터 (DB 컬럼 커버리지 낮음 → 클라이언트 처리)
    if (cfBuildYear) {
      const minYear = parseInt(cfBuildYear)
      items = items.filter((item) => item.build_year != null && item.build_year >= minYear)
    }

    // 리스크 신호등 필터 (계산 필드 → 클라이언트 처리)
    if (cfSignals.length > 0) {
      items = items.filter((item) => {
        const signal = calcListSignal(item)
        return cfSignals.includes(signal)
      })
    }

    return items
  }, [initialData.items, cfStation, cfBuildingType, cfBuildYear, cfSignals])

  const isClientFiltering = cfStation || cfBuildYear || cfBuildingType || cfSignals.length > 0
  const displayTotal = isClientFiltering ? filtered.length : initialData.total

  return (
    <div>
      {isClientFiltering && filtered.length < initialData.items.length && (
        <p className="mb-2 px-3 text-xs text-amber-600 dark:text-amber-400">
          현재 페이지 내 필터링 결과입니다 ({filtered.length}/{initialData.items.length}건)
        </p>
      )}
      <AuctionTable items={filtered} total={displayTotal} />
    </div>
  )
}
