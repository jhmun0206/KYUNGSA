"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useCallback, useState, useEffect } from "react"
import { RotateCcw, Loader2 } from "lucide-react"
import { useSession } from "next-auth/react"
import { PROPERTY_CATEGORIES } from "@/lib/property-category"
import { SEOUL_DISTRICTS, PRICE_RANGES } from "@/lib/constants"
import { fetchSavedSearches, saveSearch, deleteSavedSearch, type SavedSearch } from "@/lib/auth-api"

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

// 저장된 검색 조건 요약 텍스트
function summarizeParams(params: Record<string, string>): string {
  const parts: string[] = []
  if (params.category) parts.push(params.category)
  if (params.region) parts.push(params.region)
  if (params.district) parts.push(params.district)
  if (params.min_price || params.max_price) {
    const fmt = (v: string) => {
      const n = Number(v)
      if (n >= 1_0000_0000) return `${n / 1_0000_0000}억`
      if (n >= 1_000_0000) return `${n / 1_000_0000}천만`
      return v
    }
    const min = params.min_price ? fmt(params.min_price) : ""
    const max = params.max_price ? fmt(params.max_price) : ""
    parts.push(`${min}~${max}`)
  }
  if (params.bid_count_min) parts.push(`유찰 ${params.bid_count_min}회+`)
  if (params.grade) parts.push(`${params.grade}등급`)
  if (params.building_type) parts.push(params.building_type)
  return parts.join(" · ") || "전체 조건"
}

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
  const { data: session } = useSession()

  // 저장된 검색 조건 상태
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([])
  const [activeSearchId, setActiveSearchId] = useState<string | null>(null)
  const [showSaveInput, setShowSaveInput] = useState(false)
  const [saveName, setSaveName] = useState("")
  const [saving, setSaving] = useState(false)

  // 세션 로드 시 저장 목록 fetch
  useEffect(() => {
    if (!session?.backendToken) return
    fetchSavedSearches(session.backendToken)
      .then(setSavedSearches)
      .catch(() => {})
  }, [session?.backendToken])

  const applySearch = (s: SavedSearch) => {
    if (activeSearchId === s.id) {
      // 동일 태그 재클릭 → 조건 초기화
      setActiveSearchId(null)
      router.push(pathname)
      return
    }
    setActiveSearchId(s.id)
    router.push(`${pathname}?${new URLSearchParams(s.params_json).toString()}`)
  }

  const handleDelete = async (id: string) => {
    if (!session?.backendToken) return
    try {
      await deleteSavedSearch(session.backendToken, id)
      setSavedSearches((prev) => prev.filter((s) => s.id !== id))
      if (activeSearchId === id) setActiveSearchId(null)
    } catch {}
  }

  const handleSave = async () => {
    if (!session?.backendToken || !saveName.trim()) return
    setSaving(true)
    try {
      const params = Object.fromEntries(searchParams.entries())
      const created = await saveSearch(session.backendToken, saveName.trim(), params)
      setSavedSearches((prev) => [created, ...prev])
      setSaveName("")
      setShowSaveInput(false)
    } catch {} finally {
      setSaving(false)
    }
  }

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

      {/* 저장된 검색 조건 태그 — 로그인 + 항목 있을 때만 */}
      {session && savedSearches.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            저장된 검색
          </p>
          <div className="flex flex-col gap-1">
            {savedSearches.map((s) => {
              const active = activeSearchId === s.id
              const summary = summarizeParams(s.params_json)
              return (
                <div
                  key={s.id}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 transition-colors ${
                    active
                      ? "bg-primary text-primary-foreground"
                      : "bg-primary/10 text-primary hover:bg-primary/20"
                  }`}
                >
                  <button
                    onClick={() => applySearch(s)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <span className="text-xs font-medium block truncate">{s.name}</span>
                    {summary !== "전체 조건" && (
                      <span className={`text-[10px] block truncate ${active ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                        {summary}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(s.id)}
                    className={`ml-2 shrink-0 transition-colors ${
                      active
                        ? "text-primary-foreground/70 hover:text-primary-foreground"
                        : "text-muted-foreground hover:text-destructive"
                    }`}
                    aria-label="삭제"
                  >
                    ×
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

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

      {/* 현재 조건 저장 — 로그인 시에만 표시 */}
      {session && (
        <div>
          {!showSaveInput ? (
            <button
              onClick={() => setShowSaveInput(true)}
              className="w-full rounded-lg border border-dashed border-slate-300 dark:border-slate-600 px-3 py-2 text-xs text-muted-foreground hover:border-primary hover:text-primary transition-colors"
            >
              💾 현재 조건 저장
            </button>
          ) : (
            <div className="flex gap-1.5">
              <input
                autoFocus
                type="text"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSave()
                  if (e.key === "Escape") { setShowSaveInput(false); setSaveName("") }
                }}
                placeholder="조건 이름 입력..."
                maxLength={30}
                className="flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                onClick={handleSave}
                disabled={saving || !saveName.trim()}
                className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-colors"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : "저장"}
              </button>
            </div>
          )}
        </div>
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
