"use client"

import { formatPrice } from "@/lib/utils"
import type { CashflowResult } from "@/lib/cashflow"

interface Props {
  bidPrice: number
  taxRate: number
  legalFee: number
  otherCosts: number
  result: CashflowResult
  onLegalFeeChange: (v: number) => void
  onOtherCostsChange: (v: number) => void
}

function Row({ label, value, bold, sub }: { label: string; value: string; bold?: boolean; sub?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className={`text-sm ${bold ? 'font-semibold text-slate-800 dark:text-slate-100' : 'text-slate-500 dark:text-slate-400'}`}>
        {label}
      </span>
      <div className="text-right">
        <span className={`tabular-nums ${bold ? 'text-base font-bold text-slate-900 dark:text-slate-100' : 'text-sm font-medium text-slate-700 dark:text-slate-200'}`}>
          {value}
        </span>
        {sub && <p className="text-xs text-slate-400 dark:text-slate-500">{sub}</p>}
      </div>
    </div>
  )
}

function EditableRow({
  label, value, onChange, sub,
}: { label: string; value: number; onChange: (v: number) => void; sub?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-slate-500 dark:text-slate-400 shrink-0">{label}</span>
      <div className="flex items-center gap-2">
        {sub && <span className="text-xs text-slate-400 dark:text-slate-500 hidden sm:block">{sub}</span>}
        <input
          type="number"
          value={value || ''}
          min={0}
          placeholder="0"
          onChange={e => onChange(Number(e.target.value) || 0)}
          className="w-28 text-right text-sm font-medium border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <span className="text-xs text-slate-500 shrink-0">만원</span>
      </div>
    </div>
  )
}

export function CostSection({ bidPrice, taxRate, legalFee, otherCosts, result, onLegalFeeChange, onOtherCostsChange }: Props) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-4">
        매입 비용
      </h3>
      <div className="space-y-3">
        <Row label="낙찰가" value={formatPrice(bidPrice * 10000)} />
        <Row
          label={`취득세 (${(taxRate * 100).toFixed(1)}%)`}
          value={formatPrice(result.acquisitionTax * 10000)}
          sub="자동 계산"
        />
        <EditableRow label="법무사비" value={legalFee} onChange={onLegalFeeChange} sub="기본 300만" />
        <EditableRow label="기타비용" value={otherCosts} onChange={onOtherCostsChange} sub="인테리어 등" />

        <div className="border-t border-slate-100 dark:border-slate-800 pt-3 space-y-2">
          <Row label="총 매입가" value={formatPrice(result.totalCost * 10000)} bold />
          <Row
            label="필요 자금"
            value={formatPrice(result.requiredEquity * 10000)}
            sub="총매입가 − 대출가능액"
          />
        </div>
      </div>
    </div>
  )
}
