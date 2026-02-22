"use client"

import { GradeBadge } from "@/components/domain/GradeBadge"
import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"
import { PredictionPill } from "@/components/domain/PredictionPill"
import { CoveragePill } from "@/components/domain/CoveragePill"
import { formatPrice, calcDiscount, calcDday } from "@/lib/utils"
import type { AuctionDetailResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

interface Props {
  auction: AuctionDetailResponse
}

export function DecisionSection({ auction }: Props) {
  const score = auction.score
  const failCount = Math.max(0, auction.bid_count - 1)
  const discount = calcDiscount(auction.minimum_bid, auction.appraised_value)
  const dday = calcDday(auction.auction_date)

  return (
    <section className="space-y-4">
      {/* 등급 + 주소 + 태그 */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {score?.grade && (
              <GradeBadge
                grade={score.grade}
                provisional={score.grade_provisional}
                size="lg"
              />
            )}
            <span className="rounded-full bg-secondary px-2.5 py-1 text-sm font-medium text-secondary-foreground">
              {auction.property_type}
            </span>
            {failCount > 0 && (
              <span className="rounded-full bg-orange-50 px-2.5 py-1 text-sm font-medium text-orange-600 ring-1 ring-orange-100 dark:bg-orange-950 dark:text-orange-400 dark:ring-orange-900">
                {failCount}회 유찰
              </span>
            )}
          </div>
          <h1 className="text-xl font-bold leading-snug text-foreground sm:text-2xl">
            {auction.address}
          </h1>
          <p className="text-sm text-muted-foreground">
            {auction.court} · {auction.case_number}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <FavoriteButton caseNumber={auction.case_number} />
        </div>
      </div>

      {/* 가격 3종 + D-day */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <PriceCard label="감정가" value={formatPrice(auction.appraised_value)} />
        <PriceCard
          label="최저매각가격"
          value={formatPrice(auction.minimum_bid)}
          sub={
            discount != null
              ? `감정가 대비 ${Math.round(discount * 100)}% 할인`
              : undefined
          }
          subNeutral
        />
        <PriceCard
          label="매각기일"
          value={auction.auction_date?.replace(/-/g, ".") ?? "-"}
          sub={dday !== "-" ? dday : undefined}
          subNeutral={dday.startsWith("D+") || dday === "오늘"}
        />
        {auction.winning_bid ? (
          <PriceCard
            label="낙찰가"
            value={formatPrice(auction.winning_bid)}
            sub={
              auction.winning_ratio
                ? `낙찰가율 ${(auction.winning_ratio * 100).toFixed(1)}%`
                : undefined
            }
            subNeutral
          />
        ) : (
          <div className="flex flex-col gap-1 rounded-md bg-muted p-3">
            <span className="text-xs text-muted-foreground">모델 추정 범위 (참고)</span>
            <PredictionPill
              ratio={score?.predicted_winning_ratio}
              minimumBid={auction.minimum_bid}
            />
          </div>
        )}
      </div>

      {/* 커버리지 */}
      {score && (
        <div className="flex flex-wrap items-center gap-3 rounded-md bg-muted px-3 py-2">
          <span className="text-xs text-muted-foreground">분석 커버리지</span>
          <CoveragePill coverage={score.score_coverage} />
          {score.grade_provisional && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              * 일부 항목 미분석으로 잠정 등급
            </span>
          )}
        </div>
      )}

      <DisclaimerBanner />
    </section>
  )
}

function PriceCard({
  label,
  value,
  sub,
  subNeutral = false,
}: {
  label: string
  value: string
  sub?: string
  subNeutral?: boolean
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-muted p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-base font-bold tabular-nums text-foreground">{value}</span>
      {sub && (
        <span className={cn("text-xs", subNeutral ? "text-muted-foreground" : "text-muted-foreground")}>
          {sub}
        </span>
      )}
    </div>
  )
}
