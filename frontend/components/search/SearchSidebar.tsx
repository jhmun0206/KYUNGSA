"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useCallback } from "react"
import { RotateCcw } from "lucide-react"
import { PROPERTY_CATEGORIES } from "@/lib/property-category"
import { SEOUL_DISTRICTS, PRICE_RANGES } from "@/lib/constants"

const REGION_OPTIONS = ["서울", "경기", "인천"]

const FAIL_COUNT_OPTIONS = [
  { value: "", label: "전체" },
  { value: "1", label: "1회+" },
  { value: "2", label: "2회+" },
  { value: "3", label: "3회+" },
]

const STATION_OPTIONS = [
  { value: "", label: "전체" },
  { value: "500", label: "500m" },
  { value: "1000", label: "1km" },
]

const BUILD_YEAR_OPTIONS = [
  { value: "", label: "전체" },
  { value: "2010", label: "2010+" },
  { value: "2015", label: "2015+" },
  { value: "2020", label: "2020+" },
]

const BUILDING_TYPE_OPTIONS = [
  { value: "", label: "전체" },
  { value: "일반", label: "일반" },
  { value: "집합", label: "집합" },
]

// 칩 스타일 헬퍼
function chip(selected: boolean, sm = false) {
  return [
    "cursor-pointer rounded-full border transition-colors",
    sm ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-[12px]",
    selected
      ? "border-blue-500 bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 font-medium"
      : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-blue-300 dark:hover:border-blue-600",
  ].join(" ")
}

export function SearchSidebar() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  // 현재 선택 상태 (URL param 기준, 전부 서버 파라미터)
  const selectedTypes = (searchParams.get("category") ?? "").split(",").filter(Boolean)
  const selectedRegions = (searchParams.get("region") ?? "").split(",").filter(Boolean)
  const selectedDistricts = (searchParams.get("district") ?? "").split(",").filter(Boolean)
  const selectedPriceIdx = searchParams.get("price_idx") ?? ""
  const selectedBidCountMin = searchParams.get("bid_count_min") ?? ""
  const selectedStation = searchParams.get("station_radius_m") ?? ""
  const selectedBuildYear = searchParams.get("build_year_min") ?? ""
  const selectedBuildingType = searchParams.get("building_type") ?? ""

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value) params.set(key, value)
      else params.delete(key)
      params.delete("page")
      router.push(`${pathname}?${params.toString()}`)
    },
    [router, pathname, searchParams]
  )

  // 멀티셀렉 토글
  const toggleMulti = useCallback(
    (key: string, value: string, current: string[]) => {
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value]
      update(key, next.join(","))
    },
    [update]
  )

  // 단일셀렉 토글: 현재와 같으면 해제, 다르면 선택
  const toggleSingle = useCallback(
    (key: string, value: string, current: string) => {
      update(key, current === value ? "" : value)
    },
    [update]
  )

  // 시/도 토글: 서울 제거 시 district도 초기화
  const toggleRegion = useCallback(
    (region: string) => {
      const newRegions = selectedRegions.includes(region)
        ? selectedRegions.filter((r) => r !== region)
        : [...selectedRegions, region]
      const params = new URLSearchParams(searchParams.toString())
      if (newRegions.length > 0) params.set("region", newRegions.join(","))
      else params.delete("region")
      // 서울이 제거되면 구 선택도 초기화
      if (selectedRegions.includes("서울") && !newRegions.includes("서울")) {
        params.delete("district")
      }
      params.delete("page")
      router.push(`${pathname}?${params.toString()}`)
    },
    [router, pathname, searchParams, selectedRegions]
  )

  const hasFilters =
    selectedTypes.length > 0 ||
    selectedRegions.length > 0 ||
    selectedDistricts.length > 0 ||
    selectedPriceIdx ||
    selectedBidCountMin ||
    selectedStation ||
    selectedBuildYear ||
    selectedBuildingType

  const resetFilters = () => {
    const params = new URLSearchParams()
    const sort = searchParams.get("sort")
    if (sort) params.set("sort", sort)
    router.push(`${pathname}?${params.toString()}`)
  }

  const seoulSelected = selectedRegions.includes("서울")

  return (
    <div className="space-y-5 text-sm">

      {/* 물건 종류 — 멀티셀렉 칩 */}
      <SidebarSection title="물건 종류" count={selectedTypes.length}>
        <div className="flex flex-wrap gap-1.5">
          {PROPERTY_CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => toggleMulti("category", cat.value, selectedTypes)}
              className={chip(selectedTypes.includes(cat.value))}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </SidebarSection>

      {/* 지역 — 시/도 + 구/군 2단계 */}
      <SidebarSection title="지역" count={selectedRegions.length + selectedDistricts.length}>
        {/* 시/도 칩 */}
        <div className="flex flex-wrap gap-1.5 mb-2">
          {REGION_OPTIONS.map((r) => (
            <button
              key={r}
              onClick={() => toggleRegion(r)}
              className={chip(selectedRegions.includes(r))}
            >
              {r}
            </button>
          ))}
        </div>

        {/* 서울 선택 시: 구 선택 */}
        {seoulSelected && (
          <div className="flex flex-wrap gap-1 pt-1.5 border-t border-slate-100 dark:border-slate-800">
            {SEOUL_DISTRICTS.map((d) => (
              <button
                key={d}
                onClick={() => toggleMulti("district", d, selectedDistricts)}
                className={chip(selectedDistricts.includes(d), true)}
              >
                {d}
              </button>
            ))}
          </div>
        )}
      </SidebarSection>

      {/* 건물 형태 — 단일셀렉 칩 */}
      <SidebarSection title="건물 형태">
        <div className="flex flex-wrap gap-1.5">
          {BUILDING_TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                opt.value === ""
                  ? update("building_type", "")
                  : toggleSingle("building_type", opt.value, selectedBuildingType)
              }
              className={chip(opt.value === "" ? !selectedBuildingType : selectedBuildingType === opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {selectedBuildingType && (
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            ※ 건물형태 데이터는 일부 물건만 수집됩니다
          </p>
        )}
      </SidebarSection>

      {/* 감정가 — 단일셀렉 칩 */}
      <SidebarSection title="감정가">
        <div className="flex flex-wrap gap-1.5">
          {PRICE_RANGES.map((p, idx) => {
            const isSelected = idx === 0 ? !selectedPriceIdx : selectedPriceIdx === String(idx)
            return (
              <button
                key={idx}
                onClick={() => {
                  const params = new URLSearchParams(searchParams.toString())
                  if (idx === 0 || selectedPriceIdx === String(idx)) {
                    params.delete("price_idx")
                    params.delete("min_price")
                    params.delete("max_price")
                  } else {
                    params.set("price_idx", String(idx))
                    if (p.min != null) params.set("min_price", String(p.min))
                    else params.delete("min_price")
                    if (p.max != null) params.set("max_price", String(p.max))
                    else params.delete("max_price")
                  }
                  params.delete("page")
                  router.push(`${pathname}?${params.toString()}`)
                }}
                className={chip(isSelected)}
              >
                {p.label}
              </button>
            )
          })}
        </div>
      </SidebarSection>

      {/* 유찰횟수 — 단일셀렉 칩 */}
      <SidebarSection title="유찰횟수">
        <div className="flex flex-wrap gap-1.5">
          {FAIL_COUNT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                opt.value === ""
                  ? update("bid_count_min", "")
                  : toggleSingle("bid_count_min", opt.value, selectedBidCountMin)
              }
              className={chip(opt.value === "" ? !selectedBidCountMin : selectedBidCountMin === opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </SidebarSection>

      {/* 역까지 거리 — 단일셀렉 칩 */}
      <SidebarSection title="역까지 거리">
        <div className="flex flex-wrap gap-1.5">
          {STATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                opt.value === ""
                  ? update("station_radius_m", "")
                  : toggleSingle("station_radius_m", opt.value, selectedStation)
              }
              className={chip(opt.value === "" ? !selectedStation : selectedStation === opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </SidebarSection>

      {/* 사용승인연도 — 단일셀렉 칩 */}
      <SidebarSection title="사용승인연도">
        <div className="flex flex-wrap gap-1.5">
          {BUILD_YEAR_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                opt.value === ""
                  ? update("build_year_min", "")
                  : toggleSingle("build_year_min", opt.value, selectedBuildYear)
              }
              className={chip(opt.value === "" ? !selectedBuildYear : selectedBuildYear === opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </SidebarSection>

      {/* 필터 초기화 */}
      {hasFilters && (
        <button
          onClick={resetFilters}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
        >
          <RotateCcw size={13} />
          필터 초기화
        </button>
      )}
    </div>
  )
}

function SidebarSection({
  title,
  count,
  children,
}: {
  title: string
  count?: number
  children: React.ReactNode
}) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
        {count != null && count > 0 && (
          <span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-bold text-white">
            {count}
          </span>
        )}
      </h3>
      {children}
    </section>
  )
}
