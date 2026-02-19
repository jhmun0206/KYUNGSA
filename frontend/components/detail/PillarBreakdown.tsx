"use client"

import { ScoreRadar } from "@/components/auction/ScoreRadar"
import { PriceComparison } from "@/components/auction/PriceComparison"
import type { AuctionDetailResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

interface Props {
  auction: AuctionDetailResponse
}

function ScoreBar({ value, label }: { value: number | null; label: string }) {
  const pct = value ?? 0
  const color =
    pct >= 70 ? "bg-primary" : pct >= 50 ? "bg-amber-400" : "bg-red-400"

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-semibold tabular-nums", value == null ? "text-muted-foreground" : "text-foreground")}>
          {value != null ? `${value.toFixed(0)}점` : "분석 대기"}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function PillarBreakdown({ auction }: Props) {
  const score = auction.score

  return (
    <section className="space-y-4">
      <h2 className="text-base font-bold text-foreground">상세 분석</h2>

      {/* 레이더 + 바 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-sm font-semibold text-card-foreground">리스크 분포</p>
          {score ? (
            <ScoreRadar score={score} />
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              점수 분석 대기
            </div>
          )}
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-4 text-sm font-semibold text-card-foreground">항목별 점수</p>
          {score ? (
            <div className="space-y-3">
              <ScoreBar value={score.legal_score} label="권리분석" />
              <ScoreBar value={score.price_score} label="수익성" />
              <ScoreBar value={score.location_score} label="입지" />
              <ScoreBar value={score.occupancy_score} label="명도" />
              <div className="mt-2 flex items-center justify-between border-t border-border pt-2">
                <span className="text-sm font-semibold text-foreground">종합</span>
                <span className="text-xl font-black tabular-nums text-primary">
                  {score.total_score?.toFixed(1) ?? "-"}
                </span>
              </div>
              {score.warnings.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {score.warnings.map((w, i) => (
                    <li key={i} className="text-xs text-amber-600 dark:text-amber-400">
                      · {w}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">점수 없음</p>
          )}
        </div>
      </div>

      {/* 가격 차트 */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-card-foreground">가격 비교</p>
          {score?.predicted_winning_ratio && (
            <span className="text-xs text-muted-foreground">
              모델 추정 낙찰가율:{" "}
              <span className="font-semibold text-foreground">
                {(score.predicted_winning_ratio * 100).toFixed(0)}%
              </span>{" "}
              (참고)
            </span>
          )}
        </div>
        <PriceComparison auction={auction} />
      </div>
    </section>
  )
}
