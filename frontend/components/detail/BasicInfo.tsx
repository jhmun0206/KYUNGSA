import { formatPrice } from "@/lib/utils"
import type { AuctionDetailResponse } from "@/lib/types"
import { RoundTimeline } from "@/components/auction/RoundTimeline"

interface Props {
  auction: AuctionDetailResponse
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">{value}</dd>
    </div>
  )
}

export function BasicInfo({ auction }: Props) {
  const failCount = Math.max(0, auction.bid_count - 1)

  return (
    <section className="space-y-4">
      <h2 className="text-base font-bold text-foreground">원본 데이터</h2>

      {/* 기본 정보 그리드 */}
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-sm font-semibold text-card-foreground">기본 정보</p>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          <InfoRow label="매각기일" value={auction.auction_date?.replace(/-/g, ".") ?? "-"} />
          <InfoRow label="상태" value={auction.status || "-"} />
          <InfoRow label="감정가" value={formatPrice(auction.appraised_value)} />
          <InfoRow label="최저매각가격" value={formatPrice(auction.minimum_bid)} />
          <InfoRow
            label="낙찰가"
            value={
              auction.winning_bid
                ? `${formatPrice(auction.winning_bid)}${
                    auction.winning_ratio
                      ? ` (${(auction.winning_ratio * 100).toFixed(1)}%)`
                      : ""
                  }`
                : "-"
            }
          />
          <InfoRow label="낙찰일" value={auction.winning_date?.replace(/-/g, ".") ?? "-"} />
          <InfoRow label="유찰횟수" value={failCount > 0 ? `${failCount}회` : "없음"} />
          <InfoRow label="물건 유형" value={auction.property_type || "-"} />
          <InfoRow label="사건번호" value={auction.case_number} />
        </dl>

        {auction.specification_remarks && (
          <div className="mt-4 rounded-md bg-amber-50 p-3 dark:bg-amber-950">
            <p className="mb-1 text-xs font-semibold text-amber-700 dark:text-amber-400">
              특이사항 (매각물건명세서)
            </p>
            <p className="whitespace-pre-line text-sm text-amber-800 dark:text-amber-300">
              {auction.specification_remarks}
            </p>
          </div>
        )}
      </div>

      {/* 기일 내역 */}
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="mb-4 text-sm font-semibold text-card-foreground">기일 내역</p>
        <RoundTimeline rounds={auction.rounds} />
      </div>
    </section>
  )
}
