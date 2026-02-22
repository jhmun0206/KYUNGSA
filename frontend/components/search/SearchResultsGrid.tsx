"use client"

import { AnimatePresence, motion } from "framer-motion"
import { AuctionCard } from "@/components/domain/AuctionCard"
import type { AuctionListItem } from "@/lib/types"

interface Props {
  items: AuctionListItem[]
  total: number
}

export function SearchResultsGrid({ items, total }: Props) {
  return (
    <div className="space-y-3">
      {/* 결과 요약 */}
      <p className="text-sm text-muted-foreground">
        총 <span className="font-semibold text-foreground">{total.toLocaleString()}</span>건
      </p>

      {/* 카드 그리드 */}
      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
          <span className="text-4xl opacity-25">🔍</span>
          <p className="text-sm font-medium text-foreground">검색 결과가 없습니다</p>
          <p className="text-xs text-muted-foreground">필터 조건을 변경해 보세요</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <AnimatePresence mode="popLayout">
            {items.map((item, i) => (
              <motion.div
                key={item.case_number}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3, delay: i * 0.04, ease: "easeOut" }}
                layout
              >
                <AuctionCard item={item} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
