"use client"

import Link from "next/link"
import Image from "next/image"
import { usePathname } from "next/navigation"
import { Home, Search, Map, Heart, Scale, LogIn, LogOut, ChevronDown } from "lucide-react"
import { useState, useEffect, useRef } from "react"
import { useSession, signIn, signOut } from "next-auth/react"
import { ThemeToggle } from "./ThemeToggle"
import { cn } from "@/lib/utils"
import { getCompareCount } from "@/lib/compare"
import { migrateLocalFavoritesToDB } from "@/lib/favorites"

const NAV_ITEMS = [
  { label: "홈", href: "/", icon: Home },
  { label: "검색", href: "/search", icon: Search },
  { label: "지도", href: "/map", icon: Map },
  { label: "비교", href: "/compare", icon: Scale },
  { label: "관심", href: "/favorites", icon: Heart },
]

export function Header() {
  const pathname = usePathname()
  const [compareCount, setCompareCount] = useState(0)
  const { data: session, status } = useSession()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 비교 카운트
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

  // 로그인 시 localStorage → DB 마이그레이션
  useEffect(() => {
    if (session?.backendToken) {
      migrateLocalFavoritesToDB(session.backendToken).catch(() => {})
    }
  }, [session?.backendToken])

  // 드롭다운 외부 클릭 닫기
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

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
              const isCompare = href === "/compare"
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "relative flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  )}
                >
                  <Icon size={15} />
                  {label}
                  {isCompare && compareCount > 0 && (
                    <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-white">
                      {compareCount}
                    </span>
                  )}
                </Link>
              )
            })}
          </nav>

          {/* 우측: 테마토글 + 로그인 */}
          <div className="flex items-center gap-2">
            <ThemeToggle />

            {/* 로그인 버튼 / 아바타 드롭다운 */}
            {status === "loading" ? (
              <div className="h-8 w-8 rounded-full bg-muted animate-pulse" />
            ) : session ? (
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen((v) => !v)}
                  className="flex items-center gap-1.5 rounded-full border border-border p-0.5 pr-2 text-sm hover:bg-accent transition-colors"
                >
                  {session.user?.image ? (
                    <Image
                      src={session.user.image}
                      alt={session.user.name ?? ""}
                      width={28}
                      height={28}
                      className="rounded-full"
                    />
                  ) : (
                    <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary">
                      {session.user?.name?.[0]?.toUpperCase() ?? "U"}
                    </div>
                  )}
                  <ChevronDown size={12} className={cn("text-muted-foreground transition-transform", dropdownOpen && "rotate-180")} />
                </button>

                {dropdownOpen && (
                  <div className="absolute right-0 top-10 w-44 rounded-lg border border-border bg-background shadow-lg py-1 z-50">
                    <div className="px-3 py-2 border-b border-border">
                      <p className="text-xs font-medium truncate">{session.user?.name}</p>
                      <p className="text-[10px] text-muted-foreground truncate">{session.user?.email}</p>
                    </div>
                    <Link
                      href="/favorites"
                      onClick={() => setDropdownOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-accent transition-colors"
                    >
                      <Heart size={14} />
                      관심 목록
                    </Link>
                    <button
                      onClick={() => { signOut(); setDropdownOpen(false) }}
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                    >
                      <LogOut size={14} />
                      로그아웃
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <button
                onClick={() => signIn("google")}
                className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              >
                <LogIn size={14} />
                <span className="hidden sm:inline">로그인</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
