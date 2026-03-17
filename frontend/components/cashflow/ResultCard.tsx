import { formatPrice } from "@/lib/utils"
import type { CashflowResult } from "@/lib/cashflow"

interface Props {
  result: CashflowResult
  bidPrice: number       // 만원
  appraisedValue: number // 만원
}

function Row({
  label,
  value,
  sub,
  highlight,
  valueColor,
}: {
  label: string
  value: string
  sub?: string
  highlight?: boolean
  valueColor?: string
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
        {sub && <p className="text-xs text-slate-400 dark:text-slate-500">{sub}</p>}
      </div>
      <span
        className={`tabular-nums shrink-0 ${
          valueColor ?? (highlight
            ? 'text-base font-bold text-blue-600 dark:text-blue-400'
            : 'text-sm font-medium text-slate-800 dark:text-slate-200')
        }`}
      >
        {value}
      </span>
    </div>
  )
}

function Divider() {
  return <div className="border-t border-slate-100 dark:border-slate-800 my-3" />
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide mb-2">
      {children}
    </p>
  )
}

export function ResultCard({ result, bidPrice, appraisedValue }: Props) {
  const hasRent = result.totalMonthlyRent > 0
  const ratio = appraisedValue > 0 ? Math.round(bidPrice / appraisedValue * 100) : 0

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-4">
        분석 결과
      </h3>

      {/* 낙찰가 요약 */}
      <div className="bg-slate-50 dark:bg-slate-800/60 rounded-lg p-3 mb-4 flex justify-between items-center">
        <span className="text-xs text-slate-500 dark:text-slate-400">낙찰 희망가</span>
        <div className="text-right">
          <span className="text-sm font-bold text-slate-900 dark:text-slate-100 tabular-nums">
            {formatPrice(bidPrice * 10000)}
          </span>
          <span className="ml-1.5 text-xs text-blue-600 dark:text-blue-400">감정가 {ratio}%</span>
        </div>
      </div>

      {/* 매입 비용 */}
      <div className="space-y-2.5">
        <Row label="총 매입가" value={formatPrice(result.totalCost * 10000)} />
        <Row label="필요 자금" value={formatPrice(result.requiredEquity * 10000)} />
        <Row
          label="만실후 투자금"
          value={formatPrice(result.netEquity * 10000)}
          sub="필요자금 − 보증금합계"
        />
      </div>

      <Divider />

      {/* 대출 */}
      <SectionLabel>대출</SectionLabel>
      <div className="space-y-2">
        <Row label="대출가능액" value={formatPrice(result.loanAmount * 10000)} />
        <Row label="월 이자" value={`${result.monthlyInterest.toLocaleString()}만원`} />
      </div>

      <Divider />

      {/* 임대 수익률 */}
      <SectionLabel>임대 수익률</SectionLabel>
      {hasRent ? (
        <div className="space-y-2">
          <Row
            label="연 임대수익"
            value={`${result.annualRentIncome.toLocaleString()}만원`}
          />
          <Row
            label="연 임대수익률"
            value={`${result.annualYield > 0 ? '' : ''}${result.annualYield}%`}
            highlight
          />
          {result.netEquity > 0 && (
            <Row
              label="에퀴티 수익률"
              value={`${result.equityYield}%`}
              sub="만실후 투자금 기준"
              highlight
            />
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg">
          호실 월세를 입력하면 수익률이 계산됩니다
        </p>
      )}

      {/* 매도 (입력 시만) */}
      {result.saleProfit !== undefined && (
        <>
          <Divider />
          <SectionLabel>매도</SectionLabel>
          <div className="space-y-2">
            <Row
              label="예상 매도차익"
              value={`${result.saleProfit >= 0 ? '+' : ''}${result.saleProfit.toLocaleString()}만원`}
              valueColor={`text-sm font-semibold tabular-nums ${result.saleProfit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}
            />
            {result.saleYield !== undefined && (
              <Row label="매도수익률" value={`${result.saleYield >= 0 ? '+' : ''}${result.saleYield}%`} />
            )}
          </div>
        </>
      )}

      <p className="text-xs text-slate-400 dark:text-slate-500 mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 leading-relaxed">
        ※ 참고용 시뮬레이션. 실제 세금·수익과 다를 수 있습니다.
      </p>
    </div>
  )
}
