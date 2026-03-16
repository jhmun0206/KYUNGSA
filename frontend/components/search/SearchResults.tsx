"use client"

import { useSearchParams } from "next/navigation"
import { useMemo } from "react"
import { AuctionTable } from "@/components/search/AuctionTable"
import { calcListSignal, type SignalColor } from "@/lib/risk-signals"
import { normalizePropertyType } from "@/lib/property-category"
import type { AuctionListResponse } from "@/lib/types"

interface Props {
  initialData: AuctionListResponse
}

/** 서버에서 받은 데이터에 클라이언트 필터 적용 후 AuctionTable에 전달 */
export function SearchResults({ initialData }: Props) {
  const searchParams = useSearchParams()

  // 클라이언트 필터 파라미터 읽기
  const cfStation = searchParams.get("cf_station") ?? ""
  const cfBuildYear = searchParams.get("cf_build_year") ?? ""
  const cfBuildingType = searchParams.get("cf_building_type") ?? ""
  const cfSignals = (searchParams.get("cf_signal") ?? "").split(",").filter(Boolean) as SignalColor[]
  const cfFail = searchParams.get("cf_fail") ?? ""
  const cfMin = searchParams.get("cf_min") ?? ""
  const cfMax = searchParams.get("cf_max") ?? ""

  // 물건유형 — 멀티셀렉 지원 (정규화 기반 매칭)
  const selectedTypes = (searchParams.get("type") ?? "").split(",").filter(Boolean)

  const filtered = useMemo(() => {
    let items = initialData.items

    // 물건유형 필터 (정규화 매핑 기반 클라이언트 필터)
    if (selectedTypes.length > 0) {
      items = items.filter((item) => {
        const normalized = normalizePropertyType(item.property_type)
        // 정규화 결과 또는 서버의 property_category 필드 매칭
        return normalized ? selectedTypes.includes(normalized) : false
      })
    }

    // 감정가 범위 (서버에서도 처리하지만 사이드바 프리셋용 보충)
    if (cfMin) {
      const min = parseInt(cfMin)
      items = items.filter((item) => item.appraised_value != null && item.appraised_value >= min)
    }
    if (cfMax) {
      const max = parseInt(cfMax)
      items = items.filter((item) => item.appraised_value != null && item.appraised_value <= max)
    }

    // 유찰횟수 (N회 이상)
    if (cfFail) {
      const minFail = parseInt(cfFail)
      items = items.filter((item) => Math.max(0, item.bid_count - 1) >= minFail)
    }

    // 역거리 필터
    if (cfStation) {
      const maxDist = parseInt(cfStation)
      items = items.filter((item) => {
        const dist = item.station_distance_m
        return dist != null && dist <= maxDist
      })
    }

    // 건물형태 필터
    if (cfBuildingType) {
      items = items.filter((item) => item.building_type === cfBuildingType)
    }

    // 사용승인연도 필터
    if (cfBuildYear) {
      const minYear = parseInt(cfBuildYear)
      items = items.filter((item) => item.build_year != null && item.build_year >= minYear)
    }

    // 리스크 신호등 필터
    if (cfSignals.length > 0) {
      items = items.filter((item) => {
        const signal = calcListSignal(item)
        return cfSignals.includes(signal)
      })
    }

    return items
  }, [initialData.items, selectedTypes, cfMin, cfMax, cfFail, cfStation, cfBuildingType, cfBuildYear, cfSignals])

  const isClientFiltering = cfStation || cfBuildYear || cfBuildingType || cfSignals.length > 0 || cfFail || cfMin || cfMax || selectedTypes.length > 0
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
