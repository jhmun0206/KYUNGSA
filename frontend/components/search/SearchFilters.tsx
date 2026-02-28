"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useCallback, useState } from "react"
import { X, SlidersHorizontal } from "lucide-react"
import { COURT_OPTIONS, GRADE_OPTIONS, PROPERTY_TYPE_OPTIONS } from "@/lib/constants"
import { formatPrice } from "@/lib/utils"

const SORT_OPTIONS = [
  { value: "grade", label: "등급순" },
  { value: "auction_date", label: "매각기일순" },
  { value: "appraised_value", label: "감정가순" },
  { value: "predicted_winning_ratio", label: "낙찰가율순" },
]

const PRICE_PRESETS = [
  { label: "~1억", min: null, max: 100_000_000 },
  { label: "1~5억", min: 100_000_000, max: 500_000_000 },
  { label: "5~10억", min: 500_000_000, max: 1_000_000_000 },
  { label: "10억~", min: 1_000_000_000, max: null },
] as const

const FAIL_COUNT_OPTIONS = [
  { value: "", label: "전체" },
  { value: "0", label: "0회 (신건)" },
  { value: "1", label: "1회" },
  { value: "2", label: "2회" },
  { value: "3", label: "3회 이상" },
]

export function SearchFilters() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const selectedGrades = (searchParams.get("grade") ?? "").split(",").filter(Boolean)
  const selectedCourt = searchParams.get("court") ?? ""
  const selectedType = searchParams.get("type") ?? ""
  const selectedSort = searchParams.get("sort") ?? "grade"

  // 클라이언트 필터 (cf_ 접두어)
  const cfMin = searchParams.get("cf_min") ?? ""
  const cfMax = searchParams.get("cf_max") ?? ""
  const cfFail = searchParams.get("cf_fail") ?? ""
  const cfFrom = searchParams.get("cf_from") ?? ""
  const cfTo = searchParams.get("cf_to") ?? ""

  const hasClientFilters = !!(cfMin || cfMax || cfFail || cfFrom || cfTo)
  const [showAdvanced, setShowAdvanced] = useState(hasClientFilters)

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
      params.delete("page") // 필터 변경 시 페이지 초기화
      router.push(`${pathname}?${params.toString()}`)
    },
    [router, pathname, searchParams]
  )

  const toggleGrade = (grade: string) => {
    const next = selectedGrades.includes(grade)
      ? selectedGrades.filter((g) => g !== grade)
      : [...selectedGrades, grade]
    update("grade", next.join(","))
  }

  const hasFilters = selectedGrades.length > 0 || selectedCourt || selectedType || hasClientFilters

  const resetFilters = () => {
    const params = new URLSearchParams()
    params.set("sort", selectedSort)
    router.push(`${pathname}?${params.toString()}`)
  }

  // 가격 프리셋 선택
  const activePricePreset = PRICE_PRESETS.findIndex(
    (p) =>
      (p.min == null ? cfMin === "" : cfMin === String(p.min)) &&
      (p.max == null ? cfMax === "" : cfMax === String(p.max))
  )

  const selectPricePreset = (preset: typeof PRICE_PRESETS[number], idx: number) => {
    const params = new URLSearchParams(searchParams.toString())
    // 이미 선택된 프리셋 재클릭 → 해제
    if (activePricePreset === idx) {
      params.delete("cf_min")
      params.delete("cf_max")
    } else {
      if (preset.min != null) params.set("cf_min", String(preset.min))
      else params.delete("cf_min")
      if (preset.max != null) params.set("cf_max", String(preset.max))
      else params.delete("cf_max")
    }
    params.delete("page")
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <div className="sticky top-14 z-40 -mx-4 border-b border-border bg-background/95 px-4 py-3 backdrop-blur-sm sm:-mx-6 sm:px-6">
      {/* 메인 필터 행 */}
      <div className="flex flex-wrap items-center gap-2">
        {/* 등급 토글 */}
        <div className="flex items-center gap-1">
          {GRADE_OPTIONS.map((g) => {
            const active = selectedGrades.includes(g)
            return (
              <button
                key={g}
                onClick={() => toggleGrade(g)}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {g}등급
              </button>
            )
          })}
        </div>

        <div className="h-4 w-px bg-border" />

        {/* 법원 */}
        <select
          value={selectedCourt}
          onChange={(e) => update("court", e.target.value)}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">전체 법원</option>
          {COURT_OPTIONS.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>

        {/* 물건종류 */}
        <select
          value={selectedType}
          onChange={(e) => update("type", e.target.value)}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">전체 종류</option>
          {PROPERTY_TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <div className="ml-auto flex items-center gap-2">
          {/* 상세 필터 토글 */}
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors ${
              showAdvanced || hasClientFilters
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <SlidersHorizontal className="h-3 w-3" />
            상세
          </button>

          {/* 정렬 */}
          <select
            value={selectedSort}
            onChange={(e) => update("sort", e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {SORT_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          {hasFilters && (
            <button
              onClick={resetFilters}
              className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              초기화
            </button>
          )}
        </div>
      </div>

      {/* 상세 필터 패널 */}
      {showAdvanced && (
        <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-2 border-t border-border pt-3">
          {/* 감정가 범위 (프리셋 칩) */}
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-medium text-muted-foreground">감정가</span>
            <div className="flex items-center gap-1">
              {PRICE_PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => selectPricePreset(p, idx)}
                  className={`rounded-md px-2 py-1 text-xs transition-colors ${
                    activePricePreset === idx
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-accent hover:text-foreground"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="h-6 w-px bg-border" />

          {/* 유찰 횟수 */}
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-medium text-muted-foreground">유찰 횟수</span>
            <select
              value={cfFail}
              onChange={(e) => update("cf_fail", e.target.value)}
              className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {FAIL_COUNT_OPTIONS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          <div className="h-6 w-px bg-border" />

          {/* 매각기일 범위 */}
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-medium text-muted-foreground">매각기일</span>
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={cfFrom}
                onChange={(e) => update("cf_from", e.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <span className="text-xs text-muted-foreground">~</span>
              <input
                type="date"
                value={cfTo}
                onChange={(e) => update("cf_to", e.target.value)}
                className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
        </div>
      )}

      {/* 활성 필터 chips */}
      {hasFilters && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selectedGrades.map((g) => (
            <FilterChip key={g} label={`${g}등급`} onRemove={() => toggleGrade(g)} />
          ))}
          {selectedCourt && (
            <FilterChip
              label={COURT_OPTIONS.find((c) => c.code === selectedCourt)?.label ?? selectedCourt}
              onRemove={() => update("court", "")}
            />
          )}
          {selectedType && (
            <FilterChip label={selectedType} onRemove={() => update("type", "")} />
          )}
          {(cfMin || cfMax) && (
            <FilterChip
              label={
                cfMin && cfMax
                  ? `${formatPrice(Number(cfMin))}~${formatPrice(Number(cfMax))}`
                  : cfMin
                    ? `${formatPrice(Number(cfMin))}~`
                    : `~${formatPrice(Number(cfMax))}`
              }
              onRemove={() => {
                const params = new URLSearchParams(searchParams.toString())
                params.delete("cf_min")
                params.delete("cf_max")
                params.delete("page")
                router.push(`${pathname}?${params.toString()}`)
              }}
            />
          )}
          {cfFail && (
            <FilterChip
              label={FAIL_COUNT_OPTIONS.find((f) => f.value === cfFail)?.label ?? `${cfFail}회`}
              onRemove={() => update("cf_fail", "")}
            />
          )}
          {(cfFrom || cfTo) && (
            <FilterChip
              label={`기일 ${cfFrom || ""}~${cfTo || ""}`}
              onRemove={() => {
                const params = new URLSearchParams(searchParams.toString())
                params.delete("cf_from")
                params.delete("cf_to")
                params.delete("page")
                router.push(`${pathname}?${params.toString()}`)
              }}
            />
          )}
        </div>
      )}
    </div>
  )
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
      {label}
      <button onClick={onRemove} className="rounded-full hover:bg-primary/20">
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}
