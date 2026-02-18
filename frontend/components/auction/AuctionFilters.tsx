"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { useCallback } from "react"
import { COURT_OPTIONS, GRADE_OPTIONS } from "@/lib/constants"

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
      next.delete("page")  // 필터 변경 시 1페이지로
      router.push(`/?${next.toString()}`)
    },
    [params, router]
  )

  const currentCourt = params.get("court_office_code") || ""
  const currentGrade = params.get("grade") || ""
  const currentSort = params.get("sort") || "grade"

  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* 법원 필터 */}
      <select
        value={currentCourt}
        onChange={(e) => update("court_office_code", e.target.value)}
        className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-400"
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
        <span className="text-sm text-gray-500">등급</span>
        {GRADE_OPTIONS.map((g) => {
          const selected = currentGrade.includes(g)
          return (
            <button
              key={g}
              onClick={() => update("grade", selected ? "" : g)}
              className={`px-2.5 py-1 rounded-lg text-sm font-semibold transition-colors ${
                selected
                  ? "bg-indigo-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
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
        className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-400"
      >
        <option value="grade">등급순</option>
        <option value="auction_date">매각기일순</option>
        <option value="appraised_value">감정가순</option>
        <option value="predicted_winning_ratio">낙찰가율순</option>
      </select>
    </div>
  )
}
