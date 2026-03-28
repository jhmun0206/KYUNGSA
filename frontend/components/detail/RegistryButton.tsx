"use client"

import { useState } from "react"
import { useSession } from "next-auth/react"

interface AnalyzedRight {
  event_type: string
  purpose: string
  holder: string | null
  amount: number | null
  accepted_at: string | null
  classification: string
  reason: string
}

interface HardStopFlag {
  rule_id: string
  name: string
  description: string
}

interface RegistryData {
  source: "cache" | "fresh"
  has_hard_stop: boolean
  hard_stop_flags: HardStopFlag[]
  confidence: string
  summary: string
  extinguished_rights: AnalyzedRight[]
  surviving_rights: AnalyzedRight[]
  uncertain_rights: AnalyzedRight[]
  warnings: string[]
  fetched_at: string | null
  registry_unique_no: string | null
}

interface Props {
  caseNumber: string
  seq?: number
}

export function RegistryButton({ caseNumber, seq = 1 }: Props) {
  const { data: session, status } = useSession()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RegistryData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFetch = async () => {
    const token = session?.backendToken
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/auctions/${encodeURIComponent(caseNumber)}/registry?seq=${seq}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: undefined })) as { detail?: string }
        throw new Error(err.detail ?? `오류 ${res.status}`)
      }
      setResult(await res.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "알 수 없는 오류")
    } finally {
      setLoading(false)
    }
  }

  // 비로그인 → 인터넷등기소 링크만
  if (status !== "authenticated") {
    return (
      <span className="text-xs text-muted-foreground">
        <a
          href="https://www.iros.go.kr"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 underline"
        >
          인터넷등기소 ↗
        </a>
        <span className="ml-1.5 opacity-60">(로그인 시 자동 분석)</span>
      </span>
    )
  }

  // 결과 없음 → 조회 버튼
  if (!result) {
    return (
      <div className="space-y-1">
        <button
          onClick={handleFetch}
          disabled={loading}
          className="text-xs border rounded-md px-2.5 py-1
                     hover:bg-primary/10 hover:border-primary
                     disabled:opacity-50 transition-colors"
        >
          {loading ? "조회 중..." : "🏛 등기부 자동 분석"}
        </button>
        {error && <p className="text-xs text-destructive">{error}</p>}
        <p className="text-xs text-muted-foreground/60">
          CODEF API · 7일 캐시
        </p>
      </div>
    )
  }

  // 분석 결과 표시
  const fetchedLabel = result.source === "cache" ? "캐시" : "신규"
  return (
    <div className="mt-2 border rounded-lg p-3 space-y-2 text-sm bg-slate-50 dark:bg-slate-900/50">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
          등기부 분석 결과
        </span>
        <span className="text-xs text-muted-foreground">
          {fetchedLabel} · 신뢰도 {result.confidence}
        </span>
      </div>

      {result.has_hard_stop && result.hard_stop_flags.length > 0 && (
        <div className="rounded-md bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-2 space-y-0.5">
          {result.hard_stop_flags.map((f) => (
            <p key={f.rule_id} className="text-xs text-red-700 dark:text-red-400">
              ⚠️ [{f.rule_id}] {f.name} — {f.description}
            </p>
          ))}
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="space-y-0.5">
          {result.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-700 dark:text-amber-400">
              ⚡ {w}
            </p>
          ))}
        </div>
      )}

      {result.summary && (
        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
          {result.summary}
        </p>
      )}

      {result.surviving_rights.length > 0 && (
        <div>
          <p className="text-xs font-medium text-orange-600 dark:text-orange-400 mb-1">
            인수 권리 ({result.surviving_rights.length}건)
          </p>
          <ul className="space-y-0.5">
            {result.surviving_rights.map((r, i) => (
              <li key={i} className="text-xs text-slate-600 dark:text-slate-300">
                · {r.event_type}
                {r.holder ? ` (${r.holder})` : ""}
                {r.amount ? ` ${(r.amount / 1e4).toLocaleString()}만원` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.extinguished_rights.length > 0 && (
        <div>
          <p className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">
            소멸 권리 ({result.extinguished_rights.length}건)
          </p>
          <ul className="space-y-0.5">
            {result.extinguished_rights.slice(0, 5).map((r, i) => (
              <li key={i} className="text-xs text-slate-500 dark:text-slate-400">
                · {r.event_type}
                {r.holder ? ` (${r.holder})` : ""}
              </li>
            ))}
            {result.extinguished_rights.length > 5 && (
              <li className="text-xs text-slate-400">
                외 {result.extinguished_rights.length - 5}건
              </li>
            )}
          </ul>
        </div>
      )}

      <a
        href="https://www.iros.go.kr"
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-muted-foreground underline block pt-0.5"
      >
        인터넷등기소에서 원문 확인 ↗
      </a>
    </div>
  )
}
