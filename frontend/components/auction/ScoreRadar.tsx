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
import { Lock } from "lucide-react"
import type { ScoreDetail } from "@/lib/types"

interface Props {
  score: ScoreDetail
}

export function ScoreRadar({ score }: Props) {
  const legalLocked = score.legal_score == null

  const data = [
    {
      subject: legalLocked ? "🔒 권리분석" : "권리분석",
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
    {
      subject: "명도",
      value: score.occupancy_score ?? 0,
      fullMark: 100,
    },
  ]

  const hasData = data.some((d) => d.value > 0)

  if (!hasData) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        점수 데이터 없음
      </div>
    )
  }

  return (
    <div className="w-full">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data}>
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis
              dataKey="subject"
              tick={{ fontSize: 11, fill: "#6b7280" }}
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
      </div>
      {legalLocked && (
        <p className="text-center text-xs text-muted-foreground -mt-2">
          <Lock size={10} className="inline mr-0.5 -mt-0.5" />
          권리분석: 등기부 열람 필요
        </p>
      )}
    </div>
  )
}
