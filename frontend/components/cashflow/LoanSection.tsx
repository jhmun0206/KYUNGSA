"use client"

import { formatPrice } from "@/lib/utils"
import type { CashflowResult } from "@/lib/cashflow"
import { LTV_OPTIONS, RATE_OPTIONS } from "@/lib/cashflow"

interface Props {
  ltv: number
  loanRate: number
  result: CashflowResult
  propertyCategory: string | null | undefined
  onLtvChange: (v: number) => void
  onLoanRateChange: (v: number) => void
}

export function LoanSection({ ltv, loanRate, result, propertyCategory, onLtvChange, onLoanRateChange }: Props) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-4">
        대출 분석
      </h3>

      {/* LTV 칩 */}
      <div className="mb-4">
        <div className="text-xs text-slate-500 dark:text-slate-400 mb-2">
          대출비율 (LTV)
          {propertyCategory && (
            <span className="ml-2 text-slate-400 dark:text-slate-500">— {propertyCategory} 기준</span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {LTV_OPTIONS.map(v => (
            <button
              key={v}
              onClick={() => onLtvChange(v)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                ltv === v
                  ? 'bg-blue-600 text-white'
                  : 'border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              {Math.round(v * 100)}%
            </button>
          ))}
        </div>
      </div>

      {/* 금리 선택 */}
      <div className="mb-4">
        <div className="text-xs text-slate-500 dark:text-slate-400 mb-2">대출 금리</div>
        <div className="flex flex-wrap gap-2">
          {RATE_OPTIONS.map(v => (
            <button
              key={v}
              onClick={() => onLoanRateChange(v)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                loanRate === v
                  ? 'bg-blue-600 text-white'
                  : 'border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
            >
              {(v * 100).toFixed(1)}%
            </button>
          ))}
          {/* 직접 입력 */}
          <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-700 rounded-lg px-2">
            <input
              type="number"
              step={0.1}
              min={0.1}
              max={20}
              value={(loanRate * 100).toFixed(1)}
              onChange={e => {
                const v = parseFloat(e.target.value)
                if (!isNaN(v) && v > 0) onLoanRateChange(v / 100)
              }}
              className="w-12 text-sm text-center bg-transparent text-slate-700 dark:text-slate-200 focus:outline-none py-1.5"
            />
            <span className="text-xs text-slate-400">%</span>
          </div>
        </div>
      </div>

      {/* 결과 요약 */}
      <div className="border-t border-slate-100 dark:border-slate-800 pt-3 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-slate-500 dark:text-slate-400">대출가능액</span>
          <span className="font-medium tabular-nums text-slate-800 dark:text-slate-200">
            {formatPrice(result.loanAmount * 10000)}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-500 dark:text-slate-400">실질대출 (대출−보증금)</span>
          <span className="font-medium tabular-nums text-slate-800 dark:text-slate-200">
            {formatPrice(result.realLoan * 10000)}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-500 dark:text-slate-400">월 이자</span>
          <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
            {result.monthlyInterest.toLocaleString()}만원
          </span>
        </div>
      </div>
    </div>
  )
}
