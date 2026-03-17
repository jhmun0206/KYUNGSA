// 현금흐름 분석 — 계산 로직

import type { AuctionDetailResponse, RentPriceInfo } from "@/lib/types"

export interface CashflowUnit {
  label: string
  areaSqm: number | null
  deposit: number       // 보증금 (만원)
  monthlyRent: number   // 월세 (만원)
  isEstimated?: boolean // rent_price_info 기반 추정값 여부
}

export interface CashflowInput {
  bidPrice: number           // 낙찰 희망가 (만원)
  acquisitionTaxRate: number // 취득세율 (예: 0.046)
  legalFee: number           // 법무사비 (만원)
  otherCosts: number         // 기타비용 (만원)
  ltv: number                // 대출비율 (예: 0.80)
  loanRate: number           // 대출금리 (예: 0.045)
  units: CashflowUnit[]
  salePrice?: number         // 매도 희망가 (만원, 선택)
}

export interface CashflowResult {
  // 매입 비용
  bidPrice: number
  acquisitionTax: number
  legalFee: number
  otherCosts: number
  totalCost: number

  // 대출
  loanAmount: number
  monthlyInterest: number
  realLoan: number           // 실질대출 = 대출가능액 - 보증금합계

  // 임대
  totalDeposit: number
  totalMonthlyRent: number

  // 자금
  requiredEquity: number     // 필요 자금 = 총매입가 - 대출가능액
  netEquity: number          // 만실후 투자금 = 필요자금 - 보증금합계

  // 수익률
  annualRentIncome: number   // 연 임대수익 (월세-이자) × 12
  annualYield: number        // 연 임대수익률 % (총매입가 기준)
  equityYield: number        // 에퀴티 수익률 % (만실후 투자금 기준)

  // 매도 (선택)
  saleProfit?: number
  saleYield?: number
}

export function calcCashflow(input: CashflowInput): CashflowResult {
  const { bidPrice, acquisitionTaxRate, legalFee, otherCosts, ltv, loanRate, units, salePrice } = input

  // 매입 비용
  const acquisitionTax = Math.round(bidPrice * acquisitionTaxRate)
  const totalCost = bidPrice + acquisitionTax + legalFee + otherCosts

  // 대출
  const loanAmount = Math.round(bidPrice * ltv)
  const totalDeposit = units.reduce((s, u) => s + (u.deposit || 0), 0)
  const totalMonthlyRent = units.reduce((s, u) => s + (u.monthlyRent || 0), 0)
  const realLoan = Math.max(0, loanAmount - totalDeposit)
  const monthlyInterest = Math.round(realLoan * loanRate / 12)

  // 자금
  const requiredEquity = Math.max(0, totalCost - loanAmount)
  const netEquity = Math.max(0, requiredEquity - totalDeposit)

  // 수익률
  const annualRentIncome = (totalMonthlyRent - monthlyInterest) * 12
  const annualYield = totalCost > 0
    ? parseFloat((annualRentIncome / totalCost * 100).toFixed(2))
    : 0
  const equityYield = netEquity > 0
    ? parseFloat((annualRentIncome / netEquity * 100).toFixed(2))
    : 0

  // 매도
  let saleProfit: number | undefined
  let saleYield: number | undefined
  if (salePrice && salePrice > 0) {
    saleProfit = salePrice - totalCost
    saleYield = requiredEquity > 0
      ? parseFloat((saleProfit / requiredEquity * 100).toFixed(2))
      : 0
  }

  return {
    bidPrice, acquisitionTax, legalFee, otherCosts, totalCost,
    loanAmount, monthlyInterest, realLoan,
    totalDeposit, totalMonthlyRent,
    requiredEquity, netEquity,
    annualRentIncome, annualYield, equityYield,
    saleProfit, saleYield,
  }
}

/** 물건유형별 기본 LTV */
export function getDefaultLtv(propertyCategory: string | null | undefined): number {
  const map: Record<string, number> = {
    '상가/근린': 0.80, '근린1종': 0.80, '근린2종': 0.80,
    '오피스텔': 0.65,
    '아파트': 0.70,
    '다세대/빌라': 0.60, '단독/다가구': 0.60,
    '토지': 0.40,
  }
  return map[propertyCategory ?? ''] ?? 0.60
}

/** 취득세율 (물건유형 + 낙찰가 기준) */
export function getAcquisitionTaxRate(
  propertyCategory: string | null | undefined,
  bidPriceMan: number,  // 만원 단위
): number {
  const nonResidential = ['상가/근린', '근린1종', '근린2종', '오피스텔', '토지']
  if (nonResidential.includes(propertyCategory ?? '')) return 0.046

  // 주택 구간별 (1세대 1주택 기준)
  const won = bidPriceMan * 10000
  if (won <= 600_000_000) return 0.011
  if (won <= 900_000_000) return 0.022
  return 0.033
}

/** rent_price_info에서 면적 기반 참고 월세/보증금 찾기 */
export function findRefRent(
  rentPriceInfo: RentPriceInfo | null | undefined,
  areaSqm: number | null | undefined,
): { avgRent: number; avgDeposit: number; range: string } | null {
  if (!rentPriceInfo || !areaSqm) return null
  const ranges = rentPriceInfo.by_area_range ?? []
  const match = ranges.find(r => areaSqm >= r.min_m2 && areaSqm < r.max_m2)
  if (!match) return null
  return { avgRent: match.avg_rent, avgDeposit: match.avg_deposit, range: match.range }
}

/** 물건 상세 → CashflowUnit[] 초기화 */
export function initUnits(auction: AuctionDetailResponse): CashflowUnit[] {
  const category = auction.property_category
  const buildingType = auction.building_type
  const rentInfo = auction.rent_price_info
  const totalArea = auction.exclusive_area_m2_real ?? auction.building_info?.exclusive_area_m2 ?? null

  // 단일 유닛 유형 (아파트, 단독/다가구)
  const isSingle = category === '아파트' || category === '단독/다가구'
  if (isSingle) {
    const ref = findRefRent(rentInfo, totalArea)
    return [{
      label: '전체',
      areaSqm: totalArea,
      deposit: ref ? Math.round(ref.avgDeposit) : 0,
      monthlyRent: ref ? Math.round(ref.avgRent) : 0,
      isEstimated: !!ref,
    }]
  }

  // 집합건물 — 전유부 호실 목록 있으면 사용
  const unitItems = auction.building_info?.units
  if (buildingType === '집합' && unitItems && unitItems.length > 0) {
    return unitItems.map(u => {
      const ref = findRefRent(rentInfo, u.area_m2)
      return {
        label: u.ho || `${u.floor}층`,
        areaSqm: u.area_m2,
        deposit: ref ? Math.round(ref.avgDeposit) : 0,
        monthlyRent: ref ? Math.round(ref.avgRent) : 0,
        isEstimated: !!ref,
      }
    })
  }

  // 호실 목록 없으면 units_count 기반 빈 행 생성 (최대 20개)
  const count = Math.min(auction.building_info?.units_count ?? 1, 20)
  const estArea = totalArea && count > 0 ? Math.round(totalArea / count * 10) / 10 : null

  return Array.from({ length: count }, (_, i) => {
    const ref = findRefRent(rentInfo, estArea)
    return {
      label: `${i + 1}호`,
      areaSqm: estArea,
      deposit: ref ? Math.round(ref.avgDeposit) : 0,
      monthlyRent: ref ? Math.round(ref.avgRent) : 0,
      isEstimated: !!ref,
    }
  })
}

export const LTV_OPTIONS = [0.40, 0.50, 0.60, 0.65, 0.70, 0.80]
export const RATE_OPTIONS = [0.030, 0.035, 0.040, 0.045, 0.050, 0.055, 0.060, 0.070]
