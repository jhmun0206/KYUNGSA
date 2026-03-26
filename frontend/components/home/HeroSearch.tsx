"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Search } from "lucide-react"

const QUICK_FILTERS = [
  { label: "상가/근린", category: "상가/근린" },
  { label: "아파트", category: "아파트" },
  { label: "다세대/빌라", category: "다세대/빌라" },
  { label: "오피스텔", category: "오피스텔" },
]

export function HeroSearch() {
  const router = useRouter()
  const [query, setQuery] = useState("")

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`)
    } else {
      router.push("/search")
    }
  }

  return (
    <div className="mt-6 space-y-3">
      <form onSubmit={handleSearch} className="flex gap-2 max-w-xl mx-auto">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            placeholder="주소, 건물명으로 검색..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full border border-border rounded-lg pl-9 pr-4 py-2.5 text-sm bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <button
          type="submit"
          className="bg-primary text-primary-foreground px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors shrink-0"
        >
          검색
        </button>
      </form>

      <div className="flex gap-2 flex-wrap justify-center">
        {QUICK_FILTERS.map(({ label, category }) => (
          <button
            key={label}
            onClick={() =>
              router.push(`/search?property_type=${encodeURIComponent(category)}`)
            }
            className="text-xs border border-border rounded-full px-3 py-1 bg-background text-muted-foreground hover:bg-primary/10 hover:text-primary hover:border-primary/40 transition-colors"
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
