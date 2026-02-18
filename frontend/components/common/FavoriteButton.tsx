"use client"

import { useEffect, useState } from "react"
import { Star } from "lucide-react"
import { isFavorite, toggleFavorite } from "@/lib/favorites"

interface Props {
  caseNumber: string
}

export function FavoriteButton({ caseNumber }: Props) {
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
      className="p-1 rounded hover:bg-gray-100 transition-colors"
    >
      <Star
        size={16}
        className={active ? "fill-amber-400 text-amber-400" : "text-gray-400"}
      />
    </button>
  )
}
