"use client"

import Link from "next/link"
import { GradeBadge } from "@/components/domain/GradeBadge"
import { CoveragePill } from "@/components/domain/CoveragePill"
import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { CompareButton } from "@/components/domain/CompareButton"
import { formatPrice, calcDiscount, calcDday } from "@/lib/utils"
import { COURT_LABELS } from "@/lib/constants"
import type { AuctionListItem } from "@/lib/types"
import { cn } from "@/lib/utils"

interface Props {
  item: AuctionListItem
  className?: string
}

/**
 * 경매 물건 카드 (v4 재설계)
 * ⚠️ 할인율 배지에 green 색상 사용 금지 — 투자 추천으로 오인 방지
 * ⚠️ 정보위계: 등급/주소 → 가격 → 기일/부가정보 순
 */
export function AuctionCard({ item, className }: Props) {
  const failCount = item.bid_count - 1
  const discount = calcDiscount(item.minimum_bid, item.appraised_value)
  const dday = calcDday(item.auction_date)
  const courtLabel = COURT_LABELS[item.court_office_code] ?? item.court

  return (
    <div
      className={cn(
        "group relative flex flex-col rounded-lg border border-border bg-card transition-shadow hover:shadow-md",
        className
      )}
    >
      <Link
        href={`/auction/${encodeURIComponent(item.case_number)}`}
        className="flex flex-col gap-3 p-4"
      >
        {/* 상단: 등급 + 태그 + 즐겨찾기 */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <GradeBadge grade={item.grade} provisional={item.grade_provisional} size="md" />
            <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
              {item.property_type || "미분류"}
            </span>
            {failCount > 0 && (
              <span className="rounded-full bg-orange-50 px-2 py-0.5 text-xs font-medium text-orange-600 ring-1 ring-orange-100">
                {failCount}회 유찰
              </span>
            )}
          </div>
          {/* 즐겨찾기는 링크 영역 밖 → onClick 분리 */}
        </div>

        {/* 주소 */}
        <p className="text-sm font-semibold leading-snug text-foreground line-clamp-2">
          {item.address || "-"}
        </p>

        {/* 가격 정보 */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
          <div className="flex flex-col gap-0.5">
            <span className="text-text-weak">감정가</span>
            <span className="font-semibold tabular-nums text-foreground">
              {formatPrice(item.appraised_value)}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-text-weak">최저매각가격</span>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold tabular-nums text-foreground">
                {formatPrice(item.minimum_bid)}
              </span>
              {/* 할인율: neutral(slate) 색상만 사용 — green 금지 */}
              {discount != null && (
                <span className="rounded bg-slate-100 px-1 py-0.5 text-[10px] font-semibold tabular-nums text-slate-600 ring-1 ring-slate-200">
                  {Math.round(discount * 100)}% ↓
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 하단: 기일 + 법원 */}
        <div className="flex items-center justify-between text-xs text-text-mid">
          <div className="flex items-center gap-2">
            <span>
              {item.auction_date ? item.auction_date.replace(/-/g, ".") : "-"}
            </span>
            {item.auction_date && (
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 font-semibold tabular-nums",
                  dday === "오늘"
                    ? "bg-red-50 text-red-600"
                    : dday.startsWith("D-") && parseInt(dday.slice(2)) <= 3
                    ? "bg-orange-50 text-orange-600"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {dday}
              </span>
            )}
          </div>
          <span className="text-text-weak">{courtLabel}</span>
        </div>

        {/* 점수 커버리지 */}
        {item.total_score != null && (
          <div className="mt-0.5 flex items-center justify-between gap-3">
            <CoveragePill coverage={item.score_coverage} />
            <span className="text-xs font-semibold tabular-nums text-text-strong">
              {item.total_score.toFixed(1)}점
            </span>
          </div>
        )}
      </Link>

      {/* 액션 버튼 — 카드 우측 상단 절대 위치 */}
      <div className="absolute right-3 top-3 flex items-center gap-0.5">
        <CompareButton caseNumber={item.case_number} />
        <FavoriteButton caseNumber={item.case_number} />
      </div>
    </div>
  )
}
