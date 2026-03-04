"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Home, Search, Heart, Scale } from "lucide-react"
import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"
import { getCompareCount } from "@/lib/compare"

const NAV_ITEMS = [
  { label: "홈", href: "/", icon: Home },
  { label: "검색", href: "/search", icon: Search },
  { label: "비교", href: "/compare", icon: Scale },
  { label: "관심", href: "/favorites", icon: Heart },
]

export function MobileNav() {
  const pathname = usePathname()
  const [compareCount, setCompareCount] = useState(0)

  useEffect(() => {
    setCompareCount(getCompareCount())
    const handler = () => setCompareCount(getCompareCount())
    window.addEventListener("compare-change", handler)
    window.addEventListener("storage", handler)
    return () => {
      window.removeEventListener("compare-change", handler)
      window.removeEventListener("storage", handler)
    }
  }, [])

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-sm sm:hidden">
      <div className="flex h-16 items-stretch">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href)
          const isCompare = href === "/compare"
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "relative flex flex-1 flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground"
              )}
            >
              <span className="relative">
                <Icon size={20} strokeWidth={active ? 2.5 : 1.75} />
                {isCompare && compareCount > 0 && (
                  <span className="absolute -right-2 -top-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-destructive text-[8px] font-bold text-white">
                    {compareCount}
                  </span>
                )}
              </span>
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
