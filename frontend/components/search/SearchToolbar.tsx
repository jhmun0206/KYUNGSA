"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState, useCallback } from "react"
import { Search } from "lucide-react"
import { SORT_OPTIONS } from "@/lib/constants"

interface Props {
  total: number
}

export function SearchToolbar({ total }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const currentSort = searchParams.get("sort") ?? "auction_date"
  const [keyword, setKeyword] = useState(searchParams.get("q") ?? "")

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

  const handleKeywordSearch = () => {
    update("q", keyword.trim())
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      {/* 검색 */}
      <div className="relative flex-1 max-w-sm">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="주소, 건물명 검색..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleKeywordSearch()
          }}
          className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 pl-8 pr-3 py-1.5 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* 정렬 */}
      <select
        value={currentSort}
        onChange={(e) => update("sort", e.target.value)}
        className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {SORT_OPTIONS.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>

      {/* 건수 */}
      <span className="text-sm text-slate-500 dark:text-slate-400 whitespace-nowrap">
        총 <span className="font-semibold text-slate-700 dark:text-slate-300">{total.toLocaleString()}</span>건
      </span>
    </div>
  )
}
