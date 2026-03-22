"use client"

import { useState } from "react"
import { X, Bot, Copy, RefreshCw, Loader2 } from "lucide-react"
import { useSession } from "next-auth/react"

export function TelegramModal({ onClose }: { onClose: () => void }) {
  const { data: session } = useSession()
  const [code, setCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const BOT_USERNAME = process.env.NEXT_PUBLIC_TELEGRAM_BOT ?? ""

  const handleIssueCode = async () => {
    const token = session?.backendToken
    console.log("[TelegramModal] session:", session, "token:", token)
    if (!token) {
      setError("인증 토큰이 없습니다. 로그아웃 후 다시 로그인해주세요.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/users/me/telegram/code`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (!res.ok) throw new Error()
      const data = await res.json()
      setCode(data.code)
    } catch {
      setError("코드 발급에 실패했습니다. 다시 시도해주세요.")
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (!code) return
    navigator.clipboard.writeText(`/start ${code}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-sm rounded-2xl border border-border bg-background p-6 shadow-xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 닫기 버튼 */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X size={16} />
        </button>

        <div className="flex items-center gap-2 mb-4">
          <Bot size={20} className="text-primary" />
          <h2 className="text-base font-semibold">텔레그램 알림 연동</h2>
        </div>

        <div className="space-y-4">
          <p className="text-xs text-muted-foreground leading-relaxed">
            텔레그램 봇과 연동하면 저장된 검색 조건에 맞는 새 물건이 등록될 때 알림을 받을 수 있습니다.
          </p>

          <div className="rounded-xl bg-muted/40 px-4 py-3 text-xs space-y-1.5">
            <p className="font-medium text-foreground">연동 방법</p>
            {BOT_USERNAME ? (
              <p>
                1. 텔레그램에서{" "}
                <a
                  href={`https://t.me/${BOT_USERNAME}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  @{BOT_USERNAME}
                </a>{" "}
                을 열고
              </p>
            ) : (
              <p>1. 텔레그램에서 KYUNGSA 경매알림 봇을 열고</p>
            )}
            <p>2. 아래 인증 코드를 발급받아</p>
            <p>
              3. 봇에{" "}
              <span className="font-mono text-primary">/start 코드</span>{" "}
              형식으로 전송
            </p>
          </div>

          {code ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="flex-1 rounded-xl border border-border bg-muted/40 px-4 py-3 text-center font-mono text-2xl font-bold tracking-[0.3em] text-foreground">
                  {code}
                </div>
                <button
                  onClick={handleCopy}
                  title="/start 코드 복사"
                  className="shrink-0 rounded-xl border border-border px-3 py-3 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  <Copy size={14} />
                </button>
              </div>
              <p className="text-xs text-muted-foreground px-1">
                {copied ? "복사됨!" : `/start ${code} 복사`}
              </p>
              <button
                onClick={handleIssueCode}
                disabled={loading}
                className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-border py-2 text-xs text-muted-foreground hover:bg-accent transition-colors disabled:opacity-50"
              >
                {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                새 코드 발급
              </button>
            </div>
          ) : (
            <button
              onClick={handleIssueCode}
              disabled={loading}
              className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-primary py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
              인증 코드 발급
            </button>
          )}

          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      </div>
    </div>
  )
}
