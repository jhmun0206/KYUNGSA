"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Home, Search, Map, Heart } from "lucide-react"
import { ThemeToggle } from "./ThemeToggle"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { label: "홈", href: "/", icon: Home },
  { label: "검색", href: "/search", icon: Search },
  { label: "지도", href: "/map", icon: Map },
  { label: "관심", href: "/favorites", icon: Heart },
]

export function Header() {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          {/* 로고 */}
          <Link href="/" className="text-base font-black tracking-tight text-primary">
            KYUNGSA
          </Link>

          {/* 데스크탑 Nav — 모바일에서는 숨김 */}
          <nav className="hidden items-center gap-0.5 sm:flex">
            {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href)
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )}
                >
                  <Icon size={15} />
                  {label}
                </Link>
              )
            })}
          </nav>

          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
