"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useCallback } from "react"
import { COURT_OPTIONS, GRADE_OPTIONS } from "@/lib/constants"
import { cn } from "@/lib/utils"

export function AuctionFilters() {
  const router = useRouter()
  const params = useSearchParams()

  const update = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(params.toString())
      if (value) {
        next.set(key, value)
      } else {
        next.delete(key)
      }
      next.delete("page")
      router.push(`/?${next.toString()}`)
    },
    [params, router]
  )

  const currentCourt = params.get("court_office_code") || ""
  const currentGrade = params.get("grade") || ""
  const currentSort = params.get("sort") || "grade"

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      {/* 법원 필터 */}
      <select
        value={currentCourt}
        onChange={(e) => update("court_office_code", e.target.value)}
        className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="">전체 법원</option>
        {COURT_OPTIONS.map((c) => (
          <option key={c.code} value={c.code}>
            {c.label}
          </option>
        ))}
      </select>

      {/* 등급 필터 */}
      <div className="flex items-center gap-1">
        {GRADE_OPTIONS.map((g) => {
          const selected = currentGrade === g
          return (
            <button
              key={g}
              onClick={() => update("grade", selected ? "" : g)}
              className={cn(
                "rounded-md px-2.5 py-1 text-sm font-semibold transition-colors",
                selected
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground hover:bg-accent"
              )}
            >
              {g}
            </button>
          )
        })}
      </div>

      {/* 정렬 */}
      <select
        value={currentSort}
        onChange={(e) => update("sort", e.target.value)}
        className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="grade">등급순</option>
        <option value="auction_date">매각기일순</option>
        <option value="appraised_value">감정가순</option>
      </select>
    </div>
  )
}
