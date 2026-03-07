"use client"

import { useState, useMemo, useEffect } from "react"
import { ChevronDown, AlertTriangle, Info } from "lucide-react"
import { cn, formatPrice } from "@/lib/utils"
import {
  isResidential,
  calcAcquisitionTax,
  calcLoanAmount,
  calcMonthlyInterest,
  calcTotalCost,
  calcRequiredEquity,
  calcMonthlyNet,
  calcYieldOnPrice,
  calcYieldOnEquity,
  manToWon,
} from "@/lib/investment"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

export function InvestmentCalculator({ auction }: Props) {
  const [open, setOpen] = useState(false)

  const minBid = auction.minimum_bid ?? 0
  const appraised = auction.appraised_value ?? 0

  // 입찰가
  const [bidPrice, setBidPrice] = useState(minBid)

  // 법무사비 (만원)
  const [lawyerFeeMan, setLawyerFeeMan] = useState(300)

  // 대출비율
  const residential = isResidential(auction.property_type)
  const [loanRatio, setLoanRatio] = useState(residential ? 0.8 : 0.6)

  // 대출 금리
  const [interestRate, setInterestRate] = useState(0.045)

  // 임대수익 (만원)
  const rentInfo = auction.rent_price_info
  const [monthlyRentMan, setMonthlyRentMan] = useState(
    rentInfo?.avg_monthly_rent ? Math.round(rentInfo.avg_monthly_rent) : 0
  )
  const [depositMan, setDepositMan] = useState(
    rentInfo?.avg_deposit ? Math.round(rentInfo.avg_deposit) : 0
  )
  const [monthlyExpenseMan, setMonthlyExpenseMan] = useState(0)

  // rent_price_info 업데이트 시 자동 채움
  useEffect(() => {
    if (rentInfo?.avg_monthly_rent) {
      setMonthlyRentMan(Math.round(rentInfo.avg_monthly_rent))
    }
    if (rentInfo?.avg_deposit) {
      setDepositMan(Math.round(rentInfo.avg_deposit))
    }
  }, [rentInfo?.avg_monthly_rent, rentInfo?.avg_deposit])

  // ML 추정 낙찰가
  const predictedRatio =
    auction.ml_prediction?.predicted_ratio ??
    auction.score?.predicted_winning_ratio
  const mlEstimate = predictedRatio != null ? Math.round(appraised * predictedRatio) : null

  // 계산
  const calc = useMemo(() => {
    const acquisitionTax = calcAcquisitionTax(bidPrice, auction.property_type)
    const lawyerFee = manToWon(lawyerFeeMan)
    const totalCost = calcTotalCost(bidPrice, acquisitionTax, lawyerFee)
    const loanAmount = calcLoanAmount(bidPrice, loanRatio)
    const monthlyInterest = calcMonthlyInterest(loanAmount, interestRate)
    const requiredEquity = calcRequiredEquity(totalCost, loanAmount)

    const monthlyRent = manToWon(monthlyRentMan)
    const monthlyExpense = manToWon(monthlyExpenseMan)
    const monthlyNet = calcMonthlyNet(monthlyRent, monthlyExpense, monthlyInterest)
    const annualNet = monthlyNet * 12

    const yieldOnPrice = calcYieldOnPrice(annualNet, bidPrice)
    const yieldOnEquity = calcYieldOnEquity(annualNet, requiredEquity)

    const depositWon = manToWon(depositMan)
    const actualEquity = requiredEquity - depositWon
    const yieldOnActualEquity =
      actualEquity > 0 ? (annualNet / actualEquity) * 100 : 0

    return {
      acquisitionTax,
      lawyerFee,
      totalCost,
      loanAmount,
      monthlyInterest,
      requiredEquity,
      monthlyNet,
      annualNet,
      yieldOnPrice,
      yieldOnEquity,
      actualEquity,
      yieldOnActualEquity,
    }
  }, [
    bidPrice,
    auction.property_type,
    lawyerFeeMan,
    loanRatio,
    interestRate,
    monthlyRentMan,
    monthlyExpenseMan,
    depositMan,
  ])

  // 감정가 대비 비율
  const bidRatio = appraised > 0 ? ((bidPrice / appraised) * 100).toFixed(0) : "-"

  // 슬라이더에서 ML 추정 위치 (%)
  const mlPct =
    mlEstimate != null && appraised > minBid
      ? ((mlEstimate - minBid) / (appraised - minBid)) * 100
      : null

  if (minBid <= 0 || appraised <= 0) return null

  return (
    <section id="investment" className="space-y-2">
      {/* 접기/펼치기 헤더 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h2 className="text-base font-bold text-foreground">
          투자 분석 시뮬레이터
        </h2>
        <ChevronDown
          size={16}
          className={cn(
            "text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
        />
      </button>
      <p className="text-xs text-muted-foreground">
        이 시뮬레이션은 참고용이며, 실제와 다를 수 있습니다
      </p>

      {open && (
        <div className="space-y-4 pt-2">
          {/* 건축물대장 기본 정보 */}
          {auction.building_info && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/30 px-4 py-2.5 text-xs text-muted-foreground">
              {auction.building_info.main_purpose && (
                <span>{auction.building_info.main_purpose}</span>
              )}
              {auction.building_info.exclusive_area_m2 != null && (
                <span>전용 {auction.building_info.exclusive_area_m2.toFixed(1)}㎡</span>
              )}
              {auction.building_info.total_area != null && auction.building_info.exclusive_area_m2 == null && (
                <span>연면적 {auction.building_info.total_area.toFixed(1)}㎡</span>
              )}
              {auction.building_info.ground_floors != null && (
                <span>지상 {auction.building_info.ground_floors}층</span>
              )}
              {auction.building_info.build_year != null && (
                <span>{auction.building_info.build_year}년</span>
              )}
              {auction.building_info.units_count != null && auction.building_info.units_count > 0 && (
                <span>{auction.building_info.units_count}세대</span>
              )}
            </div>
          )}

          {/* 입찰가 슬라이더 */}
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <p className="text-sm font-semibold text-card-foreground">
              낙찰 희망가 설정
            </p>

            <div className="relative">
              <input
                type="range"
                min={minBid}
                max={appraised}
                step={10000}
                value={bidPrice}
                onChange={(e) => setBidPrice(Number(e.target.value))}
                className="w-full accent-primary"
              />
              {/* ML 추정 마커 */}
              {mlPct != null && mlPct >= 0 && mlPct <= 100 && (
                <div
                  className="absolute top-0 -translate-x-1/2 pointer-events-none"
                  style={{ left: `${mlPct}%` }}
                >
                  <div className="w-0.5 h-4 bg-amber-500 mx-auto" />
                  <span className="text-[9px] text-amber-600 dark:text-amber-400 whitespace-nowrap">
                    모델 추정
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-foreground tabular-nums">
                  {formatPrice(bidPrice)}
                </span>
                <span className="text-xs text-muted-foreground">원</span>
              </div>
              <span className="text-xs text-muted-foreground">
                감정가 대비 {bidRatio}%
                {predictedRatio != null && (
                  <span className="ml-1 text-amber-600 dark:text-amber-400">
                    (모델 추정: {(predictedRatio * 100).toFixed(1)}%)
                  </span>
                )}
              </span>
            </div>

            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>최저가 {formatPrice(minBid)}</span>
              <span>감정가 {formatPrice(appraised)}</span>
            </div>
          </div>

          {/* 3칸 그리드: 매입비용 | 대출분석 | 수익률 */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {/* 매입 비용 */}
            <div className="rounded-lg border border-border bg-card p-4 space-y-2">
              <p className="text-sm font-semibold text-card-foreground">
                매입 비용
              </p>
              <InfoRow label="낙찰가" value={formatPrice(bidPrice)} />
              <InfoRow label="취등록세" value={formatPrice(calc.acquisitionTax)} />
              <EditableRow
                label="법무사비"
                value={lawyerFeeMan}
                onChange={setLawyerFeeMan}
                suffix="만원"
              />
              <div className="border-t border-border pt-1.5">
                <InfoRow
                  label="총 매입가"
                  value={formatPrice(calc.totalCost)}
                  bold
                />
              </div>
              <InfoRow
                label="필요자금"
                value={formatPrice(calc.requiredEquity)}
                sub
              />
            </div>

            {/* 대출 분석 */}
            <div className="rounded-lg border border-border bg-card p-4 space-y-2">
              <p className="text-sm font-semibold text-card-foreground">
                대출 분석
              </p>
              <InfoRow
                label="대출가능"
                value={formatPrice(calc.loanAmount)}
              />
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">대출비율</span>
                <select
                  value={String(loanRatio)}
                  onChange={(e) => setLoanRatio(Number(e.target.value))}
                  className="rounded border border-border bg-background px-1.5 py-0.5 text-xs text-foreground"
                >
                  <option value="0.5">50%</option>
                  <option value="0.6">60%</option>
                  <option value="0.7">70%</option>
                  <option value="0.8">80%</option>
                </select>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">대출 금리</span>
                <select
                  value={String(interestRate)}
                  onChange={(e) => setInterestRate(Number(e.target.value))}
                  className="rounded border border-border bg-background px-1.5 py-0.5 text-xs text-foreground"
                >
                  <option value="0.03">3.0%</option>
                  <option value="0.035">3.5%</option>
                  <option value="0.04">4.0%</option>
                  <option value="0.045">4.5%</option>
                  <option value="0.05">5.0%</option>
                  <option value="0.055">5.5%</option>
                  <option value="0.06">6.0%</option>
                </select>
              </div>
              <div className="border-t border-border pt-1.5">
                <InfoRow
                  label="월 이자"
                  value={formatPrice(calc.monthlyInterest)}
                  bold
                />
              </div>
            </div>

            {/* 수익률 */}
            <div className="rounded-lg border border-border bg-card p-4 space-y-2">
              <p className="text-sm font-semibold text-card-foreground">
                수익률
              </p>
              {monthlyRentMan > 0 ? (
                <>
                  <InfoRow
                    label="월 순수익"
                    value={formatPrice(calc.monthlyNet)}
                    color={
                      calc.monthlyNet >= 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-red-500"
                    }
                  />
                  <InfoRow
                    label="연수익률"
                    value={`${calc.yieldOnPrice.toFixed(1)}%`}
                  />
                  <InfoRow
                    label="에퀴티 수익률"
                    value={`${calc.yieldOnEquity.toFixed(1)}%`}
                    bold
                  />
                  {depositMan > 0 && (
                    <InfoRow
                      label="실투자 수익률"
                      value={`${calc.yieldOnActualEquity.toFixed(1)}%`}
                      sub
                    />
                  )}
                </>
              ) : (
                <p className="text-xs text-muted-foreground py-4 text-center">
                  아래 월 임대수익을 입력하면
                  <br />
                  수익률이 자동 계산됩니다
                </p>
              )}
            </div>
          </div>

          {/* 임대수익 입력 */}
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-card-foreground">
                월 임대수익 (선택 입력)
              </p>
              {rentInfo && rentInfo.sample_count >= 3 && (
                <span
                  className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-blue-600 dark:bg-blue-950 dark:text-blue-400"
                  title={`최근 3개월 인근 ${rentInfo.sample_count}건 실거래 평균`}
                >
                  <Info size={10} />
                  실거래 평균 {rentInfo.sample_count}건
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <EditableRow
                label="월세 수입"
                value={monthlyRentMan}
                onChange={setMonthlyRentMan}
                suffix="만원"
              />
              <EditableRow
                label="보증금"
                value={depositMan}
                onChange={setDepositMan}
                suffix="만원"
              />
              <EditableRow
                label="월 관리비"
                value={monthlyExpenseMan}
                onChange={setMonthlyExpenseMan}
                suffix="만원"
              />
            </div>
            {rentInfo && rentInfo.sample_count >= 3 && (
              <p className="text-[10px] text-muted-foreground">
                ※ 인근 {rentInfo.avg_area_m2 ? `${rentInfo.avg_area_m2.toFixed(0)}㎡ 기준 ` : ""}실거래 평균 자동입력. 직접 수정 가능.
              </p>
            )}
          </div>

          {/* 면책 문구 */}
          <div className="flex items-start gap-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <p>
              참고용 시뮬레이션이며, 실제 세금·대출조건·공실률은 개인 상황에 따라
              다릅니다. 전문가 상담을 권장합니다.
            </p>
          </div>
        </div>
      )}
    </section>
  )
}

function InfoRow({
  label,
  value,
  bold = false,
  sub = false,
  color,
}: {
  label: string
  value: string
  bold?: boolean
  sub?: boolean
  color?: string
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          "tabular-nums",
          bold && "text-sm font-bold text-foreground",
          sub && "text-muted-foreground",
          !bold && !sub && !color && "font-medium text-foreground",
          color
        )}
      >
        {value}
      </span>
    </div>
  )
}

function EditableRow({
  label,
  value,
  onChange,
  suffix,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  suffix: string
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={value || ""}
          onChange={(e) => onChange(Number(e.target.value) || 0)}
          className="w-20 rounded border border-border bg-background px-2 py-0.5 text-right text-xs tabular-nums text-foreground"
        />
        <span className="text-muted-foreground">{suffix}</span>
      </div>
    </div>
  )
}
