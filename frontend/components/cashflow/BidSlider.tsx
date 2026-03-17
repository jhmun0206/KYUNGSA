"use client"

import { formatMan } from "@/lib/utils"

interface Props {
  value: number          // 만원
  min: number            // 최저매각가격 (만원)
  max: number            // 감정가 (만원)
  appraisedValue: number // 감정가 (만원, 비율 계산용)
  mlPrediction?: { predicted_ratio: number | null; predicted_price: number | null } | null
  onChange: (v: number) => void
}

export function BidSlider({ value, min, max, appraisedValue, mlPrediction, onChange }: Props) {
  const ratio = appraisedValue > 0 ? Math.round(value / appraisedValue * 100) : 0
  const pct = max > min ? Math.round((value - min) / (max - min) * 100) : 0

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-4">
        낙찰 희망가
      </h3>

      <div className="mb-4">
        <span className="text-2xl font-bold text-slate-900 dark:text-slate-100 tabular-nums">
          {formatMan(value)}
        </span>
        <span className="ml-2 text-sm font-medium text-blue-600 dark:text-blue-400">
          감정가 대비 {ratio}%
        </span>
      </div>

      {/* 슬라이더 */}
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max > min ? max : min + 10000}
          step={100}
          value={value}
          onChange={e => onChange(Number(e.target.value))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer
            bg-slate-200 dark:bg-slate-700
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-5
            [&::-webkit-slider-thumb]:h-5
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-blue-600
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:shadow-md"
          style={{
            background: `linear-gradient(to right, rgb(37 99 235) ${pct}%, rgb(226 232 240) ${pct}%)`,
          }}
        />
      </div>

      <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500 mt-2">
        <span>최저 {formatMan(min)}</span>
        <span>감정가 {formatMan(appraisedValue)}</span>
      </div>

      {/* 유사사례 참고 범위 */}
      {mlPrediction?.predicted_ratio != null && (
        <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-950/40 rounded-lg border border-blue-100 dark:border-blue-800">
          <p className="text-xs text-slate-500 dark:text-slate-400">💡 유사사례 참고 범위</p>
          <p className="text-sm font-medium text-blue-700 dark:text-blue-400">
            {(mlPrediction.predicted_ratio * 100).toFixed(1)}%
            <span className="text-slate-500 dark:text-slate-400 font-normal ml-2">
              ≈ {Math.round(appraisedValue * mlPrediction.predicted_ratio).toLocaleString()}만원
            </span>
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">참고용 데이터. 실제 낙찰가와 다를 수 있습니다.</p>
        </div>
      )}

      {/* 직접 입력 */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
        <span className="text-xs text-slate-400 dark:text-slate-500 shrink-0">직접 입력</span>
        <input
          type="number"
          value={value}
          min={1}
          onChange={e => {
            const v = Number(e.target.value)
            if (v > 0) onChange(v)
          }}
          className="flex-1 text-right text-sm font-medium border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-1.5 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <span className="text-xs text-slate-500 shrink-0">만원</span>
      </div>
    </div>
  )
}
