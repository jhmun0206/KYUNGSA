"use client"

import { useEffect, useState, useMemo } from "react"
import Link from "next/link"
import { AnimatePresence, motion } from "framer-motion"
import { getFavorites, toggleFavorite } from "@/lib/favorites"
import { fetchAuctionDetail } from "@/lib/api"
import { SignalBadge } from "@/components/domain/SignalBadge"
import { calcListSignal } from "@/lib/risk-signals"
import { formatPrice, calcDday, calcDiscount } from "@/lib/utils"
import { Heart, Trash2 } from "lucide-react"
import type { AuctionDetailResponse } from "@/lib/types"
import { Skeleton } from "@/components/ui/skeleton"

type SortKey = "saved" | "score" | "dday"

export default function FavoritesPage() {
  const [items, setItems] = useState<AuctionDetailResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [keys, setKeys] = useState<string[]>([])
  const [sort, setSort] = useState<SortKey>("saved")

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

  const { activeItems, soldItems } = useMemo(() => {
    const active = items.filter((i) => i.status !== "매각")
    const sold = items.filter((i) => i.status === "매각")
    return { activeItems: active, soldItems: sold }
  }, [items])

  const sorted = useMemo(() => {
    const arr = [...activeItems]
    if (sort === "score") {
      arr.sort((a, b) => (b.score?.total_score ?? -1) - (a.score?.total_score ?? -1))
    } else if (sort === "dday") {
      arr.sort((a, b) => {
        const da = a.auction_date ?? ""
        const db = b.auction_date ?? ""
        return da < db ? -1 : da > db ? 1 : 0
      })
    }
    // "saved" → 저장 순서(keys 배열 순서) 유지
    return arr
  }, [activeItems, sort])

  // 요약 통계 (진행중 물건 기준)
  const avgScore = useMemo(() => {
    const scored = activeItems.filter((i) => i.score?.total_score != null)
    if (scored.length === 0) return null
    const sum = scored.reduce((acc, i) => acc + (i.score!.total_score ?? 0), 0)
    return (sum / scored.length).toFixed(1)
  }, [activeItems])

  const avgDiscount = useMemo(() => {
    const discounted = activeItems
      .map((i) => calcDiscount(i.minimum_bid, i.appraised_value))
      .filter((d): d is number => d != null)
    if (discounted.length === 0) return null
    const avg = discounted.reduce((a, b) => a + b, 0) / discounted.length
    return Math.round(avg * 100)
  }, [activeItems])

  if (loading) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-foreground">관심 목록</h1>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (keys.length === 0 || items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Heart className="h-12 w-12 opacity-20" />
        <div>
          <p className="text-sm font-medium text-foreground">저장한 매물이 없습니다</p>
          <p className="mt-1 text-xs">검색에서 카드 우측 하트를 눌러 저장하세요</p>
        </div>
        <Link
          href="/search"
          className="mt-2 rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          물건 검색하기 →
        </Link>
      </div>
    )
  }

  return (
    <div>
      {/* 헤더 */}
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">
          관심 목록{" "}
          <span className="text-sm font-normal text-muted-foreground">{items.length}건</span>
          {soldItems.length > 0 && (
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              (진행중 {activeItems.length}, 종료 {soldItems.length})
            </span>
          )}
        </h1>

        {/* 정렬 */}
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          className="rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="saved">최근 저장순</option>
          <option value="score">점수 높은순</option>
          <option value="dday">매각기일순</option>
        </select>
      </div>

      {/* 요약 스트립 */}
      {items.length > 0 && (
        <div className="mb-5 flex flex-wrap gap-4 rounded-lg bg-muted px-4 py-3 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">저장</span>
            <span className="font-semibold text-foreground">{items.length}건</span>
          </div>
          {avgScore && (
            <div className="flex items-center gap-1.5">
              <span className="text-muted-foreground">평균 점수</span>
              <span className="font-semibold text-foreground">{avgScore}점</span>
            </div>
          )}
          {avgDiscount != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-muted-foreground">평균 할인율</span>
              <span className="font-semibold text-foreground">{avgDiscount}%</span>
            </div>
          )}
        </div>
      )}

      {/* 진행중 카드 목록 */}
      <ul className="space-y-2">
        <AnimatePresence mode="popLayout">
          {sorted.map((item) => {
            const failCount = Math.max(0, item.bid_count - 1)
            const dday = calcDday(item.auction_date)
            return (
              <motion.li
                key={item.case_number}
                layout
                initial={{ opacity: 0, x: 0 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -40 }}
                transition={{ duration: 0.22 }}
              >
                <div className="flex items-center justify-between rounded-lg border border-border bg-card p-4 transition-shadow hover:shadow-sm">
                  <div className="flex min-w-0 items-start gap-3">
                    <SignalBadge
                      color={item.score ? calcListSignal(item.score) : "unknown"}
                      size="sm"
                    />
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
                          <span className="ml-2 font-medium text-foreground">{dday}</span>
                        )}
                      </p>
                    </div>
                  </div>

                  <div className="ml-3 flex shrink-0 items-center gap-1">
                    <Link
                      href={`/auction/${encodeURIComponent(item.case_number)}${(item.property_sequence ?? 1) > 1 ? `?seq=${item.property_sequence}` : ""}`}
                      className="rounded-md bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/20"
                    >
                      상세
                    </Link>
                    <button
                      onClick={() => handleRemove(item.case_number)}
                      className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                      title="관심 해제"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>

      {/* 종료된 관심 물건 섹션 */}
      {soldItems.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
            종료된 관심 물건{" "}
            <span className="font-normal">{soldItems.length}건</span>
          </h2>
          <ul className="space-y-2 opacity-70">
            {soldItems.map((item) => {
              const failCount = Math.max(0, item.bid_count - 1)
              return (
                <li key={item.case_number}>
                  <div className="flex items-center justify-between rounded-lg border border-border bg-card p-4">
                    <div className="flex min-w-0 items-start gap-3">
                      <SignalBadge
                        color={item.score ? calcListSignal(item.score) : "unknown"}
                        size="sm"
                      />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">
                          {item.address}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {item.property_type} · {item.court}
                          {failCount > 0 && ` · ${failCount}회 유찰`}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          감정가 {formatPrice(item.appraised_value)}
                          {item.winning_bid && (
                            <span className="ml-2">
                              낙찰가 <span className="font-medium text-foreground">{formatPrice(item.winning_bid)}</span>
                              {item.winning_ratio && (
                                <span className="ml-1 text-muted-foreground">({(item.winning_ratio * 100).toFixed(0)}%)</span>
                              )}
                            </span>
                          )}
                        </p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          매각완료{item.winning_date && ` · ${item.winning_date.replace(/-/g, ".")}`}
                        </p>
                      </div>
                    </div>

                    <div className="ml-3 flex shrink-0 items-center gap-1">
                      <Link
                        href={`/auction/${encodeURIComponent(item.case_number)}${(item.property_sequence ?? 1) > 1 ? `?seq=${item.property_sequence}` : ""}`}
                        className="rounded-md bg-muted px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground"
                      >
                        상세
                      </Link>
                      <button
                        onClick={() => handleRemove(item.case_number)}
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        title="관심 해제"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
