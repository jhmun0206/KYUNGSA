"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Home, Search, Map, Heart } from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { label: "홈", href: "/", icon: Home },
  { label: "검색", href: "/search", icon: Search },
  { label: "지도", href: "/map", icon: Map },
  { label: "관심", href: "/favorites", icon: Heart },
]

export function MobileNav() {
  const pathname = usePathname()

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-sm sm:hidden">
      <div className="flex h-16 items-stretch">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon size={20} strokeWidth={active ? 2.5 : 1.75} />
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
