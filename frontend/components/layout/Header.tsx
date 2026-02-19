import Link from "next/link"
import { Map, Star } from "lucide-react"
import { ThemeToggle } from "./ThemeToggle"

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <Link
            href="/"
            className="text-base font-black tracking-tight text-primary"
          >
            KYUNGSA
          </Link>

          <nav className="flex items-center gap-1">
            <Link
              href="/map"
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-text-mid transition-colors hover:bg-accent hover:text-foreground"
            >
              <Map size={15} />
              지도
            </Link>
            <Link
              href="/favorites"
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-text-mid transition-colors hover:bg-accent hover:text-foreground"
            >
              <Star size={15} />
              즐겨찾기
            </Link>
            <ThemeToggle />
          </nav>
        </div>
      </div>
    </header>
  )
}
