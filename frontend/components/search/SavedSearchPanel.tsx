"use client"

import { useEffect, useState } from "react"
import { useRouter, usePathname } from "next/navigation"
import { Bookmark, Trash2, ChevronDown, ChevronUp, Loader2 } from "lucide-react"
import { useSession } from "next-auth/react"
import {
  fetchSavedSearches,
  deleteSavedSearch,
  saveSearch,
  type SavedSearch,
} from "@/lib/auth-api"

interface Props {
  /** 현재 검색 파라미터 (저장 시 사용) */
  currentParams: Record<string, string>
}

export function SavedSearchPanel({ currentParams }: Props) {
  const { data: session } = useSession()
  const router = useRouter()
  const pathname = usePathname()

  const [searches, setSearches] = useState<SavedSearch[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saveName, setSaveName] = useState("")
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const token = session?.backendToken

  // 패널 열릴 때 목록 로드
  useEffect(() => {
    if (!open || !token) return
    setLoading(true)
    fetchSavedSearches(token)
      .then(setSearches)
      .catch(() => setMsg("목록을 불러오지 못했습니다"))
      .finally(() => setLoading(false))
  }, [open, token])

  if (!session) return null

  const handleSave = async () => {
    if (!token || !saveName.trim()) return
    setSaving(true)
    try {
      const created = await saveSearch(token, saveName.trim(), currentParams)
      setSearches((prev) => [created, ...prev])
      setSaveName("")
      setMsg("저장됐습니다")
      setTimeout(() => setMsg(null), 2000)
    } catch {
      setMsg("저장 실패")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!token) return
    try {
      await deleteSavedSearch(token, id)
      setSearches((prev) => prev.filter((s) => s.id !== id))
    } catch {
      setMsg("삭제 실패")
    }
  }

  const handleApply = (params: Record<string, string>) => {
    const p = new URLSearchParams(params)
    router.push(`${pathname}?${p.toString()}`)
  }

  return (
    <div className="border border-border rounded-xl overflow-hidden text-sm">
      {/* 헤더 */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-muted/40 hover:bg-muted/60 transition-colors"
      >
        <span className="flex items-center gap-1.5 font-medium text-foreground">
          <Bookmark size={14} />
          저장된 검색 조건
          {searches.length > 0 && (
            <span className="ml-1 rounded-full bg-primary/10 text-primary text-xs px-1.5 py-0.5">
              {searches.length}
            </span>
          )}
        </span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {open && (
        <div className="px-3 py-2 space-y-2">
          {/* 현재 조건 저장 */}
          <div className="flex gap-1.5">
            <input
              type="text"
              placeholder="조건 이름 입력"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
              className="flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary"
              maxLength={30}
            />
            <button
              onClick={handleSave}
              disabled={saving || !saveName.trim()}
              className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-colors"
            >
              {saving ? <Loader2 size={12} className="animate-spin" /> : "저장"}
            </button>
          </div>
          {msg && <p className="text-xs text-muted-foreground">{msg}</p>}

          {/* 저장된 목록 */}
          {loading ? (
            <div className="flex justify-center py-3">
              <Loader2 size={16} className="animate-spin text-muted-foreground" />
            </div>
          ) : searches.length === 0 ? (
            <p className="text-xs text-muted-foreground py-1">저장된 검색 조건이 없습니다.</p>
          ) : (
            <ul className="space-y-1">
              {searches.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center gap-1.5 group"
                >
                  <button
                    onClick={() => handleApply(s.params_json)}
                    className="flex-1 text-left rounded-md px-2 py-1.5 text-xs text-foreground hover:bg-accent transition-colors truncate"
                    title={s.name}
                  >
                    {s.name}
                  </button>
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <Trash2 size={12} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
