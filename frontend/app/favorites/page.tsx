"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { getFavorites, toggleFavorite } from "@/lib/favorites"
import { fetchAuctionDetail } from "@/lib/api"
import { GradeBadge } from "@/components/auction/GradeBadge"
import { Star } from "lucide-react"
import type { AuctionDetailResponse } from "@/lib/types"

function formatAmount(v: number | null): string {
  if (v === null) return "-"
  const uk = Math.round(v / 10000)
  if (uk >= 10000) return `${(uk / 10000).toFixed(1)}억`
  return `${uk.toLocaleString()}만원`
}

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
      <div className="flex h-48 items-center justify-center text-gray-400">
        불러오는 중...
      </div>
    )
  }

  if (keys.length === 0 || items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20 text-gray-400">
        <Star className="h-12 w-12 opacity-30" />
        <p>즐겨찾기한 물건이 없습니다.</p>
        <Link
          href="/"
          className="text-sm text-indigo-600 hover:underline"
        >
          목록으로 가기 →
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">
        즐겨찾기{" "}
        <span className="text-base font-normal text-gray-500">
          {items.length}건
        </span>
      </h1>

      <div className="space-y-3">
        {items.map((item) => {
          const failCount = Math.max(0, item.bid_count - 1)
          return (
            <div
              key={item.case_number}
              className="flex items-center justify-between rounded-xl border border-gray-100 bg-white p-4 shadow-sm"
            >
              <div className="flex items-start gap-3">
                {item.score?.grade && (
                  <GradeBadge
                    grade={item.score.grade}
                    provisional={item.score.grade_provisional}
                  />
                )}
                <div>
                  <p className="text-sm font-semibold text-gray-900 line-clamp-1">
                    {item.address}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {item.property_type} · {item.court} ·{" "}
                    {failCount > 0 ? `${failCount}회 유찰` : "유찰 없음"}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    감정가 {formatAmount(item.appraised_value)} / 최저
                    {formatAmount(item.minimum_bid)}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <Link
                  href={`/auction/${encodeURIComponent(item.case_number)}`}
                  className="rounded-lg bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100"
                >
                  상세
                </Link>
                <button
                  onClick={() => handleRemove(item.case_number)}
                  className="rounded-lg border border-gray-200 p-1.5 text-gray-400 hover:text-red-500"
                  title="즐겨찾기 해제"
                >
                  <Star className="h-4 w-4 fill-current" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
