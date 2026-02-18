import Link from "next/link"
import { GradeBadge } from "@/components/auction/GradeBadge"
import { FavoriteButton } from "@/components/common/FavoriteButton"
import type { AuctionListItem } from "@/lib/types"

function formatAmount(v: number | null): string {
  if (v === null) return "-"
  const uk = Math.round(v / 10000)
  if (uk >= 10000) {
    return `${(uk / 10000).toFixed(1)}억`
  }
  return `${uk.toLocaleString()}만`
}

function formatDate(d: string | null): string {
  if (!d) return "-"
  return d.replace(/-/g, ".")
}

interface Props {
  item: AuctionListItem
}

export function AuctionCard({ item }: Props) {
  const failCount = item.bid_count - 1

  return (
    <Link
      href={`/auction/${encodeURIComponent(item.case_number)}`}
      className="block rounded-xl border border-gray-200 bg-white p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <GradeBadge grade={item.grade} provisional={item.grade_provisional} />
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
            {item.property_type || "미분류"}
          </span>
          {failCount > 0 && (
            <span className="text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded">
              {failCount}회 유찰
            </span>
          )}
        </div>
        <FavoriteButton caseNumber={item.case_number} />
      </div>

      <p className="mt-2 text-sm font-medium text-gray-900 line-clamp-2">
        {item.address || "-"}
      </p>

      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
        <div>
          <span className="text-gray-400">감정가</span>{" "}
          <span className="font-semibold tabular-nums">{formatAmount(item.appraised_value)}</span>
        </div>
        <div>
          <span className="text-gray-400">최저가</span>{" "}
          <span className="font-semibold tabular-nums">{formatAmount(item.minimum_bid)}</span>
        </div>
        <div>
          <span className="text-gray-400">매각기일</span>{" "}
          <span className="font-medium">{formatDate(item.auction_date)}</span>
        </div>
        <div>
          <span className="text-gray-400">법원</span>{" "}
          <span className="font-medium">{item.court}</span>
        </div>
      </div>

      {item.total_score !== null && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>종합 점수</span>
            <span className="font-semibold text-gray-800">{item.total_score.toFixed(1)}</span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full"
              style={{ width: `${Math.min(item.total_score, 100)}%` }}
            />
          </div>
          {item.score_coverage !== null && item.score_coverage < 0.7 && (
            <p className="mt-1 text-xs text-amber-600">
              {Math.round(item.score_coverage * 100)}% 항목만 분석됨
            </p>
          )}
        </div>
      )}
    </Link>
  )
}
