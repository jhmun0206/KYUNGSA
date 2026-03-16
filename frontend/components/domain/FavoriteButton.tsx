"use client"

import { useEffect, useState } from "react"
import { Heart } from "lucide-react"
import { useSession } from "next-auth/react"
import { isFavorite, toggleFavorite, addFavoriteDB, removeFavoriteDB } from "@/lib/favorites"
import { cn } from "@/lib/utils"

interface Props {
  caseNumber: string
  className?: string
  label?: string
}

export function FavoriteButton({ caseNumber, className, label }: Props) {
  const [active, setActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const { data: session } = useSession()

  useEffect(() => {
    setActive(isFavorite(caseNumber))
  }, [caseNumber])

  async function handleClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    if (loading) return

    const token = session?.backendToken

    if (token) {
      // DB 모드: 낙관적 업데이트
      setLoading(true)
      const newState = !active
      setActive(newState)
      try {
        if (newState) {
          await addFavoriteDB(caseNumber, token)
        } else {
          await removeFavoriteDB(caseNumber, token)
        }
      } catch {
        setActive(!newState) // 롤백
      } finally {
        setLoading(false)
      }
    } else {
      // localStorage 모드
      const added = toggleFavorite(caseNumber)
      setActive(added)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      title={active ? "즐겨찾기 해제" : "즐겨찾기 추가"}
      className={cn(
        "flex items-center gap-1 rounded border px-2 py-1 transition-colors disabled:opacity-50",
        active
          ? "border-red-200 bg-red-50 text-red-500"
          : "border-slate-200 text-slate-400 hover:border-red-300 hover:bg-red-50 hover:text-red-500",
        className
      )}
    >
      <Heart className={cn("h-3.5 w-3.5", active && "fill-current")} />
      {label && <span className="text-[11px]">{label}</span>}
    </button>
  )
}
