"use client"

import { useState } from "react"
import { GradeBadge } from "@/components/domain/GradeBadge"
import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"
import { PredictionPill } from "@/components/domain/PredictionPill"
import { CoveragePill } from "@/components/domain/CoveragePill"
import { CheckCircle2, Info, AlertTriangle, XCircle } from "lucide-react"
import { formatPrice, calcDiscount, calcDday } from "@/lib/utils"
import type { AuctionDetailResponse } from "@/lib/types"
import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

const GRADE_SUMMARIES: Record<string, { text: string; Icon: LucideIcon; bgClass: string }> = {
  A: {
    text: "주요 리스크 지표가 양호합니다",
    Icon: CheckCircle2,
    bgClass: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  },
  B: {
    text: "일부 확인이 필요한 항목이 있습니다",
    Icon: Info,
    bgClass: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  },
  C: {
    text: "주의가 필요한 항목이 다수 있습니다",
    Icon: AlertTriangle,
    bgClass: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  },
  D: {
    text: "상당한 리스크 요소가 확인됩니다",
    Icon: XCircle,
    bgClass: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  },
}

interface Props {
  auction: AuctionDetailResponse
}

export function DecisionSection({ auction }: Props) {
  const score = auction.score
  const failCount = Math.max(0, auction.bid_count - 1)
  const discount = calcDiscount(auction.minimum_bid, auction.appraised_value)
  const dday = calcDday(auction.auction_date)

  const [showGradeInfo, setShowGradeInfo] = useState(false)
  const [showMlInfo, setShowMlInfo] = useState(false)

  const predictedRatio =
    auction.ml_prediction?.predicted_ratio ?? score?.predicted_winning_ratio
  const isML = auction.ml_prediction?.predicted_ratio != null

  return (
    <section className="space-y-4">
      {/* 등급 + 주소 + 태그 */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {score?.grade && (
              <GradeBadge
                grade={score.grade}
                provisional={score.grade_provisional}
                size="lg"
              />
            )}
            {score?.grade && (
              <button
                onClick={() => setShowGradeInfo((v) => !v)}
                className="text-muted-foreground hover:text-foreground"
              >
                <Info size={14} />
              </button>
            )}
            <span className="rounded-full bg-secondary px-2.5 py-1 text-sm font-medium text-secondary-foreground">
              {auction.property_type}
            </span>
            {failCount > 0 && (
              <span className="rounded-full bg-orange-50 px-2.5 py-1 text-sm font-medium text-orange-600 ring-1 ring-orange-100 dark:bg-orange-950 dark:text-orange-400 dark:ring-orange-900">
                {failCount}회 유찰
              </span>
            )}
          </div>

          {/* 등급 설명 Tooltip */}
          {showGradeInfo && (
            <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground space-y-1">
              <p className="font-medium text-foreground">등급 기준</p>
              <p>· <span className="font-medium">A등급</span>: 종합 80점 이상 — 주요 리스크 지표 양호</p>
              <p>· <span className="font-medium">B등급</span>: 종합 60~79점 — 일부 확인 필요</p>
              <p>· <span className="font-medium">C등급</span>: 종합 40~59점 — 복합 리스크 존재</p>
              <p>· <span className="font-medium">D등급</span>: 종합 40점 미만 — 신중한 검토 필요</p>
              <p className="mt-1 opacity-70">* 커버리지 40% 미만은 잠정 등급 (분석 완료 시 변동 가능)</p>
            </div>
          )}

          <h1 className="text-xl font-bold leading-snug text-foreground sm:text-2xl">
            {auction.address}
          </h1>
          <p className="text-sm text-muted-foreground">
            {auction.court} · {auction.case_number}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <FavoriteButton caseNumber={auction.case_number} />
        </div>
      </div>

      {/* 등급 한 줄 요약 */}
      {score?.grade && GRADE_SUMMARIES[score.grade] && (() => {
        const summary = GRADE_SUMMARIES[score.grade]
        return (
          <div className={cn(
            "flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium",
            summary.bgClass
          )}>
            <summary.Icon className="h-4 w-4 shrink-0" />
            <span>{summary.text}</span>
          </div>
        )
      })()}

      {/* 가격 3종 + D-day */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <PriceCard label="감정가" value={formatPrice(auction.appraised_value)} />
        <PriceCard
          label="최저매각가격"
          value={formatPrice(auction.minimum_bid)}
          sub={
            discount != null
              ? `감정가 대비 ${Math.round(discount * 100)}% 할인`
              : undefined
          }
          subNeutral
        />
        <PriceCard
          label="매각기일"
          value={auction.auction_date?.replace(/-/g, ".") ?? "-"}
          sub={dday !== "-" ? dday : undefined}
          subNeutral={dday.startsWith("D+") || dday === "오늘"}
        />
        {auction.winning_bid ? (
          <PriceCard
            label="낙찰가"
            value={formatPrice(auction.winning_bid)}
            sub={
              auction.winning_ratio
                ? `낙찰가율 ${(auction.winning_ratio * 100).toFixed(1)}%`
                : undefined
            }
            subNeutral
          />
        ) : (
          <div className="flex flex-col gap-1 rounded-md bg-muted p-3">
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground">모델 추정 범위 (참고)</span>
              {predictedRatio != null && (
                <button
                  onClick={() => setShowMlInfo((v) => !v)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <Info size={12} />
                </button>
              )}
            </div>
            <PredictionPill
              mlPrediction={auction.ml_prediction}
              ratio={score?.predicted_winning_ratio}
              appraisedValue={auction.appraised_value}
            />
          </div>
        )}
      </div>

      {/* ML 근거 Tooltip */}
      {showMlInfo && predictedRatio != null && (
        <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground space-y-1">
          <p className="font-medium text-foreground">추정 근거</p>
          <p>· {isML ? "동일 지역/유형 낙찰 사례 기반 ML 모델" : "통계 기반 추정"}</p>
          {isML && auction.ml_prediction?.top_factors && auction.ml_prediction.top_factors.length > 0 && (
            <p>
              · 주요 변수:{" "}
              {auction.ml_prediction.top_factors.slice(0, 3).map((f) => f.feature).join(" · ")}
            </p>
          )}
          {discount != null && <p>· 할인율: {Math.round(discount * 100)}%</p>}
          <p>· 유찰 횟수: {failCount}회</p>
          {auction.property_type && <p>· 물건 유형: {auction.property_type}</p>}
          {isML && auction.ml_prediction?.confidence && (
            <p>· 신뢰도: {auction.ml_prediction.confidence === "high" ? "높음" : auction.ml_prediction.confidence === "medium" ? "보통" : "낮음"}</p>
          )}
          <p className="mt-1 opacity-70">* 모델 추정치이며, 실제 낙찰가와 다를 수 있습니다</p>
        </div>
      )}

      {/* 커버리지 */}
      {score && (
        <div className="flex flex-wrap items-center gap-3 rounded-md bg-muted px-3 py-2">
          <span className="text-xs text-muted-foreground">분석 커버리지</span>
          <CoveragePill coverage={score.score_coverage} variant="detail" />
          {score.grade_provisional && (
            <span className="text-xs text-amber-600 dark:text-amber-400">
              * 일부 항목 미분석으로 잠정 등급
            </span>
          )}
        </div>
      )}

      <DisclaimerBanner />
    </section>
  )
}

function PriceCard({
  label,
  value,
  sub,
  subNeutral = false,
}: {
  label: string
  value: string
  sub?: string
  subNeutral?: boolean
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md bg-muted p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-base font-bold tabular-nums text-foreground">{value}</span>
      {sub && (
        <span className={cn("text-xs", subNeutral ? "text-muted-foreground" : "text-muted-foreground")}>
          {sub}
        </span>
      )}
    </div>
  )
}
