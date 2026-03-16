"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useCallback } from "react"
import { RotateCcw } from "lucide-react"
import { PROPERTY_CATEGORIES } from "@/lib/property-category"
import { SEOUL_DISTRICTS, PRICE_RANGES } from "@/lib/constants"
import { SIGNAL_EMOJI, type SignalColor } from "@/lib/risk-signals"

const FAIL_COUNT_OPTIONS = [
  { value: "", label: "전체" },
  { value: "1", label: "1회 이상" },
  { value: "2", label: "2회 이상" },
  { value: "3", label: "3회 이상" },
]

const STATION_OPTIONS = [
  { value: "", label: "전체" },
  { value: "500", label: "500m 이내" },
  { value: "1000", label: "1km 이내" },
]

const BUILD_YEAR_OPTIONS = [
  { value: "", label: "전체" },
  { value: "2010", label: "2010년 이후" },
  { value: "2015", label: "2015년 이후" },
  { value: "2020", label: "2020년 이후" },
]

const BUILDING_TYPE_OPTIONS = [
  { value: "", label: "전체" },
  { value: "일반", label: "건물 전체 (일반)" },
  { value: "집합", label: "집합건물" },
]

const SIGNAL_OPTIONS: { value: SignalColor; label: string }[] = [
  { value: "green", label: `${SIGNAL_EMOJI.green} 양호` },
  { value: "yellow", label: `${SIGNAL_EMOJI.yellow} 주의` },
  { value: "red", label: `${SIGNAL_EMOJI.red} 위험` },
  { value: "unknown", label: `${SIGNAL_EMOJI.unknown} 미분류` },
]

export function SearchSidebar() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  // 현재 선택 상태 읽기
  const selectedTypes = (searchParams.get("type") ?? "").split(",").filter(Boolean)
  const selectedDistricts = (searchParams.get("district") ?? "").split(",").filter(Boolean)
  const selectedGrades = (searchParams.get("grade") ?? "").split(",").filter(Boolean)
  const selectedPriceIdx = searchParams.get("price_range") ?? ""
  const selectedFail = searchParams.get("cf_fail") ?? ""
  const selectedStation = searchParams.get("cf_station") ?? ""
  const selectedBuildYear = searchParams.get("cf_build_year") ?? ""
  const selectedBuildingType = searchParams.get("cf_building_type") ?? ""
  const selectedSignals = (searchParams.get("cf_signal") ?? "").split(",").filter(Boolean)

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
      params.delete("page")
      router.push(`${pathname}?${params.toString()}`)
    },
    [router, pathname, searchParams]
  )

  const toggleMulti = useCallback(
    (key: string, value: string, current: string[]) => {
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value]
      update(key, next.join(","))
    },
    [update]
  )

  const hasFilters =
    selectedTypes.length > 0 ||
    selectedDistricts.length > 0 ||
    selectedGrades.length > 0 ||
    selectedPriceIdx ||
    selectedFail ||
    selectedStation ||
    selectedBuildYear ||
    selectedBuildingType ||
    selectedSignals.length > 0

  const resetFilters = () => {
    const params = new URLSearchParams()
    const sort = searchParams.get("sort")
    if (sort) params.set("sort", sort)
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <div className="space-y-5 text-sm">
      {/* 물건 종류 */}
      <SidebarSection title="물건 종류" count={selectedTypes.length}>
        <div className="space-y-1.5">
          {PROPERTY_CATEGORIES.map((cat) => (
            <label key={cat.value} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="checkbox"
                checked={selectedTypes.includes(cat.value)}
                onChange={() => toggleMulti("type", cat.value, selectedTypes)}
                className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{cat.label}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 건물 형태 */}
      <SidebarSection title="건물 형태">
        <div className="space-y-1.5">
          {BUILDING_TYPE_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="radio"
                name="building_type"
                checked={selectedBuildingType === opt.value}
                onChange={() => update("cf_building_type", opt.value)}
                className="h-3.5 w-3.5 border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{opt.label}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 지역 (서울) */}
      <SidebarSection title="지역 (서울)" count={selectedDistricts.length}>
        <div className="grid grid-cols-2 gap-x-2 gap-y-1.5">
          {SEOUL_DISTRICTS.map((d) => (
            <label key={d} className="flex items-center gap-1.5 cursor-pointer hover:text-foreground">
              <input
                type="checkbox"
                checked={selectedDistricts.includes(d)}
                onChange={() => toggleMulti("district", d, selectedDistricts)}
                className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{d}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 감정가 */}
      <SidebarSection title="감정가">
        <div className="space-y-1.5">
          {PRICE_RANGES.map((p, idx) => (
            <label key={idx} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="radio"
                name="price_range"
                checked={selectedPriceIdx === String(idx) || (idx === 0 && !selectedPriceIdx)}
                onChange={() => {
                  const params = new URLSearchParams(searchParams.toString())
                  if (idx === 0) {
                    params.delete("price_range")
                    params.delete("cf_min")
                    params.delete("cf_max")
                  } else {
                    params.set("price_range", String(idx))
                    if (p.min != null) params.set("cf_min", String(p.min))
                    else params.delete("cf_min")
                    if (p.max != null) params.set("cf_max", String(p.max))
                    else params.delete("cf_max")
                  }
                  params.delete("page")
                  router.push(`${pathname}?${params.toString()}`)
                }}
                className="h-3.5 w-3.5 border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{p.label}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 유찰횟수 */}
      <SidebarSection title="유찰횟수">
        <div className="space-y-1.5">
          {FAIL_COUNT_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="radio"
                name="fail_count"
                checked={selectedFail === opt.value}
                onChange={() => update("cf_fail", opt.value)}
                className="h-3.5 w-3.5 border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{opt.label}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 역까지 거리 */}
      <SidebarSection title="역까지 거리">
        <div className="space-y-1.5">
          {STATION_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="radio"
                name="station_radius"
                checked={selectedStation === opt.value}
                onChange={() => update("cf_station", opt.value)}
                className="h-3.5 w-3.5 border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{opt.label}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 사용승인연도 */}
      <SidebarSection title="사용승인연도">
        <div className="space-y-1.5">
          {BUILD_YEAR_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="radio"
                name="build_year"
                checked={selectedBuildYear === opt.value}
                onChange={() => update("cf_build_year", opt.value)}
                className="h-3.5 w-3.5 border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{opt.label}</span>
            </label>
          ))}
        </div>
      </SidebarSection>

      {/* 리스크 등급 */}
      <SidebarSection title="리스크 등급" count={selectedSignals.length}>
        <div className="space-y-1.5">
          {SIGNAL_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer hover:text-foreground">
              <input
                type="checkbox"
                checked={selectedSignals.includes(opt.value)}
                onChange={() => toggleMulti("cf_signal", opt.value, selectedSignals)}
                className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 accent-blue-600"
              />
              <span className="text-slate-700 dark:text-slate-300 text-[13px]">{opt.label}</span>
            </label>
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
