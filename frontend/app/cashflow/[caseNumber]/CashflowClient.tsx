"use client"

import { useState } from "react"
import type { AuctionDetailResponse } from "@/lib/types"
import {
  calcCashflow,
  getDefaultLtv,
  getAcquisitionTaxRate,
  initUnits,
  type CashflowUnit,
} from "@/lib/cashflow"
import { BidSlider } from "@/components/cashflow/BidSlider"
import { CostSection } from "@/components/cashflow/CostSection"
import { LoanSection } from "@/components/cashflow/LoanSection"
import { UnitsTable } from "@/components/cashflow/UnitsTable"
import { SaleSection } from "@/components/cashflow/SaleSection"
import { ResultCard } from "@/components/cashflow/ResultCard"

interface Props {
  auction: AuctionDetailResponse
}

export default function CashflowClient({ auction }: Props) {
  const category = auction.property_category ?? null
  const minBid = Math.round((auction.minimum_bid ?? 0) / 10000)
  const appraisedVal = Math.round((auction.appraised_value ?? 0) / 10000)

  // 초기값
  const defaultLtv = getDefaultLtv(category)
  const defaultLoanRate = auction.default_loan_rate ?? 0.045

  const [bidPrice, setBidPrice] = useState(minBid > 0 ? minBid : Math.round(appraisedVal * 0.7))
  const [legalFee, setLegalFee] = useState(300)
  const [otherCosts, setOtherCosts] = useState(0)
  const [ltv, setLtv] = useState(defaultLtv)
  const [loanRate, setLoanRate] = useState(defaultLoanRate)
  const [units, setUnits] = useState<CashflowUnit[]>(() => initUnits(auction))
  const [salePrice, setSalePrice] = useState(0)

  const taxRate = getAcquisitionTaxRate(category, bidPrice)

  const result = calcCashflow({
    bidPrice,
    acquisitionTaxRate: taxRate,
    legalFee,
    otherCosts,
    ltv,
    loanRate,
    units,
    salePrice: salePrice > 0 ? salePrice : undefined,
  })

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      {/* 왼쪽: 입력 패널 */}
      <div className="flex-1 min-w-0 space-y-4">
        <BidSlider
          value={bidPrice}
          min={minBid > 0 ? minBid : 1000}
          max={appraisedVal > minBid ? appraisedVal : minBid + 50000}
          appraisedValue={appraisedVal > 0 ? appraisedVal : bidPrice}
          mlPrediction={auction.ml_prediction}
          onChange={setBidPrice}
        />
        <CostSection
          bidPrice={bidPrice}
          taxRate={taxRate}
          legalFee={legalFee}
          otherCosts={otherCosts}
          result={result}
          onLegalFeeChange={setLegalFee}
          onOtherCostsChange={setOtherCosts}
        />
        <LoanSection
          ltv={ltv}
          loanRate={loanRate}
          result={result}
          propertyCategory={category}
          onLtvChange={setLtv}
          onLoanRateChange={setLoanRate}
        />
        <UnitsTable
          units={units}
          address={auction.address}
          propertyCategory={category}
          onChange={setUnits}
        />
        <SaleSection
          salePrice={salePrice}
          result={result}
          onChange={setSalePrice}
        />
      </div>

      {/* 오른쪽: 결과 카드 (sticky) */}
      <div className="w-full lg:w-80 lg:shrink-0">
        <div className="lg:sticky lg:top-6">
          <ResultCard
            result={result}
            bidPrice={bidPrice}
            appraisedValue={appraisedVal > 0 ? appraisedVal : bidPrice}
          />
        </div>
      </div>
    </div>
  )
}
