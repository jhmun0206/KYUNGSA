"use client"

import { useState } from "react"
import { ChevronDown, Lock } from "lucide-react"
import { ScoreRadar } from "@/components/auction/ScoreRadar"
import { PriceComparison } from "@/components/auction/PriceComparison"
import type { AuctionDetailResponse } from "@/lib/types"
import { cn, getScoreInterpretation, calcDiscount } from "@/lib/utils"

interface Props {
  auction: AuctionDetailResponse
}

function ScoreBarWithBreakdown({
  value,
  label,
  children,
}: {
  value: number | null
  label: string
  children?: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const hasBreakdown = !!children
  const pct = value ?? 0
  const color =
    pct >= 70 ? "bg-primary" : pct >= 50 ? "bg-amber-400" : "bg-red-400"
  const interp = getScoreInterpretation(value)

  return (
    <div className="space-y-1">
      <button
        className="w-full text-left"
        onClick={() => hasBreakdown && setOpen((v) => !v)}
      >
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-1 text-muted-foreground">
            {label}
            {hasBreakdown && (
              <ChevronDown
                size={12}
                className={cn("transition-transform", open && "rotate-180")}
              />
            )}
          </span>
          <div className="flex items-center gap-2">
            <span className={cn("text-xs", interp.colorClass)}>{interp.text}</span>
            <span
              className={cn(
                "font-semibold tabular-nums",
                value == null ? "text-muted-foreground" : "text-foreground"
              )}
            >
              {value != null ? `${value.toFixed(0)}점` : "분석 대기"}
            </span>
          </div>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted mt-1">
          <div
            className={cn("h-full rounded-full transition-all", color)}
            style={{ width: `${pct}%` }}
          />
        </div>
      </button>
      {open && hasBreakdown && (
        <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground space-y-0.5">
          {children}
        </div>
      )}
    </div>
  )
}

/** 권리분석 잠금 상태 전용 UI */
function LegalLockedBar({ onCta }: { onCta: () => void }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-1 text-muted-foreground">
          <Lock size={12} />
          권리분석
        </span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
          잠금
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted" />
      <button
        onClick={onCta}
        className="text-xs text-primary hover:text-primary/80"
      >
        등기부등본 열람 시 자동 분석됩니다 →
      </button>
    </div>
  )
}

function fmtDist(m: number): string {
  return m < 1000 ? `${m}m` : `${(m / 1000).toFixed(1)}km`
}

export function PillarBreakdown({ auction }: Props) {
  const score = auction.score
  const [showLegalModal, setShowLegalModal] = useState(false)

  // 수익성 근거
  const discount = calcDiscount(auction.minimum_bid, auction.appraised_value)
  const failCount = Math.max(0, auction.bid_count - 1)
  const predictedRatio =
    auction.ml_prediction?.predicted_ratio ?? score?.predicted_winning_ratio

  // 입지 근거 (location_data — 현재 DB 미저장, 대부분 null)
  const locData = auction.location_data
  const stationM =
    typeof locData?.nearest_station_m === "number" ? locData.nearest_station_m : null
  const amenityCount =
    typeof locData?.amenity_count_500m === "number" ? locData.amenity_count_500m : null
  const schoolM =
    typeof locData?.nearest_school_m === "number" ? locData.nearest_school_m : null
  const hasLocationData = stationM != null || amenityCount != null || schoolM != null

  // 명도 근거
  const hasReport = !!auction.specification_remarks

  const legalLocked = score?.legal_score == null

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
              {/* 권리분석 — 잠금/정상 분기 */}
              {legalLocked ? (
                <LegalLockedBar onCta={() => setShowLegalModal(true)} />
              ) : (
                <ScoreBarWithBreakdown value={score.legal_score} label="권리분석">
                  <p>· 등기부 분석 완료</p>
                </ScoreBarWithBreakdown>
              )}

              {/* 수익성 */}
              <ScoreBarWithBreakdown value={score.price_score} label="수익성">
                {discount != null && <p>· 할인율: {Math.round(discount * 100)}%</p>}
                <p>· 유찰 횟수: {failCount}회</p>
                {predictedRatio != null && (
                  <p>· 추정 낙찰가율: {(predictedRatio * 100).toFixed(0)}%</p>
                )}
                <p className="text-[10px] mt-1 opacity-70">
                  자동 수집 데이터 기반, 실제와 다를 수 있습니다
                </p>
              </ScoreBarWithBreakdown>

              {/* 입지 — location_data 없으면 accordion 숨김 */}
              <ScoreBarWithBreakdown value={score.location_score} label="입지">
                {hasLocationData ? (
                  <>
                    {stationM != null && <p>· 지하철: {fmtDist(stationM)}</p>}
                    {amenityCount != null && (
                      <p>· 편의시설 500m 이내: {amenityCount}개</p>
                    )}
                    {schoolM != null && <p>· 학교: {fmtDist(schoolM)}</p>}
                    <p className="text-[10px] mt-1 opacity-70">
                      자동 수집 데이터 기반, 실제와 다를 수 있습니다
                    </p>
                  </>
                ) : undefined}
              </ScoreBarWithBreakdown>

              {/* 명도 */}
              <ScoreBarWithBreakdown value={score.occupancy_score} label="명도">
                <p>· 현황조사서: {hasReport ? "수집 완료" : "데이터 없음"}</p>
                <p className="text-[10px] mt-1 opacity-70">
                  자동 수집 데이터 기반, 실제와 다를 수 있습니다
                </p>
              </ScoreBarWithBreakdown>

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
            <div className="flex flex-col items-center justify-center gap-2 py-6">
              <p className="text-sm font-medium text-muted-foreground">점수 분석 대기</p>
              <p className="text-xs text-muted-foreground">
                데이터 수집 완료 후 자동으로 업데이트됩니다
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 등기부 열람 CTA */}
      {score && legalLocked && (
        <button
          onClick={() => setShowLegalModal(true)}
          className="w-full rounded-lg border-2 border-dashed border-primary/30 bg-primary/5 px-4 py-3 text-center hover:border-primary/50 hover:bg-primary/10 transition-colors"
        >
          <div className="flex items-center justify-center gap-2">
            <Lock size={16} className="text-primary" />
            <span className="text-sm font-medium text-primary">등기부 열람하기</span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            권리분석 점수가 자동으로 채워집니다
          </p>
        </button>
      )}

      {/* 가격 차트 */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-card-foreground">가격 비교</p>
          {(auction.ml_prediction?.predicted_ratio ?? score?.predicted_winning_ratio) != null && (
            <span className="text-xs text-muted-foreground">
              모델 추정 낙찰가율:{" "}
              <span className="font-semibold text-foreground">
                {(
                  (auction.ml_prediction?.predicted_ratio ??
                    score?.predicted_winning_ratio ??
                    0) * 100
                ).toFixed(0)}
                %
              </span>{" "}
              (참고)
              <span className="ml-1 text-[10px] text-muted-foreground">
                {auction.ml_prediction?.model_version === "ml_v1" ? "ML 모델" : "통계 기반"}
              </span>
            </span>
          )}
        </div>
        <PriceComparison auction={auction} />
      </div>

      {/* 등기부 열람 모달 */}
      {showLegalModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setShowLegalModal(false)}
        >
          <div
            className="mx-4 w-full max-w-sm rounded-xl bg-card p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Lock size={24} className="text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground">등기부 열람 서비스</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                등기부등본을 자동으로 열람하고
                <br />
                권리분석 점수를 산출합니다.
              </p>
              <div className="mt-4 rounded-lg bg-muted p-3">
                <p className="text-sm font-medium text-foreground">현재 준비 중입니다</p>
                <p className="text-xs text-muted-foreground mt-1">
                  서비스 출시 시 알림을 받으시겠습니까?
                </p>
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => setShowLegalModal(false)}
                  className="flex-1 rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-accent"
                >
                  닫기
                </button>
                <button
                  onClick={() => {
                    setShowLegalModal(false)
                  }}
                  className="flex-1 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
                >
                  알림 받기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
