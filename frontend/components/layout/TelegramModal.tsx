"use client"

import { useState, useEffect } from "react"
import { X, Bot, CheckCircle2, Copy, RefreshCw, Loader2, Unlink } from "lucide-react"
import { useSession } from "next-auth/react"
import { fetchTelegramStatus, issueTelegramCode, disconnectTelegram } from "@/lib/auth-api"

interface Props {
  onClose: () => void
}

export function TelegramModal({ onClose }: Props) {
  const { data: session, status: sessionStatus } = useSession()
  const token = session?.backendToken

  const [connected, setConnected] = useState<boolean | null>(null)
  const [verifiedAt, setVerifiedAt] = useState<string | null>(null)
  const [code, setCode] = useState<string | null>(null)
  const [expiresIn, setExpiresIn] = useState(0)
  const [loading, setLoading] = useState(true)
  const [issuing, setIssuing] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [copied, setCopied] = useState(false)

  const BOT_USERNAME = process.env.NEXT_PUBLIC_TELEGRAM_BOT ?? ""

  // 세션 인증 완료 시 1회만 텔레그램 연동 상태 조회
  useEffect(() => {
    if (sessionStatus !== "authenticated" || !token) {
      // 로딩/비인증 상태면 스피너 해제 (세션 로딩 중일 때는 유지)
      if (sessionStatus !== "loading") setLoading(false)
      return
    }
    fetchTelegramStatus(token)
      .then((s) => { setConnected(s.connected); setVerifiedAt(s.verified_at) })
      .catch(() => setConnected(false))
      .finally(() => setLoading(false))
  }, [sessionStatus, token])

  // 카운트다운
  useEffect(() => {
    if (expiresIn <= 0) return
    const id = setInterval(() => setExpiresIn((v) => Math.max(0, v - 1)), 1000)
    return () => clearInterval(id)
  }, [expiresIn])

  const handleIssueCode = async () => {
    if (!token) return
    setIssuing(true)
    try {
      const res = await issueTelegramCode(token)
      setCode(res.code)
      setExpiresIn(res.expires_in)
    } finally {
      setIssuing(false)
    }
  }

  const handleCopy = () => {
    if (!code) return
    navigator.clipboard.writeText(`/start ${code}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDisconnect = async () => {
    if (!token) return
    setDisconnecting(true)
    try {
      await disconnectTelegram(token)
      setConnected(false)
      setVerifiedAt(null)
      setCode(null)
    } finally {
      setDisconnecting(false)
    }
  }

  const minutes = Math.floor(expiresIn / 60)
  const seconds = expiresIn % 60

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

        {loading ? (
          <div className="flex justify-center py-6">
            <Loader2 size={24} className="animate-spin text-muted-foreground" />
          </div>
        ) : connected ? (
          /* ── 연동 완료 상태 ── */
          <div className="space-y-4">
            <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 px-4 py-3">
              <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
              <div>
                <p className="text-sm font-medium">연동 완료</p>
                {verifiedAt && (
                  <p className="text-xs text-muted-foreground">
                    {new Date(verifiedAt).toLocaleDateString("ko-KR")} 연동
                  </p>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              저장된 검색 조건과 매칭되는 새 물건이 나오면 텔레그램으로 알림을 보내드립니다.
            </p>
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-destructive/50 py-2.5 text-sm text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
            >
              {disconnecting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Unlink size={14} />
              )}
              연동 해제
            </button>
          </div>
        ) : (
          /* ── 미연동 상태 ── */
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
                <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                  <span>{copied ? "복사됨!" : `/start ${code} 복사`}</span>
                  {expiresIn > 0 ? (
                    <span className={expiresIn < 60 ? "text-destructive font-medium" : ""}>
                      {minutes}:{String(seconds).padStart(2, "0")} 남음
                    </span>
                  ) : (
                    <span className="text-destructive">만료됨</span>
                  )}
                </div>
                <button
                  onClick={handleIssueCode}
                  disabled={issuing}
                  className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-border py-2 text-xs text-muted-foreground hover:bg-accent transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} />
                  새 코드 발급
                </button>
              </div>
            ) : (
              <button
                onClick={handleIssueCode}
                disabled={issuing}
                className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-primary py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {issuing ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Bot size={14} />
                )}
                인증 코드 발급
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
