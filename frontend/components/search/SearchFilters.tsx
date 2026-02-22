"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useCallback } from "react"
import { X } from "lucide-react"
import { COURT_OPTIONS, GRADE_OPTIONS, PROPERTY_TYPE_OPTIONS } from "@/lib/constants"

const SORT_OPTIONS = [
  { value: "grade", label: "등급순" },
  { value: "auction_date", label: "매각기일순" },
  { value: "appraised_value", label: "감정가순" },
  { value: "predicted_winning_ratio", label: "낙찰가율순" },
]

export function SearchFilters() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const selectedGrades = (searchParams.get("grade") ?? "").split(",").filter(Boolean)
  const selectedCourt = searchParams.get("court") ?? ""
  const selectedType = searchParams.get("type") ?? ""
  const selectedSort = searchParams.get("sort") ?? "grade"

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

  const hasFilters = selectedGrades.length > 0 || selectedCourt || selectedType

  const resetFilters = () => {
    const params = new URLSearchParams()
    params.set("sort", selectedSort)
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
