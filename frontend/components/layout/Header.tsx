import Link from "next/link"

export function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          <Link href="/" className="text-lg font-bold text-indigo-700 tracking-tight">
            KYUNGSA
          </Link>
          <nav className="flex items-center gap-6 text-sm font-medium text-gray-600">
            <Link href="/" className="hover:text-gray-900">
              물건 목록
            </Link>
            <Link href="/favorites" className="hover:text-gray-900">
              즐겨찾기
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
