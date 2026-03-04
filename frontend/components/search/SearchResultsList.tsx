"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { ChevronUp, ChevronDown } from "lucide-react"
import { AuctionListRow } from "@/components/domain/AuctionListRow"
import type { AuctionListItem } from "@/lib/types"

const SORTABLE_COLUMNS = [
  { key: "appraised_value", label: "감정가",  width: "w-20" },
  { key: "minimum_bid",     label: "최저가",  width: "w-24" },
  { key: "discount_rate",   label: "할인율",  width: "w-12" },
  { key: "auction_date",    label: "기일",    width: "w-16" },
  { key: "bid_count",       label: "유찰",    width: "w-10" },
  { key: "grade",           label: "점수",    width: "w-12" },
] as const

interface Props {
  items: AuctionListItem[]
  total: number
}

export function SearchResultsList({ items, total }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const currentSort = searchParams.get("sort") ?? "grade"

  function handleSort(key: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("sort", key)
    params.delete("page")
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <div>
      {/* 데스크탑 컬럼 헤더 */}
      <div className="hidden sm:flex items-center gap-6 border-b border-border px-4 py-1.5 text-[11px] font-medium text-muted-foreground">
        <div className="w-10 shrink-0" /> {/* 등급 배지 영역 */}
        <div className="flex-1">소재지</div>
        {SORTABLE_COLUMNS.map((col) => (
          <button
            key={col.key}
            onClick={() => handleSort(col.key)}
            className={`flex items-center justify-end gap-0.5 hover:text-foreground transition-colors ${col.width} ${
              currentSort === col.key ? "text-primary" : ""
            }`}
          >
            {col.label}
            {currentSort === col.key ? (
              <ChevronUp size={10} />
            ) : (
              <ChevronDown size={10} className="opacity-30" />
            )}
          </button>
        ))}
        <div className="w-14 shrink-0" /> {/* 액션 버튼 영역 */}
      </div>

      {/* 리스트 행들 */}
      <div>
        {items.map((item) => (
          <AuctionListRow key={item.case_number} item={item} />
        ))}
      </div>

      {/* 하단 건수 */}
      {total > 0 && (
        <p className="px-4 py-2 text-xs text-muted-foreground">
          총 {total.toLocaleString()}건
        </p>
      )}
    </div>
  )
}
