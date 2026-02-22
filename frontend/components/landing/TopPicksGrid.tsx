"use client"

import { motion } from "framer-motion"
import { AuctionCard } from "@/components/domain/AuctionCard"
import type { AuctionListItem } from "@/lib/types"

interface Props {
  items: AuctionListItem[]
}

export function TopPicksGrid({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
        현재 분석된 물건이 없습니다.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {items.map((item, i) => (
        <motion.div
          key={item.case_number}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: i * 0.07, ease: "easeOut" }}
        >
          <AuctionCard item={item} />
        </motion.div>
      ))}
    </div>
  )
}
