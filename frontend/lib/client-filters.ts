import type { AuctionListItem } from "@/lib/types"

export interface ClientFilterParams {
  minPrice?: number | null      // 감정가 최소 (원 단위)
  maxPrice?: number | null      // 감정가 최대 (원 단위)
  failCount?: number | null     // 유찰 횟수 (0, 1, 2, 3=3+)
  dateFrom?: string | null      // 매각기일 시작 (ISO: "2026-03-01")
  dateTo?: string | null        // 매각기일 종료 (ISO: "2026-04-01")
}

/** 현재 페이지 아이템에 클라이언트 필터 적용 */
export function applyClientFilters(
  items: AuctionListItem[],
  filters: ClientFilterParams
): AuctionListItem[] {
  return items.filter((item) => {
    // 감정가 범위
    if (filters.minPrice != null && item.appraised_value != null) {
      if (item.appraised_value < filters.minPrice) return false
    }
    if (filters.maxPrice != null && item.appraised_value != null) {
      if (item.appraised_value > filters.maxPrice) return false
    }

    // 유찰 횟수
    if (filters.failCount != null) {
      const itemFail = Math.max(0, item.bid_count - 1)
      if (filters.failCount >= 3) {
        if (itemFail < 3) return false
      } else {
        if (itemFail !== filters.failCount) return false
      }
    }

    // 매각기일 범위
    if (filters.dateFrom && item.auction_date) {
      if (item.auction_date < filters.dateFrom) return false
    }
    if (filters.dateTo && item.auction_date) {
      if (item.auction_date > filters.dateTo) return false
    }

    return true
  })
}

/** 클라이언트 필터가 하나라도 활성인지 확인 */
export function hasActiveClientFilters(filters: ClientFilterParams): boolean {
  return (
    filters.minPrice != null ||
    filters.maxPrice != null ||
    filters.failCount != null ||
    (filters.dateFrom != null && filters.dateFrom !== "") ||
    (filters.dateTo != null && filters.dateTo !== "")
  )
}
