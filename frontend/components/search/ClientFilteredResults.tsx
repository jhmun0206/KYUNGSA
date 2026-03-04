"use client"

import { SearchResultsList } from "@/components/search/SearchResultsList"
import {
  applyClientFilters,
  hasActiveClientFilters,
  type ClientFilterParams,
} from "@/lib/client-filters"
import type { AuctionListItem } from "@/lib/types"

interface Props {
  items: AuctionListItem[]
  serverTotal: number
  clientFilters: ClientFilterParams
}

/** 클라이언트 필터를 적용한 결과 래퍼 — 현재 페이지 내 필터링 */
export function ClientFilteredResults({ items, serverTotal, clientFilters }: Props) {
  const isFiltering = hasActiveClientFilters(clientFilters)
  const filtered = isFiltering ? applyClientFilters(items, clientFilters) : items
  const displayTotal = isFiltering ? filtered.length : serverTotal

  return (
    <div>
      {isFiltering && (
        <p className="mb-2 text-xs text-amber-600 dark:text-amber-400">
          현재 페이지 내 필터링 결과입니다 ({filtered.length}/{items.length}건)
        </p>
      )}
      <SearchResultsList items={filtered} total={displayTotal} />
    </div>
  )
}
