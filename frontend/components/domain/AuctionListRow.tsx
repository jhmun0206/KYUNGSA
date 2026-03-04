"use client"

import Link from "next/link"
import { ChevronRight, MapPin } from "lucide-react"
import { GradeBadge } from "./GradeBadge"
import { CompareButton } from "./CompareButton"
import { FavoriteButton } from "./FavoriteButton"
import { formatPrice, calcDiscount, calcDday, getDdayColor, cn } from "@/lib/utils"
import { COURT_OPTIONS } from "@/lib/constants"
import type { AuctionListItem } from "@/lib/types"

export function AuctionListRow({ item }: { item: AuctionListItem }) {
  const failCount = Math.max(0, item.bid_count - 1)
  const discount = calcDiscount(item.minimum_bid, item.appraised_value)
  const dday = calcDday(item.auction_date)
  const ddayColor = getDdayColor(item.auction_date)
  const courtLabel =
    COURT_OPTIONS.find((c) => c.code === item.court_office_code)?.label ?? item.court
  const detailHref = `/auction/${encodeURIComponent(item.case_number)}`
  const mapHref = `https://map.kakao.com/link/search/${encodeURIComponent(item.address ?? "")}`

  return (
    <div className="group relative border-b border-border last:border-b-0 hover:bg-accent/30 transition-colors">
      {/* 모바일 전체 클릭 오버레이 */}
      <Link href={detailHref} className="absolute inset-0 sm:hidden" aria-label="상세 보기" />

      <div className="flex items-center gap-3 px-4 py-3">
        {/* 등급 */}
        <div className="shrink-0">
          <GradeBadge
            grade={item.grade}
            provisional={item.grade_provisional}
            size="sm"
          />
        </div>

        {/* 메인 정보 영역 */}
        <div className="flex-1 min-w-0">
          {/* 주소 + 카카오맵 링크 */}
          <div className="flex items-start gap-1">
            <Link
              href={detailHref}
              className="hidden sm:block text-sm font-medium text-foreground hover:text-primary truncate leading-snug"
            >
              {item.address}
            </Link>
            <span className="sm:hidden text-sm font-medium text-foreground truncate leading-snug">
              {item.address}
            </span>
            <a
              href={mapHref}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-muted-foreground hover:text-primary mt-0.5"
              onClick={(e) => e.stopPropagation()}
            >
              <MapPin size={12} />
            </a>
          </div>

          {/* 물건종류 · 법원 */}
          <p className="text-xs text-muted-foreground mt-0.5">
            {item.property_type} · {courtLabel}
          </p>

          {/* 모바일: 가격/할인율/유찰 행 */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 sm:hidden">
            <span className="text-xs text-muted-foreground">
              감정가 {formatPrice(item.appraised_value)}
            </span>
            <span className="text-xs font-medium text-foreground">
              최저 {formatPrice(item.minimum_bid)}
            </span>
            {discount != null && (
              <span className="rounded px-1 text-[10px] bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200">
                {Math.round(discount * 100)}%↓
              </span>
            )}
            {failCount > 0 && (
              <span className="text-[10px] text-muted-foreground">{failCount}회유찰</span>
            )}
          </div>

          {/* 모바일: 점수/기일 행 */}
          <div className="flex items-center gap-2 mt-1 sm:hidden">
            {item.total_score != null ? (
              <span className="text-xs text-muted-foreground">
                종합{" "}
                <span className="font-medium text-foreground">
                  {item.total_score.toFixed(0)}점
                </span>
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">-점</span>
            )}
            <span className={cn("text-xs", ddayColor)}>{dday}</span>
          </div>
        </div>

        {/* 데스크탑: 컬럼 값들 */}
        <div className="hidden sm:flex items-center gap-6 shrink-0">
          {/* 감정가 */}
          <div className="w-20 text-right">
            <p className="text-xs text-muted-foreground">{formatPrice(item.appraised_value)}</p>
          </div>
          {/* 최저가 + 할인율 */}
          <div className="w-24 text-right">
            <p className="text-sm font-medium">{formatPrice(item.minimum_bid)}</p>
            {discount != null && (
              <span className="text-[10px] rounded px-1 bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200">
                {Math.round(discount * 100)}%↓
              </span>
            )}
          </div>
          {/* 기일 + D-day */}
          <div className="w-16 text-right">
            <p className={cn("text-xs", ddayColor)}>{dday}</p>
            <p className="text-[10px] text-muted-foreground">
              {item.auction_date?.replace(/-/g, ".")}
            </p>
          </div>
          {/* 유찰 */}
          <div className="w-10 text-right">
            <p className="text-xs text-muted-foreground">
              {failCount > 0 ? `${failCount}회` : "신건"}
            </p>
          </div>
          {/* 종합점수 */}
          <div className="w-12 text-right">
            <p className="text-sm font-semibold tabular-nums">
              {item.total_score != null ? `${item.total_score.toFixed(0)}점` : "-"}
            </p>
          </div>
        </div>

        {/* 액션 버튼 */}
        <div
          className="flex items-center gap-1 shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          <FavoriteButton caseNumber={item.case_number} />
          <CompareButton caseNumber={item.case_number} />
        </div>

        {/* 모바일 ChevronRight */}
        <ChevronRight size={16} className="text-muted-foreground shrink-0 sm:hidden" />
      </div>
    </div>
  )
}
