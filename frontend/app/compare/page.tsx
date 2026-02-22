"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AnimatePresence, motion } from "framer-motion"
import { Scale, Trash2 } from "lucide-react"
import { getCompareList, toggleCompare, clearCompare } from "@/lib/compare"
import { fetchAuctionDetail } from "@/lib/api"
import { GradeBadge } from "@/components/domain/GradeBadge"
import { formatPrice, calcDiscount, calcDday } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { AuctionDetailResponse } from "@/lib/types"

// 점수 미니 바
function MiniScoreBar({ value, best }: { value: number | null; best: boolean }) {
  const pct = value ?? 0
  const color =
    pct >= 70 ? "bg-primary" : pct >= 50 ? "bg-amber-400" : "bg-red-400"

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span
        className={cn(
          "w-10 text-right text-xs tabular-nums",
          value == null
            ? "text-muted-foreground"
            : best
            ? "font-bold text-primary"
            : "font-medium text-foreground"
        )}
      >
        {value != null ? `${value.toFixed(0)}` : "-"}
      </span>
    </div>
  )
}

// 비교 행
interface RowProps {
  label: string
  values: (string | React.ReactNode)[]
  highlight?: number // 하이라이트할 인덱스
}
function CompareRow({ label, values, highlight }: RowProps) {
  return (
    <div className="grid items-center gap-3 border-b border-border py-2.5" style={{ gridTemplateColumns: `8rem repeat(${values.length}, 1fr)` }}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {values.map((v, i) => (
        <div key={i} className={cn("text-sm", highlight === i && "font-bold text-primary")}>
          {v}
        </div>
      ))}
    </div>
  )
}

export default function ComparePage() {
  const [items, setItems] = useState<AuctionDetailResponse[]>([])
  const [loading, setLoading] = useState(true)

  function loadItems() {
    const keys = getCompareList()
    if (keys.length === 0) {
      setItems([])
      setLoading(false)
      return
    }
    setLoading(true)
    Promise.all(keys.map((cn) => fetchAuctionDetail(cn).catch(() => null)))
      .then((results) => setItems(results.filter(Boolean) as AuctionDetailResponse[]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadItems()
  }, [])

  function handleRemove(caseNumber: string) {
    toggleCompare(caseNumber)
    setItems((prev) => prev.filter((i) => i.case_number !== caseNumber))
    window.dispatchEvent(new Event("compare-change"))
  }

  function handleClear() {
    clearCompare()
    setItems([])
    window.dispatchEvent(new Event("compare-change"))
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-foreground">물건 비교</h1>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-64 w-full rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Scale className="h-12 w-12 opacity-20" />
        <div>
          <p className="text-sm font-medium text-foreground">비교할 물건을 선택하세요</p>
          <p className="mt-1 text-xs">검색에서 저울 아이콘을 눌러 추가하세요 (최대 3건)</p>
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

  // 최고값 인덱스 계산
  function bestIdx(getter: (item: AuctionDetailResponse) => number | null | undefined): number | undefined {
    let best = -Infinity
    let idx: number | undefined
    items.forEach((item, i) => {
      const v = getter(item)
      if (v != null && v > best) {
        best = v
        idx = i
      }
    })
    return idx
  }

  const bestTotal = bestIdx((i) => i.score?.total_score)
  const bestLegal = bestIdx((i) => i.score?.legal_score)
  const bestPrice = bestIdx((i) => i.score?.price_score)
  const bestLocation = bestIdx((i) => i.score?.location_score)
  const bestDiscount = bestIdx((i) => calcDiscount(i.minimum_bid, i.appraised_value))

  return (
    <div>
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground">
          물건 비교{" "}
          <span className="text-sm font-normal text-muted-foreground">{items.length}건</span>
        </h1>
        <button
          onClick={handleClear}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          초기화
        </button>
      </div>

      {/* 모바일: 카드 나열, sm+: 가로 비교 테이블 */}

      {/* --- 모바일 뷰 (카드 형태) --- */}
      <div className="space-y-4 sm:hidden">
        <AnimatePresence mode="popLayout">
          {items.map((item) => {
            const failCount = Math.max(0, item.bid_count - 1)
            const discount = calcDiscount(item.minimum_bid, item.appraised_value)
            const dday = calcDday(item.auction_date)

            return (
              <motion.div
                key={item.case_number}
                layout
                initial={{ opacity: 0, x: 0 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -40 }}
                transition={{ duration: 0.2 }}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="mb-3 flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {item.score?.grade && (
                      <GradeBadge grade={item.score.grade} provisional={item.score.grade_provisional} size="md" />
                    )}
                    <span className="text-sm font-semibold text-foreground">
                      {item.score?.total_score?.toFixed(1) ?? "-"}점
                    </span>
                  </div>
                  <button
                    onClick={() => handleRemove(item.case_number)}
                    className="rounded-md p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <p className="mb-2 text-sm font-medium leading-snug text-foreground line-clamp-2">
                  {item.address}
                </p>

                <div className="space-y-1.5 text-xs text-muted-foreground">
                  <p>{item.property_type} · {item.court}</p>
                  <p>감정가 {formatPrice(item.appraised_value)} / 최저 {formatPrice(item.minimum_bid)}</p>
                  {discount != null && <p>할인율 {Math.round(discount * 100)}%</p>}
                  <p>{dday} · {failCount > 0 ? `${failCount}회 유찰` : "신건"}</p>
                </div>

                {item.score && (
                  <div className="mt-3 space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">권리분석</span>
                      <span>{item.score.legal_score?.toFixed(0) ?? "-"}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">수익성</span>
                      <span>{item.score.price_score?.toFixed(0) ?? "-"}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">입지</span>
                      <span>{item.score.location_score?.toFixed(0) ?? "-"}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">명도</span>
                      <span>{item.score.occupancy_score?.toFixed(0) ?? "대기"}</span>
                    </div>
                  </div>
                )}

                <div className="mt-3">
                  <Link
                    href={`/auction/${encodeURIComponent(item.case_number)}`}
                    className="block rounded-md bg-primary/10 px-3 py-2 text-center text-xs font-semibold text-primary hover:bg-primary/20"
                  >
                    상세 보기
                  </Link>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>

      {/* --- 데스크탑 뷰 (가로 비교 테이블) --- */}
      <div className="hidden sm:block">
        <div className="rounded-lg border border-border bg-card p-4">
          {/* 물건 헤더 */}
          <div
            className="grid items-start gap-3 border-b border-border pb-3"
            style={{ gridTemplateColumns: `8rem repeat(${items.length}, 1fr)` }}
          >
            <div />
            <AnimatePresence mode="popLayout">
              {items.map((item) => (
                <motion.div
                  key={item.case_number}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    {item.score?.grade && (
                      <GradeBadge grade={item.score.grade} provisional={item.score.grade_provisional} size="md" />
                    )}
                    <button
                      onClick={() => handleRemove(item.case_number)}
                      className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <p className="text-sm font-semibold leading-snug text-foreground line-clamp-2">
                    {item.address}
                  </p>
                  <p className="text-xs text-muted-foreground">{item.property_type} · {item.court}</p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          {/* 점수 섹션 */}
          <CompareRow
            label="종합 점수"
            highlight={bestTotal}
            values={items.map((i) =>
              i.score?.total_score != null ? `${i.score.total_score.toFixed(1)}점` : "-"
            )}
          />
          <CompareRow
            label="권리분석"
            highlight={bestLegal}
            values={items.map((i, idx) => (
              <MiniScoreBar key={idx} value={i.score?.legal_score ?? null} best={bestLegal === idx} />
            ))}
          />
          <CompareRow
            label="수익성"
            highlight={bestPrice}
            values={items.map((i, idx) => (
              <MiniScoreBar key={idx} value={i.score?.price_score ?? null} best={bestPrice === idx} />
            ))}
          />
          <CompareRow
            label="입지"
            highlight={bestLocation}
            values={items.map((i, idx) => (
              <MiniScoreBar key={idx} value={i.score?.location_score ?? null} best={bestLocation === idx} />
            ))}
          />
          <CompareRow
            label="명도"
            values={items.map((i, idx) => (
              <MiniScoreBar key={idx} value={i.score?.occupancy_score ?? null} best={false} />
            ))}
          />

          {/* 구분선 */}
          <div className="my-2" />

          {/* 가격 섹션 */}
          <CompareRow
            label="감정가"
            values={items.map((i) => formatPrice(i.appraised_value))}
          />
          <CompareRow
            label="최저매각가격"
            values={items.map((i) => formatPrice(i.minimum_bid))}
          />
          <CompareRow
            label="할인율"
            highlight={bestDiscount}
            values={items.map((i) => {
              const d = calcDiscount(i.minimum_bid, i.appraised_value)
              return d != null ? `${Math.round(d * 100)}%` : "-"
            })}
          />
          <CompareRow
            label="매각기일"
            values={items.map((i, idx) => {
              const dday = calcDday(i.auction_date)
              return (
                <span key={idx}>
                  {i.auction_date?.replace(/-/g, ".") ?? "-"}{" "}
                  <span className="text-xs text-muted-foreground">{dday}</span>
                </span>
              )
            })}
          />
          <CompareRow
            label="유찰횟수"
            values={items.map((i) => {
              const f = Math.max(0, i.bid_count - 1)
              return f > 0 ? `${f}회` : "신건"
            })}
          />
          <CompareRow
            label="낙찰가율 (참고)"
            values={items.map((i) =>
              i.score?.predicted_winning_ratio != null
                ? `${(i.score.predicted_winning_ratio * 100).toFixed(0)}%`
                : "-"
            )}
          />

          {/* 액션 */}
          <div
            className="grid gap-3 pt-3"
            style={{ gridTemplateColumns: `8rem repeat(${items.length}, 1fr)` }}
          >
            <div />
            {items.map((item) => (
              <Link
                key={item.case_number}
                href={`/auction/${encodeURIComponent(item.case_number)}`}
                className="block rounded-md bg-primary/10 px-3 py-2 text-center text-xs font-semibold text-primary hover:bg-primary/20"
              >
                상세 보기
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
