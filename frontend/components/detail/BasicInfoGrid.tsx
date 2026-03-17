import { formatPrice, calcDday, calcDiscount } from "@/lib/utils"
import { SkyviewMap } from "./SkyviewMap"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

function InfoCard({
  label,
  value,
  sub,
  subClass,
}: {
  label: string
  value: string
  sub?: string
  subClass?: string
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 p-4">
      <span className="text-xs text-slate-400 dark:text-slate-500">{label}</span>
      <span className="text-base font-bold tabular-nums text-slate-900 dark:text-slate-100">
        {value}
      </span>
      {sub && (
        <span className={`text-xs ${subClass ?? 'text-slate-400 dark:text-slate-500'}`}>
          {sub}
        </span>
      )}
    </div>
  )
}

function CoverageBar({ coverage }: { coverage: number | null | undefined }) {
  const pct = Math.round((coverage ?? 0) * 100)
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-400' : 'bg-slate-300'
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-500 dark:text-slate-400 shrink-0">데이터 완성도</span>
      <div className="flex-1 bg-slate-200 dark:bg-slate-700 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 w-8 text-right">
        {pct}%
      </span>
    </div>
  )
}

export function BasicInfoGrid({ auction }: Props) {
  const discount = calcDiscount(auction.minimum_bid, auction.appraised_value)
  const dday = calcDday(auction.auction_date)
  const failCount = Math.max(0, auction.bid_count - 1)

  const ddayClass =
    dday.startsWith('D-') && parseInt(dday.slice(2)) <= 3
      ? 'text-red-600 dark:text-red-400 font-semibold'
      : dday.startsWith('D+') || dday === '오늘'
      ? 'text-slate-400 dark:text-slate-500 line-through'
      : 'text-blue-600 dark:text-blue-400'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 왼쪽: 기본정보 */}
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <InfoCard
            label="감정가"
            value={formatPrice(auction.appraised_value)}
          />
          <InfoCard
            label="최저매각가격"
            value={formatPrice(auction.minimum_bid)}
            sub={discount != null ? `감정가 대비 ${Math.round(discount * 100)}% ↓` : undefined}
            subClass="text-blue-600 dark:text-blue-400"
          />
          <InfoCard
            label="매각기일"
            value={auction.auction_date?.replace(/-/g, '.') ?? '-'}
            sub={dday !== '-' ? dday : undefined}
            subClass={ddayClass}
          />
          <InfoCard
            label={auction.winning_bid ? '낙찰가' : '유찰횟수'}
            value={
              auction.winning_bid
                ? formatPrice(auction.winning_bid)
                : `${failCount}회`
            }
            sub={auction.winning_ratio
              ? `낙찰가율 ${(auction.winning_ratio * 100).toFixed(1)}%`
              : undefined}
            subClass="text-emerald-600 dark:text-emerald-400"
          />
        </div>

        {/* 유사사례 참고 범위 */}
        {auction.ml_prediction?.predicted_ratio != null && !auction.winning_bid && (
          <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-xs text-slate-500 dark:text-slate-400">유사사례 참고 범위</span>
              <span className="text-sm font-bold text-blue-600 dark:text-blue-400 tabular-nums">
                {(auction.ml_prediction.predicted_ratio * 100).toFixed(1)}%
              </span>
              {auction.ml_prediction.predicted_price != null && (
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  ≈ {formatPrice(auction.ml_prediction.predicted_price)}
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1">
              * 참고용 데이터입니다. 실제 낙찰가와 다를 수 있습니다.
            </p>
          </div>
        )}

        {/* 데이터 완성도 */}
        {auction.score && (
          <CoverageBar coverage={auction.score.score_coverage} />
        )}
      </div>

      {/* 오른쪽: 위치 */}
      <SkyviewMap lat={auction.lat} lng={auction.lng} address={auction.address} />
    </div>
  )
}
