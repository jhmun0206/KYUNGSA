"use client"

import { Trash2 } from "lucide-react"
import type { CashflowUnit } from "@/lib/cashflow"
import { NearbyRentLink } from "./NearbyRentLink"

const VACANCY_OPTIONS = [0, 0.05, 0.10, 0.15, 0.20]

interface Props {
  units: CashflowUnit[]
  address: string
  propertyCategory: string | null | undefined
  vacancyRate: number
  onVacancyRateChange: (v: number) => void
  onChange: (units: CashflowUnit[]) => void
}

function NumInput({
  value,
  onChange,
  placeholder,
  step,
}: {
  value: number
  onChange: (v: number) => void
  placeholder?: string
  step?: string
}) {
  return (
    <input
      type="number"
      min={0}
      step={step}
      value={value || ''}
      placeholder={placeholder ?? '0'}
      onChange={e => onChange(Number(e.target.value) || 0)}
      className="w-full text-right text-sm border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />
  )
}

export function UnitsTable({ units, address, propertyCategory, vacancyRate, onVacancyRateChange, onChange }: Props) {
  const hasEstimated = units.some(u => u.isEstimated)
  const hasRentData = units.some(u => u.isEstimated)

  const updateUnit = (i: number, patch: Partial<CashflowUnit>) => {
    const next = [...units]
    next[i] = { ...next[i], ...patch, isEstimated: false }
    onChange(next)
  }

  const deleteUnit = (i: number) => onChange(units.filter((_, j) => j !== i))

  const addUnit = () =>
    onChange([...units, { label: `${units.length + 1}호`, areaSqm: null, deposit: 0, monthlyRent: 0 }])

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          호실별 임대수익
        </h3>
        <NearbyRentLink address={address} propertyCategory={propertyCategory} />
      </div>

      {/* 공실률 선택 */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-slate-500 dark:text-slate-400 shrink-0">공실률 가정</span>
        <div className="flex gap-1 flex-wrap">
          {VACANCY_OPTIONS.map(v => (
            <button
              key={v}
              onClick={() => onVacancyRateChange(v)}
              className={`px-2.5 py-0.5 text-xs rounded-full border transition-colors ${
                vacancyRate === v
                  ? 'bg-blue-600 text-white border-blue-600 dark:bg-blue-500 dark:border-blue-500'
                  : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:border-blue-400 dark:hover:border-blue-500'
              }`}
            >
              {v === 0 ? '0%' : `${(v * 100).toFixed(0)}%`}
            </button>
          ))}
        </div>
      </div>

      {hasEstimated && (
        <p className="text-xs text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg px-3 py-2 mb-3">
          💡 인근 실거래 데이터 기반 참고값이 자동 입력됐습니다. 직접 수정 가능합니다.
        </p>
      )}
      {!hasRentData && (
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-3">
          ⚠ 이 지역·유형의 임대 시세 데이터가 없습니다. 직접 입력해 주세요.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-400 dark:text-slate-500 border-b border-slate-100 dark:border-slate-800">
              <th className="text-left py-2 pr-2 font-medium">호실</th>
              <th className="text-right py-2 px-2 font-medium">면적(㎡)</th>
              <th className="text-right py-2 px-2 font-medium">보증금(만)</th>
              <th className="text-right py-2 px-2 font-medium">월세(만)</th>
              <th className="w-6 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50 dark:divide-slate-800/60">
            {units.map((unit, i) => (
              <>
              <tr key={i}>
                {/* 호실명 */}
                <td className="py-1.5 pr-2">
                  <input
                    type="text"
                    value={unit.label}
                    onChange={e => updateUnit(i, { label: e.target.value })}
                    className="w-full text-sm border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </td>
                {/* 면적 */}
                <td className="py-1.5 px-2 w-20">
                  <NumInput
                    value={unit.areaSqm != null ? Math.round(unit.areaSqm * 10) / 10 : 0}
                    onChange={v => updateUnit(i, { areaSqm: v ? Math.round(v * 10) / 10 : null })}
                    placeholder="-"
                    step="0.1"
                  />
                </td>
                {/* 보증금 */}
                <td className="py-1.5 px-2 w-24">
                  <NumInput
                    value={unit.deposit}
                    onChange={v => updateUnit(i, { deposit: v })}
                  />
                </td>
                {/* 월세 */}
                <td className={`py-1.5 px-2 w-24 ${unit.isEstimated ? 'opacity-70' : ''}`}>
                  <NumInput
                    value={unit.monthlyRent}
                    onChange={v => updateUnit(i, { monthlyRent: v })}
                  />
                </td>
                {/* 삭제 */}
                <td className="py-1.5 pl-1">
                  {units.length > 1 && (
                    <button
                      onClick={() => deleteUnit(i)}
                      className="p-1 text-slate-300 dark:text-slate-600 hover:text-red-400 dark:hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </td>
              </tr>
              {unit.note && (
                <tr key={`note-${i}`}>
                  <td colSpan={5} className="pb-2 pt-0.5">
                    <p className="text-xs text-amber-600 dark:text-amber-400">⚠ {unit.note}</p>
                  </td>
                </tr>
              )}
              </>
            ))}
          </tbody>
          {/* 합계 행 */}
          <tfoot>
            <tr className="border-t border-slate-200 dark:border-slate-700 font-medium text-sm">
              <td colSpan={2} className="pt-2.5 text-slate-500 dark:text-slate-400">합계</td>
              <td className="pt-2.5 px-2 text-right tabular-nums text-slate-700 dark:text-slate-200">
                {units.reduce((s, u) => s + (u.deposit || 0), 0).toLocaleString()}
              </td>
              <td className="pt-2.5 px-2 text-right tabular-nums text-blue-600 dark:text-blue-400 font-semibold">
                {units.reduce((s, u) => s + (u.monthlyRent || 0), 0).toLocaleString()}
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>

      <button
        onClick={addUnit}
        className="mt-3 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
      >
        + 호실 추가
      </button>
    </div>
  )
}
