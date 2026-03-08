"use client"

import { useState, useMemo, useEffect, useRef } from "react"
import { ChevronDown, AlertTriangle, Info, Plus, Trash2, ExternalLink } from "lucide-react"
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
import type { AuctionDetailResponse, RentAreaRange } from "@/lib/types"

interface RoomRow {
  id: string
  name: string
  area_m2: string      // string for controlled input
  deposit_man: number
  rent_man: number
}

function findRefRent(
  areaStr: string,
  ranges: RentAreaRange[]
): { avgRent: number; avgDeposit: number; count: number } | null {
  const area = parseFloat(areaStr)
  if (!area || !ranges.length) return null
  const match = ranges.find(r => area >= r.min_m2 && area < r.max_m2)
  return match ? { avgRent: match.avg_rent, avgDeposit: match.avg_deposit, count: match.count } : null
}

interface Props {
  auction: AuctionDetailResponse
}

export function InvestmentCalculator({ auction }: Props) {
  const [open, setOpen] = useState(false)

  const minBid = auction.minimum_bid ?? 0
  const appraised = auction.appraised_value ?? 0
  const buildingInfo = auction.building_info
  const rentInfo = auction.rent_price_info
  const byAreaRange: RentAreaRange[] = rentInfo?.by_area_range ?? []

  // 호실 테이블 여부: building_info가 있으면 테이블 모드
  const showRoomTable = !!buildingInfo

  const unitsCount =
    typeof buildingInfo?.units_count === "number" ? buildingInfo.units_count : null
  const initialCount = Math.min(Math.max(unitsCount ?? 1, 1), 20)
  const idRef = useRef(initialCount)

  const [rooms, setRooms] = useState<RoomRow[]>(() =>
    Array.from({ length: initialCount }, (_, i) => ({
      id: `r${i}`,
      name: `${i + 1}호`,
      area_m2: "",
      deposit_man: 0,
      rent_man: 0,
    }))
  )

  // 단일 입력 fallback 상태 (building_info 없을 때)
  const [monthlyRentMan, setMonthlyRentMan] = useState(
    rentInfo?.overall_avg_rent ? Math.round(rentInfo.overall_avg_rent) : 0
  )
  const [depositMan, setDepositMan] = useState(
    rentInfo?.overall_avg_deposit ? Math.round(rentInfo.overall_avg_deposit) : 0
  )
  useEffect(() => {
    if (!showRoomTable) {
      if (rentInfo?.overall_avg_rent) setMonthlyRentMan(Math.round(rentInfo.overall_avg_rent))
      if (rentInfo?.overall_avg_deposit) setDepositMan(Math.round(rentInfo.overall_avg_deposit))
    }
  }, [showRoomTable, rentInfo?.overall_avg_rent, rentInfo?.overall_avg_deposit])

  // 입찰가
  const [bidPrice, setBidPrice] = useState(minBid)

  // 법무사비 (만원)
  const [lawyerFeeMan, setLawyerFeeMan] = useState(300)

  // 대출비율
  const residential = isResidential(auction.property_type)
  const [loanRatio, setLoanRatio] = useState(residential ? 0.8 : 0.6)

  // 대출 금리 (서버 설정값 우선, 없으면 4.5%)
  const [interestRate, setInterestRate] = useState(auction.default_loan_rate ?? 0.045)

  // 월 관리비 (공통)
  const [monthlyExpenseMan, setMonthlyExpenseMan] = useState(0)

  // 합산 (테이블 vs 단일 입력)
  const totalRentMan = showRoomTable
    ? rooms.reduce((s, r) => s + r.rent_man, 0)
    : monthlyRentMan
  const totalDepositMan = showRoomTable
    ? rooms.reduce((s, r) => s + r.deposit_man, 0)
    : depositMan

  // ML 추정 낙찰가
  const predictedRatio =
    auction.ml_prediction?.predicted_ratio ?? auction.score?.predicted_winning_ratio
  const mlEstimate =
    predictedRatio != null ? Math.round(appraised * predictedRatio) : null

  // 계산
  const calc = useMemo(() => {
    const acquisitionTax = calcAcquisitionTax(bidPrice, auction.property_type)
    const lawyerFee = manToWon(lawyerFeeMan)
    const totalCost = calcTotalCost(bidPrice, acquisitionTax, lawyerFee)
    const loanAmount = calcLoanAmount(bidPrice, loanRatio)
    const monthlyInterest = calcMonthlyInterest(loanAmount, interestRate)
    const requiredEquity = calcRequiredEquity(totalCost, loanAmount)

    const monthlyRent = manToWon(totalRentMan)
    const monthlyExpense = manToWon(monthlyExpenseMan)
    const monthlyNet = calcMonthlyNet(monthlyRent, monthlyExpense, monthlyInterest)
    const annualNet = monthlyNet * 12

    const yieldOnPrice = calcYieldOnPrice(annualNet, bidPrice)
    const yieldOnEquity = calcYieldOnEquity(annualNet, requiredEquity)

    const depositWon = manToWon(totalDepositMan)
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
    totalRentMan,
    monthlyExpenseMan,
    totalDepositMan,
  ])

  // 감정가 대비 비율
  const bidRatio = appraised > 0 ? ((bidPrice / appraised) * 100).toFixed(0) : "-"

  // 슬라이더에서 ML 추정 위치 (%)
  const mlPct =
    mlEstimate != null && appraised > minBid
      ? ((mlEstimate - minBid) / (appraised - minBid)) * 100
      : null

  // 외부 링크 (좌표 기반)
  const lat = auction.lat
  const lng = auction.lng
  const dabangUrl =
    lat && lng
      ? `https://www.dabangapp.com/map/onetwo?lat=${lat}&lng=${lng}&zoom=15`
      : null
  const naverUrl =
    lat && lng
      ? `https://land.naver.com/article/articleList.nhn?rletTypeCd=SG&tradeTypeCd=B2&lat=${lat}&lng=${lng}`
      : null

  // Room 핼퍼
  function updateRoom(id: string, field: keyof RoomRow, value: string | number) {
    setRooms(prev => prev.map(r => (r.id === id ? { ...r, [field]: value } : r)))
  }

  function addRoom() {
    idRef.current++
    setRooms(prev => [
      ...prev,
      {
        id: `r${idRef.current}`,
        name: `${prev.length + 1}호`,
        area_m2: "",
        deposit_man: 0,
        rent_man: 0,
      },
    ])
  }

  function removeRoom(id: string) {
    setRooms(prev => prev.filter(r => r.id !== id))
  }

  if (minBid <= 0 || appraised <= 0) return null

  return (
    <section id="investment" className="space-y-2">
      {/* 접기/펼치기 헤더 */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h2 className="text-base font-bold text-foreground">투자 분석 시뮬레이터</h2>
        <ChevronDown
          size={16}
          className={cn("text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>
      <p className="text-xs text-muted-foreground">
        이 시뮬레이션은 참고용이며, 실제와 다를 수 있습니다
      </p>

      {open && (
        <div className="space-y-4 pt-2">
          {/* 건축물대장 기본 정보 */}
          {buildingInfo && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/30 px-4 py-2.5 text-xs text-muted-foreground">
              {buildingInfo.main_purpose && <span>{buildingInfo.main_purpose}</span>}
              {buildingInfo.exclusive_area_m2 != null && (
                <span>전용 {buildingInfo.exclusive_area_m2.toFixed(1)}㎡</span>
              )}
              {buildingInfo.total_area != null && buildingInfo.exclusive_area_m2 == null && (
                <span>연면적 {buildingInfo.total_area.toFixed(1)}㎡</span>
              )}
              {buildingInfo.ground_floors != null && (
                <span>지상 {buildingInfo.ground_floors}층</span>
              )}
              {buildingInfo.build_year != null && (
                <span>{buildingInfo.build_year}년</span>
              )}
              {buildingInfo.units_count != null && buildingInfo.units_count > 0 && (
                <span>{buildingInfo.units_count}세대</span>
              )}
            </div>
          )}

          {/* 입찰가 슬라이더 */}
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <p className="text-sm font-semibold text-card-foreground">낙찰 희망가 설정</p>
            <div className="relative">
              <input
                type="range"
                min={minBid}
                max={appraised}
                step={10000}
                value={bidPrice}
                onChange={e => setBidPrice(Number(e.target.value))}
                className="w-full accent-primary"
              />
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
              <p className="text-sm font-semibold text-card-foreground">매입 비용</p>
              <InfoRow label="낙찰가" value={formatPrice(bidPrice)} />
              <InfoRow label="취등록세" value={formatPrice(calc.acquisitionTax)} />
              <EditableRow
                label="법무사비"
                value={lawyerFeeMan}
                onChange={setLawyerFeeMan}
                suffix="만원"
              />
              <div className="border-t border-border pt-1.5">
                <InfoRow label="총 매입가" value={formatPrice(calc.totalCost)} bold />
              </div>
              <InfoRow label="필요자금" value={formatPrice(calc.requiredEquity)} sub />
            </div>

            {/* 대출 분석 */}
            <div className="rounded-lg border border-border bg-card p-4 space-y-2">
              <p className="text-sm font-semibold text-card-foreground">대출 분석</p>
              <InfoRow label="대출가능" value={formatPrice(calc.loanAmount)} />
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">대출비율</span>
                <select
                  value={String(loanRatio)}
                  onChange={e => setLoanRatio(Number(e.target.value))}
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
                  onChange={e => setInterestRate(Number(e.target.value))}
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
                <InfoRow label="월 이자" value={formatPrice(calc.monthlyInterest)} bold />
              </div>
            </div>

            {/* 수익률 */}
            <div className="rounded-lg border border-border bg-card p-4 space-y-2">
              <p className="text-sm font-semibold text-card-foreground">수익률</p>
              {totalRentMan > 0 ? (
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
                  <InfoRow label="연수익률" value={`${calc.yieldOnPrice.toFixed(1)}%`} />
                  <InfoRow
                    label="에퀴티 수익률"
                    value={`${calc.yieldOnEquity.toFixed(1)}%`}
                    bold
                  />
                  {totalDepositMan > 0 && (
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
          {showRoomTable ? (
            <RoomTable
              rooms={rooms}
              byAreaRange={byAreaRange}
              rentInfo={rentInfo}
              onUpdateRoom={updateRoom}
              onAddRoom={addRoom}
              onRemoveRoom={removeRoom}
              monthlyExpenseMan={monthlyExpenseMan}
              setMonthlyExpenseMan={setMonthlyExpenseMan}
            />
          ) : (
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
                    실거래 {rentInfo.sample_count}건
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
                  ※ 인근 {rentInfo.source} 실거래 평균 자동입력. 직접 수정 가능.
                </p>
              )}
            </div>
          )}

          {/* 인근 시세 외부 링크 */}
          {(dabangUrl || naverUrl) && (
            <div className="rounded-lg border border-border bg-card px-4 py-3 space-y-2">
              <p className="text-xs font-medium text-card-foreground">인근 임대 시세 확인</p>
              <div className="flex flex-wrap gap-2">
                {dabangUrl && (
                  <a
                    href={dabangUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-accent transition-colors"
                  >
                    다방에서 시세 확인
                    <ExternalLink size={10} />
                  </a>
                )}
                {naverUrl && (
                  <a
                    href={naverUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:bg-accent transition-colors"
                  >
                    네이버 부동산
                    <ExternalLink size={10} />
                  </a>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground">
                실제 시세는 현지 중개사무소 확인을 권장합니다
              </p>
            </div>
          )}

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

// ── 호실별 임대수익 테이블 ────────────────────────────────────────

function RoomTable({
  rooms,
  byAreaRange,
  rentInfo,
  onUpdateRoom,
  onAddRoom,
  onRemoveRoom,
  monthlyExpenseMan,
  setMonthlyExpenseMan,
}: {
  rooms: RoomRow[]
  byAreaRange: RentAreaRange[]
  rentInfo: AuctionDetailResponse["rent_price_info"]
  onUpdateRoom: (id: string, field: keyof RoomRow, value: string | number) => void
  onAddRoom: () => void
  onRemoveRoom: (id: string) => void
  monthlyExpenseMan: number
  setMonthlyExpenseMan: (v: number) => void
}) {
  const hasRentInfo = byAreaRange.length > 0
  const totalRent = rooms.reduce((s, r) => s + r.rent_man, 0)
  const totalDeposit = rooms.reduce((s, r) => s + r.deposit_man, 0)

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-card-foreground">호실별 월 임대수익</p>
        {rentInfo && rentInfo.sample_count >= 3 && (
          <span
            className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-blue-600 dark:bg-blue-950 dark:text-blue-400"
            title={`최근 3개월 인근 ${rentInfo.sample_count}건 실거래 기반`}
          >
            <Info size={10} />
            실거래 {rentInfo.sample_count}건
          </span>
        )}
      </div>

      {/* 테이블 */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="pb-1.5 text-left font-medium w-14">호실</th>
              <th className="pb-1.5 text-right font-medium w-16">면적(㎡)</th>
              {hasRentInfo && (
                <th className="pb-1.5 text-right font-medium w-20">참고월세</th>
              )}
              <th className="pb-1.5 text-right font-medium w-20">보증금(만)</th>
              <th className="pb-1.5 text-right font-medium w-20">월세(만)</th>
              <th className="pb-1.5 w-6" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {rooms.map(row => {
              const ref = findRefRent(row.area_m2, byAreaRange)
              return (
                <tr key={row.id}>
                  <td className="py-1.5 pr-2">
                    <input
                      value={row.name}
                      onChange={e => onUpdateRoom(row.id, "name", e.target.value)}
                      className="w-12 rounded border border-border bg-background px-1.5 py-0.5 text-xs text-foreground"
                    />
                  </td>
                  <td className="py-1.5 px-1 text-right">
                    <input
                      type="number"
                      value={row.area_m2 || ""}
                      onChange={e => onUpdateRoom(row.id, "area_m2", e.target.value)}
                      placeholder="면적"
                      className="w-14 rounded border border-border bg-background px-1 py-0.5 text-right text-xs tabular-nums text-foreground"
                    />
                  </td>
                  {hasRentInfo && (
                    <td className="py-1.5 px-1 text-right">
                      {ref ? (
                        <span
                          className="text-blue-600 dark:text-blue-400 tabular-nums"
                          title={`실거래 ${ref.count}건 평균`}
                        >
                          {ref.avgRent.toFixed(0)}만*
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                  )}
                  <td className="py-1.5 px-1 text-right">
                    <input
                      type="number"
                      value={row.deposit_man || ""}
                      onChange={e =>
                        onUpdateRoom(row.id, "deposit_man", Number(e.target.value) || 0)
                      }
                      className="w-16 rounded border border-border bg-background px-1 py-0.5 text-right text-xs tabular-nums text-foreground"
                    />
                  </td>
                  <td className="py-1.5 px-1 text-right">
                    <input
                      type="number"
                      value={row.rent_man || ""}
                      onChange={e =>
                        onUpdateRoom(row.id, "rent_man", Number(e.target.value) || 0)
                      }
                      className="w-16 rounded border border-border bg-background px-1 py-0.5 text-right text-xs tabular-nums text-foreground"
                    />
                  </td>
                  <td className="py-1.5 pl-1 text-center">
                    <button
                      onClick={() => onRemoveRoom(row.id)}
                      className="text-muted-foreground hover:text-destructive transition-colors"
                    >
                      <Trash2 size={12} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="border-t border-border font-medium">
              <td
                colSpan={hasRentInfo ? 3 : 2}
                className="pt-1.5 text-muted-foreground"
              >
                합계 ({rooms.length}호실)
              </td>
              <td className="pt-1.5 text-right tabular-nums">
                {totalDeposit > 0 ? `${totalDeposit.toLocaleString()}만` : "-"}
              </td>
              <td className="pt-1.5 text-right tabular-nums text-foreground">
                {totalRent > 0 ? `${totalRent.toLocaleString()}만` : "-"}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      {/* 행 추가 + 월 관리비 */}
      <div className="flex items-center justify-between">
        <button
          onClick={onAddRoom}
          className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
        >
          <Plus size={12} />
          호실 추가
        </button>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">월 관리비</span>
          <input
            type="number"
            value={monthlyExpenseMan || ""}
            onChange={e => setMonthlyExpenseMan(Number(e.target.value) || 0)}
            className="w-16 rounded border border-border bg-background px-2 py-0.5 text-right text-xs tabular-nums text-foreground"
          />
          <span className="text-muted-foreground">만원</span>
        </div>
      </div>

      {/* 참고 면책 */}
      {hasRentInfo && rentInfo && (
        <p className="text-[10px] text-muted-foreground">
          * 참고 월세는 최근 3개월 인근 {rentInfo.source} 실거래 데이터 기반이며,
          실제 임대 조건과 다를 수 있습니다. 투자 판단은 현장 확인 후 결정하세요.
        </p>
      )}
    </div>
  )
}

// ── 공통 서브 컴포넌트 ────────────────────────────────────────────

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
          onChange={e => onChange(Number(e.target.value) || 0)}
          className="w-20 rounded border border-border bg-background px-2 py-0.5 text-right text-xs tabular-nums text-foreground"
        />
        <span className="text-muted-foreground">{suffix}</span>
      </div>
    </div>
  )
}
