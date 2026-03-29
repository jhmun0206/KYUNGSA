"use client"

import { useState } from "react"
import {
  SIGNAL_EMOJI,
  SIGNAL_TEXT_CLASS,
  SIGNAL_BG_CLASS,
  calcOccupancySignal,
  calcPriceSignal,
  calcLocationSignal,
} from "@/lib/risk-signals"
import type { RiskSignal } from "@/lib/risk-signals"
import type { AuctionDetailResponse } from "@/lib/types"
import { RegistryButton, type RegistryData } from "./RegistryButton"

interface Props {
  auction: AuctionDetailResponse
}

function RiskRow({ risk }: { risk: RiskSignal }) {
  return (
    <div className={`p-4 rounded-xl border ${SIGNAL_BG_CLASS[risk.color]}`}>
      <div className="flex items-start gap-3">
        <span className="text-base mt-0.5 shrink-0">{SIGNAL_EMOJI[risk.color]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {risk.category}
            </span>
            <span className={`text-xs font-medium ${SIGNAL_TEXT_CLASS[risk.color]}`}>
              {risk.label}
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
            {risk.reason}
          </p>
          {risk.detail && risk.detail.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {risk.detail.map((d, i) => (
                <li key={i} className="text-xs text-slate-600 dark:text-slate-300">
                  • {d}
                </li>
              ))}
            </ul>
          )}
        </div>
        {risk.actionUrl && (
          <a
            href={risk.actionUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap shrink-0"
          >
            {risk.actionLabel ?? '바로가기'} ↗
          </a>
        )}
      </div>
    </div>
  )
}

function RegistryRow({ caseNumber, seq }: { caseNumber: string; seq: number }) {
  const [result, setResult] = useState<RegistryData | null>(null)

  return (
    <div className={`p-4 rounded-xl border ${SIGNAL_BG_CLASS["unknown"]}`}>
      <div className="flex items-center gap-3">
        <span className="text-base shrink-0">{SIGNAL_EMOJI["unknown"]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              선순위권리
            </span>
            <span className={`text-xs font-medium ${SIGNAL_TEXT_CLASS["unknown"]}`}>
              등기부 열람 후 확인
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
            근저당·가압류·가처분 등 인수 권리 여부 — 자동 분석 또는 직접 열람
          </p>
        </div>
        <RegistryButton caseNumber={caseNumber} seq={seq} onResult={setResult} />
      </div>

      {result && (
        <div className="mt-3 pt-3 border-t space-y-3">
          {/* Hard Stop 경고 */}
          {result.has_hard_stop && result.hard_stop_flags.length > 0 && (
            <div className="space-y-1">
              {result.hard_stop_flags.map((f) => (
                <div key={f.rule_id} className="flex items-start gap-1.5">
                  <span className="text-xs text-red-600 dark:text-red-400 font-semibold shrink-0">⛔ {f.name}</span>
                  <span className="text-xs text-slate-600 dark:text-slate-300">{f.description}</span>
                </div>
              ))}
            </div>
          )}

          {/* 요약 */}
          {result.summary && (
            <p className="text-xs text-slate-700 dark:text-slate-200 leading-relaxed">{result.summary}</p>
          )}

          {/* 인수 권리 */}
          {result.surviving_rights.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-1">인수 권리</p>
              <ul className="space-y-0.5">
                {result.surviving_rights.map((r, i) => (
                  <li key={i} className="text-xs text-slate-600 dark:text-slate-300">
                    • [{r.event_type}] {r.purpose}
                    {r.holder && ` — ${r.holder}`}
                    {r.amount != null && ` (${r.amount.toLocaleString()}원)`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 소멸 권리 */}
          {result.extinguished_rights.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-green-700 dark:text-green-400 mb-1">소멸 권리</p>
              <ul className="space-y-0.5">
                {result.extinguished_rights.map((r, i) => (
                  <li key={i} className="text-xs text-slate-500 dark:text-slate-400 line-through">
                    • [{r.event_type}] {r.purpose}
                    {r.holder && ` — ${r.holder}`}
                    {r.amount != null && ` (${r.amount.toLocaleString()}원)`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 불확실 권리 */}
          {result.uncertain_rights.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">확인 필요</p>
              <ul className="space-y-0.5">
                {result.uncertain_rights.map((r, i) => (
                  <li key={i} className="text-xs text-slate-500 dark:text-slate-400">
                    • [{r.event_type}] {r.purpose} — {r.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 경고 */}
          {result.warnings.length > 0 && (
            <ul className="space-y-0.5">
              {result.warnings.map((w, i) => (
                <li key={i} className="text-xs text-amber-700 dark:text-amber-400">⚠ {w}</li>
              ))}
            </ul>
          )}

          <p className="text-xs text-slate-400 dark:text-slate-500">
            신뢰도: {result.confidence}
            {result.source === "cache" && " · 캐시"}
            {result.fetched_at && ` · ${result.fetched_at.slice(0, 10)}`}
          </p>
        </div>
      )}
    </div>
  )
}

export function RiskChecklist({ auction }: Props) {
  const scoreRisks: RiskSignal[] = [
    // 유치권/법정지상권 — 항상 미확인
    {
      category: '유치권/법정지상권',
      color: 'unknown',
      label: '매각물건명세서 확인',
      reason: '유치권 신고 여부 및 법정지상권 성립 가능성 직접 확인 필요',
      actionUrl: 'https://www.courtauction.go.kr',
      actionLabel: '대법원경매',
    },
    // 점수 기반 신호등
    calcOccupancySignal(auction),
    calcPriceSignal(auction),
    calcLocationSignal(auction),
  ]

  return (
    <div className="space-y-2">
      {/* 선순위권리 — RegistryButton 내장 */}
      <RegistryRow
        caseNumber={auction.case_number}
        seq={auction.property_sequence}
      />
      {scoreRisks.map((risk) => (
        <RiskRow key={risk.category} risk={risk} />
      ))}
    </div>
  )
}
