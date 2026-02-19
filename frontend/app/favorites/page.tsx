"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { getFavorites, toggleFavorite } from "@/lib/favorites"
import { fetchAuctionDetail } from "@/lib/api"
import { GradeBadge } from "@/components/domain/GradeBadge"
import { formatPrice, calcDday } from "@/lib/utils"
import { Star, Trash2 } from "lucide-react"
import type { AuctionDetailResponse } from "@/lib/types"
import { Skeleton } from "@/components/ui/skeleton"

export default function FavoritesPage() {
  const [items, setItems] = useState<AuctionDetailResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [keys, setKeys] = useState<string[]>([])

  useEffect(() => {
    const favs = getFavorites()
    setKeys(favs)
    if (favs.length === 0) {
      setLoading(false)
      return
    }
    Promise.all(favs.map((cn) => fetchAuctionDetail(cn).catch(() => null)))
      .then((results) => {
        setItems(results.filter(Boolean) as AuctionDetailResponse[])
      })
      .finally(() => setLoading(false))
  }, [])

  function handleRemove(caseNumber: string) {
    toggleFavorite(caseNumber)
    setItems((prev) => prev.filter((i) => i.case_number !== caseNumber))
    setKeys((prev) => prev.filter((k) => k !== caseNumber))
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-foreground">즐겨찾기</h1>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (keys.length === 0 || items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-muted-foreground">
        <Star className="h-12 w-12 opacity-20" />
        <p className="text-sm">즐겨찾기한 물건이 없습니다.</p>
        <Link href="/" className="text-sm text-primary hover:underline">
          물건 목록으로 →
        </Link>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-foreground">
          즐겨찾기{" "}
          <span className="text-sm font-normal text-muted-foreground">{items.length}건</span>
        </h1>
      </div>

      <div className="space-y-2">
        {items.map((item) => {
          const failCount = Math.max(0, item.bid_count - 1)
          const dday = calcDday(item.auction_date)
          return (
            <div
              key={item.case_number}
              className="flex items-center justify-between rounded-lg border border-border bg-card p-4 transition-shadow hover:shadow-sm"
            >
              <div className="flex min-w-0 items-start gap-3">
                {item.score?.grade && (
                  <GradeBadge
                    grade={item.score.grade}
                    provisional={item.score.grade_provisional}
                    size="sm"
                  />
                )}
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {item.address}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {item.property_type} · {item.court}
                    {failCount > 0 && ` · ${failCount}회 유찰`}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    감정가 {formatPrice(item.appraised_value)} / 최저{" "}
                    {formatPrice(item.minimum_bid)}
                    {item.auction_date && (
                      <span className="ml-2 font-medium text-foreground">
                        {dday}
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div className="ml-3 flex shrink-0 items-center gap-1">
                <Link
                  href={`/auction/${encodeURIComponent(item.case_number)}`}
                  className="rounded-md bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/20"
                >
                  상세
                </Link>
                <button
                  onClick={() => handleRemove(item.case_number)}
                  className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  title="즐겨찾기 해제"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
