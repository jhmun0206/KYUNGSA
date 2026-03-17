import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { CompareButton } from "@/components/domain/CompareButton"
import { normalizePropertyType } from "@/lib/property-category"
import {
  SIGNAL_EMOJI,
  SIGNAL_LABEL,
  SIGNAL_TEXT_CLASS,
  calcOverallSignal,
  calcOccupancySignal,
  calcPriceSignal,
  calcLocationSignal,
} from "@/lib/risk-signals"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

export function DetailHeader({ auction }: Props) {
  const failCount = Math.max(0, auction.bid_count - 1)
  const normalizedType = normalizePropertyType(auction.property_type)

  // 전체 리스크 수준
  const signals = [
    calcOccupancySignal(auction),
    calcPriceSignal(auction),
    calcLocationSignal(auction),
  ]
  const overallSignal = calcOverallSignal(signals)

  return (
    <div className="space-y-3">
      {/* 신호등 + 물건유형 + 유찰 + 버튼 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xl leading-none">{SIGNAL_EMOJI[overallSignal]}</span>
          <div>
            <div className="text-[11px] text-slate-400 leading-none mb-0.5">리스크 수준</div>
            <div className={`text-sm font-semibold leading-none ${SIGNAL_TEXT_CLASS[overallSignal]}`}>
              {SIGNAL_LABEL[overallSignal]}
            </div>
          </div>
        </div>

        <div className="flex gap-1.5 flex-wrap">
          <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-medium">
            {normalizedType ?? auction.property_type ?? '미분류'}
          </span>
          {failCount > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300 text-xs font-medium">
              {failCount}회 유찰
            </span>
          )}
          {auction.status === '매각' && (
            <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
              매각완료
            </span>
          )}
        </div>

        {/* 관심/비교 — 오른쪽 정렬 */}
        <div className="ml-auto flex gap-1.5">
          <FavoriteButton caseNumber={auction.case_number} label="관심" />
          <CompareButton caseNumber={auction.case_number} label="비교" />
        </div>
      </div>

      {/* 주소 + 사건번호 */}
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-50 leading-snug">
          {auction.address}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {auction.court} · {auction.case_number}
        </p>
      </div>
    </div>
  )
}
