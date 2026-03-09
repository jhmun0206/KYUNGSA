/** 투자 분석 시뮬레이터 계산 함수 */

/** 주거용 물건 여부 판별 */
export function isResidential(propertyType: string): boolean {
  const residential = ["아파트", "다세대", "연립", "단독주택", "다가구", "빌라"]
  return residential.some((t) => propertyType?.includes(t))
}

/** 취등록세 계산 (농특세+교육세 포함 개략치)
 *  - 주택 6억 이하: 1.1%, 9억 이하: 2.2%, 9억 초과: 3.3%
 *  - 상업용/토지: 4.6%
 *  ※ 다주택 중과, 지방세 세부 항목 미반영 */
export function calcAcquisitionTax(
  price: number,
  propertyType: string
): number {
  if (isResidential(propertyType)) {
    if (price <= 600_000_000) return Math.round(price * 0.011)
    if (price <= 900_000_000) return Math.round(price * 0.022)
    return Math.round(price * 0.033)
  }
  return Math.round(price * 0.046)
}

/** 물건 유형별 기본 LTV (대출 비율)
 *  아파트=70%, 오피스텔=65%, 다세대/빌라=60%, 단독/다가구=60%
 *  상가/근생=50%, 토지=40%, 기타=60% */
export function getDefaultLoanRatio(propertyType: string): number {
  if (propertyType.includes("아파트")) return 0.70
  if (propertyType === "오피스텔") return 0.65
  if (
    propertyType.includes("다세대") ||
    propertyType.includes("연립") ||
    propertyType.includes("빌라")
  ) return 0.60
  if (propertyType.includes("단독") || propertyType.includes("다가구")) return 0.60
  if (propertyType.includes("상가") || propertyType.includes("근린시설")) return 0.50
  if (
    propertyType.includes("전답") ||
    propertyType.includes("임야") ||
    propertyType.includes("대지")
  ) return 0.40
  return 0.60
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
