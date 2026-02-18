"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

function toUk(v: number | null): number | null {
  return v !== null ? Math.round(v / 10000) : null
}

function formatUk(v: number): string {
  if (v >= 10000) return `${(v / 10000).toFixed(1)}억`
  return `${v.toLocaleString()}만`
}

export function PriceComparison({ auction }: Props) {
  const appraised = toUk(auction.appraised_value)
  const minimum = toUk(auction.minimum_bid)

  // 실거래가
  let market: number | null = null
  if (auction.market_price_info) {
    const mp = auction.market_price_info
    const raw = mp.market_price || mp.avg_deal_amount || mp.recent_deal_amount
    if (raw) market = toUk(Number(raw))
  }

  // 예상 낙찰가
  let predicted: number | null = null
  if (auction.score?.predicted_winning_ratio && minimum !== null) {
    predicted = Math.round(minimum * auction.score.predicted_winning_ratio)
  }

  const bars = [
    { name: "감정가", value: appraised, color: "#6b7280" },
    { name: "실거래가", value: market, color: "#10b981" },
    { name: "최저입찰가", value: minimum, color: "#3b82f6" },
    { name: "예상낙찰가", value: predicted, color: "#f59e0b" },
  ].filter((b) => b.value !== null) as { name: string; value: number; color: string }[]

  if (bars.length === 0) {
    return <div className="text-sm text-gray-400">가격 정보 없음</div>
  }

  return (
    <div className="h-52 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bars} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis
            tickFormatter={formatUk}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
            width={55}
          />
          <Tooltip
            formatter={(v) => [v != null ? formatUk(Number(v)) : "-", "금액"]}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {bars.map((b, i) => (
              <Cell key={i} fill={b.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
