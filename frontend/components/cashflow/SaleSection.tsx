"use client"

import type { CashflowResult } from "@/lib/cashflow"
import { formatMan } from "@/lib/utils"

interface Props {
  salePrice: number
  result: CashflowResult
  onChange: (v: number) => void
}

export function SaleSection({ salePrice, result, onChange }: Props) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-4">
        매도 수익 <span className="normal-case font-normal text-slate-400">(선택)</span>
      </h3>

      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-600 dark:text-slate-300 whitespace-nowrap shrink-0">
          매도 희망가
        </label>
        <input
          type="number"
          min={0}
          placeholder="0"
          value={salePrice || ''}
          onChange={e => onChange(Number(e.target.value) || 0)}
          className="flex-1 text-right text-sm font-medium border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <span className="text-sm text-slate-500 dark:text-slate-400 shrink-0">만원</span>
      </div>

      {salePrice > 0 && result.saleProfit !== undefined && (
        <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-slate-400">총 매입가</span>
            <span className="tabular-nums text-slate-700 dark:text-slate-200">
              {formatMan(result.totalCost)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-slate-400">매도차익</span>
            <span className={`tabular-nums font-semibold ${result.saleProfit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
              {result.saleProfit >= 0 ? '+' : ''}{result.saleProfit.toLocaleString()}만원
            </span>
          </div>
          {result.saleYield !== undefined && (
            <div className="flex justify-between text-sm">
              <span className="text-slate-500 dark:text-slate-400">매도수익률 (필요자금 기준)</span>
              <span className={`tabular-nums font-semibold ${result.saleYield >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                {result.saleYield >= 0 ? '+' : ''}{result.saleYield}%
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
