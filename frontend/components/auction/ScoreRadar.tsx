"use client"

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import type { ScoreDetail } from "@/lib/types"

interface Props {
  score: ScoreDetail
}

export function ScoreRadar({ score }: Props) {
  const data = [
    {
      subject: "권리분석",
      value: score.legal_score ?? 0,
      fullMark: 100,
    },
    {
      subject: "수익성",
      value: score.price_score ?? 0,
      fullMark: 100,
    },
    {
      subject: "입지",
      value: score.location_score ?? 0,
      fullMark: 100,
    },
  ]

  const hasData = data.some((d) => d.value > 0)

  if (!hasData) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-gray-400">
        점수 데이터 없음
      </div>
    )
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fontSize: 12, fill: "#6b7280" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: "#9ca3af" }}
          />
          <Radar
            name="점수"
            dataKey="value"
            stroke="#2563eb"
            fill="#3b82f6"
            fillOpacity={0.25}
          />
          <Tooltip
            formatter={(v) => [v != null ? `${Number(v).toFixed(1)}점` : "-", "점수"]}
          />
        </RadarChart>
      </ResponsiveContainer>
      {score.occupancy_score === null && (
        <p className="text-center text-xs text-gray-400 -mt-2">
          명도 항목: 분석 대기
        </p>
      )}
    </div>
  )
}
