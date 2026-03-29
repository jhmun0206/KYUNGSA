"use client"

import { useState } from "react"
import { useSession } from "next-auth/react"

export interface AnalyzedRight {
  event_type: string
  purpose: string
  holder: string | null
  amount: number | null
  accepted_at: string | null
  classification: string
  reason: string
}

export interface HardStopFlag {
  rule_id: string
  name: string
  description: string
}

export interface RegistryData {
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
  onResult: (result: RegistryData) => void
}

export function RegistryButton({ caseNumber, seq = 1, onResult }: Props) {
  const { data: session, status } = useSession()
  const [loading, setLoading] = useState(false)
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
      const data: RegistryData = await res.json()
      onResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "알 수 없는 오류")
    } finally {
      setLoading(false)
    }
  }

  // 세션 확인 중
  if (status === "loading") {
    return <span className="text-xs text-muted-foreground shrink-0">확인 중...</span>
  }

  // 비로그인 → 인터넷등기소 링크 + 로그인 안내
  if (status === "unauthenticated") {
    return (
      <div className="text-xs text-muted-foreground shrink-0 text-right">
        <a
          href="https://www.iros.go.kr"
          target="_blank"
          rel="noopener noreferrer"
          className="underline"
        >
          인터넷등기소 ↗
        </a>
        <span className="ml-1">(로그인 시 자동 분석)</span>
      </div>
    )
  }

  return (
    <div className="shrink-0 text-right space-y-1">
      <button
        onClick={handleFetch}
        disabled={loading}
        className="text-sm border rounded px-3 py-1
                   hover:bg-primary/10 hover:border-primary
                   transition-colors whitespace-nowrap disabled:opacity-50"
      >
        {loading ? "조회 중..." : "🏛 등기부 분석"}
      </button>
      {error && (
        <p className="text-xs text-destructive">조회 실패. 잠시 후 다시 시도해주세요.</p>
      )}
    </div>
  )
}
