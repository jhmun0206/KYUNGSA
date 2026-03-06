/** 투자 분석 시뮬레이터 계산 함수 */

/** 주거용 물건 여부 판별 */
export function isResidential(propertyType: string): boolean {
  const residential = ["아파트", "다세대", "연립", "단독주택", "다가구", "빌라"]
  return residential.some((t) => propertyType?.includes(t))
}

/** 취등록세 계산 (단순화 버전)
 *  - 주택 6억 이하: 1%, 9억 이하: 2%, 9억 초과: 3%
 *  - 상업용: 4%
 *  ※ 다주택 중과, 농특세, 교육세 등 미반영 */
export function calcAcquisitionTax(
  price: number,
  propertyType: string
): number {
  if (isResidential(propertyType)) {
    if (price <= 600_000_000) return Math.round(price * 0.01)
    if (price <= 900_000_000) return Math.round(price * 0.02)
    return Math.round(price * 0.03)
  }
  return Math.round(price * 0.04)
}

/** 대출 가능 금액 */
export function calcLoanAmount(bidPrice: number, loanRatio: number): number {
  return Math.floor(bidPrice * loanRatio)
}

/** 월 이자 (이자만 상환) */
export function calcMonthlyInterest(
  loanAmount: number,
  annualRate: number
): number {
  return Math.floor((loanAmount * annualRate) / 12)
}

/** 총 매입 비용 */
export function calcTotalCost(
  bidPrice: number,
  acquisitionTax: number,
  lawyerFee: number
): number {
  return bidPrice + acquisitionTax + lawyerFee
}

/** 필요 자기자금 (총비용 - 대출) */
export function calcRequiredEquity(
  totalCost: number,
  loanAmount: number
): number {
  return totalCost - loanAmount
}

/** 월 순수익 */
export function calcMonthlyNet(
  monthlyRent: number,
  monthlyExpense: number,
  monthlyInterest: number
): number {
  return monthlyRent - monthlyExpense - monthlyInterest
}

/** 연수익률 (낙찰가 대비) */
export function calcYieldOnPrice(annualNet: number, bidPrice: number): number {
  if (bidPrice <= 0) return 0
  return (annualNet / bidPrice) * 100
}

/** 에퀴티 수익률 (자기자금 대비) */
export function calcYieldOnEquity(
  annualNet: number,
  requiredEquity: number
): number {
  if (requiredEquity <= 0) return 0
  return (annualNet / requiredEquity) * 100
}

/** 만원 단위 숫자를 원 단위로 */
export function manToWon(man: number): number {
  return man * 10000
}

/** 원 단위를 만원으로 */
export function wonToMan(won: number): number {
  return Math.round(won / 10000)
}
