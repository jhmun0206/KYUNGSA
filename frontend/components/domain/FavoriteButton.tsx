"use client"

import { useEffect, useState } from "react"
import { Star } from "lucide-react"
import { useSession } from "next-auth/react"
import { isFavorite, toggleFavorite, addFavoriteDB, removeFavoriteDB } from "@/lib/favorites"
import { cn } from "@/lib/utils"

interface Props {
  caseNumber: string
  className?: string
}

export function FavoriteButton({ caseNumber, className }: Props) {
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
        "rounded-full p-1.5 transition-colors hover:bg-accent disabled:opacity-50",
        className
      )}
    >
      <Star
        size={15}
        className={active ? "fill-amber-400 text-amber-400" : "text-text-weak"}
      />
    </button>
  )
}
