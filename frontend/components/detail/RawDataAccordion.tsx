"use client"

import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { formatPrice } from "@/lib/utils"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-slate-400 dark:text-slate-500">{label}</dt>
      <dd className="text-sm font-medium text-slate-700 dark:text-slate-200">{value}</dd>
    </div>
  )
}

export function RawDataAccordion({ auction }: Props) {
  const [open, setOpen] = useState(false)
  const failCount = Math.max(0, auction.bid_count - 1)

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
          원본 데이터
        </span>
        <ChevronDown
          className={`h-4 w-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="px-4 py-4 space-y-5 bg-white dark:bg-slate-900">
          {/* 기본 정보 그리드 */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            <InfoRow label="사건번호" value={auction.case_number} />
            <InfoRow label="관할 법원" value={auction.court} />
            <InfoRow label="상태" value={auction.status} />
            <InfoRow label="감정가" value={formatPrice(auction.appraised_value)} />
            <InfoRow label="최저매각가격" value={formatPrice(auction.minimum_bid)} />
            <InfoRow label="매각기일" value={auction.auction_date?.replace(/-/g, '.') ?? null} />
            <InfoRow label="유찰횟수" value={failCount > 0 ? `${failCount}회` : '없음'} />
            <InfoRow label="물건 유형" value={auction.property_type} />
            {auction.winning_bid && (
              <>
                <InfoRow label="낙찰가" value={formatPrice(auction.winning_bid)} />
                <InfoRow
                  label="낙찰가율"
                  value={auction.winning_ratio
                    ? `${(auction.winning_ratio * 100).toFixed(1)}%`
                    : null}
                />
                <InfoRow label="낙찰일" value={auction.winning_date?.replace(/-/g, '.') ?? null} />
              </>
            )}
          </dl>

          {/* 특이사항 */}
          {auction.specification_remarks && (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-950/50 p-3 border border-amber-200 dark:border-amber-800">
              <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-1.5">
                특이사항 (매각물건명세서)
              </p>
              <p className="text-sm text-amber-800 dark:text-amber-300 whitespace-pre-line leading-relaxed">
                {auction.specification_remarks}
              </p>
            </div>
          )}

          {/* 점수 요약 */}
          {auction.score && (
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wide">
                분석 점수
              </p>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
                <InfoRow
                  label="수익성"
                  value={auction.score.price_score != null ? `${Math.round(auction.score.price_score)}점` : null}
                />
                <InfoRow
                  label="입지"
                  value={auction.score.location_score != null ? `${Math.round(auction.score.location_score)}점` : null}
                />
                <InfoRow
                  label="명도"
                  value={auction.score.occupancy_score != null ? `${Math.round(auction.score.occupancy_score)}점` : null}
                />
                <InfoRow
                  label="종합"
                  value={auction.score.total_score != null ? `${Math.round(auction.score.total_score)}점` : null}
                />
              </dl>
              {auction.score.warnings && auction.score.warnings.length > 0 && (
                <div className="mt-2 space-y-1">
                  {auction.score.warnings.slice(0, 5).map((w, i) => (
                    <p key={i} className="text-xs text-amber-700 dark:text-amber-400">• {w}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
