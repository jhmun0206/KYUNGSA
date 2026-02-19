"use client"

import { useEffect, useState } from "react"
import { Star } from "lucide-react"
import { isFavorite, toggleFavorite } from "@/lib/favorites"
import { cn } from "@/lib/utils"

interface Props {
  caseNumber: string
  className?: string
}

export function FavoriteButton({ caseNumber, className }: Props) {
  const [active, setActive] = useState(false)

  useEffect(() => {
    setActive(isFavorite(caseNumber))
  }, [caseNumber])

  function handleClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    const added = toggleFavorite(caseNumber)
    setActive(added)
  }

  return (
    <button
      onClick={handleClick}
      title={active ? "즐겨찾기 해제" : "즐겨찾기 추가"}
      className={cn(
        "rounded-full p-1.5 transition-colors hover:bg-accent",
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
