import { Suspense } from "react"
import Link from "next/link"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { fetchAuctions } from "@/lib/api"
import { SearchSidebar } from "@/components/search/SearchSidebar"
import { SearchResults } from "@/components/search/SearchResults"
import { GradeLegend } from "@/components/search/GradeLegend"
import { MobileFilterDrawer } from "@/components/search/MobileFilterDrawer"
import { SearchToolbar } from "@/components/search/SearchToolbar"

export const dynamic = "force-dynamic"

interface PageProps {
  searchParams: Record<string, string | undefined>
}

function toStr(v: string | undefined): string | undefined {
  return v && v.trim() ? v.trim() : undefined
}

function toNum(v: string | undefined): number | undefined {
  if (!v) return undefined
  const n = parseInt(v)
  return isNaN(n) ? undefined : n
}

export default async function SearchPage({ searchParams }: PageProps) {
  const page = Math.max(1, parseInt(searchParams.page ?? "1"))
  const size = 30

  let data = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0, page: 1, size }
  let apiError = false

  try {
    data = await fetchAuctions({
      grade: toStr(searchParams.grade),
      court_office_code: toStr(searchParams.court),
      region: toStr(searchParams.region),
      district: toStr(searchParams.district),
      property_type: toStr(searchParams.category),   // URL: category → API: property_type
      q: toStr(searchParams.q),
      sort: toStr(searchParams.sort) ?? "auction_date",
      status: toStr(searchParams.status),
      min_price: toNum(searchParams.min_price),
      max_price: toNum(searchParams.max_price),
      bid_count_min: toNum(searchParams.bid_count_min),
      building_type: toStr(searchParams.building_type),
      build_year_min: toNum(searchParams.build_year_min),
      station_radius_m: toNum(searchParams.station_radius_m),
      page,
      size,
    })
  } catch {
    apiError = true
  }

  const totalPages = Math.ceil(data.total / size)

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* 사이드바 - 데스크탑에서 항상 표시 */}
      <aside className="hidden lg:block w-64 border-r border-slate-200 dark:border-slate-800 overflow-y-auto p-4 shrink-0 bg-white dark:bg-slate-950">
        <Suspense fallback={null}>
          <SearchSidebar />
        </Suspense>
      </aside>

      {/* 메인 콘텐츠 */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* 상단 툴바: 검색 + 정렬 + 건수 */}
        <div className="shrink-0 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
          <Suspense fallback={null}>
            <SearchToolbar total={data.total} />
          </Suspense>
        </div>

        {/* 에러 배너 */}
        {apiError && (
          <div className="mx-4 mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.
          </div>
        )}

        {/* 테이블 영역 */}
        <div className="flex-1 overflow-y-auto">
          <Suspense fallback={null}>
            <SearchResults initialData={data} />
          </Suspense>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <Pagination page={page} totalPages={totalPages} searchParams={searchParams} />
          )}

          {/* 범례 */}
          <GradeLegend />
        </div>
      </main>

      {/* 모바일: 하단 필터 버튼 + 드로어 */}
      <Suspense fallback={null}>
        <MobileFilterDrawer />
      </Suspense>
    </div>
  )
}

function Pagination({
  page,
  totalPages,
  searchParams,
}: {
  page: number
  totalPages: number
  searchParams: Record<string, string | undefined>
}) {
  const buildUrl = (p: number) => {
    const params = new URLSearchParams()
    Object.entries(searchParams).forEach(([k, v]) => {
      if (v && k !== "page") params.set(k, v)
    })
    params.set("page", String(p))
    return `/search?${params.toString()}`
  }

  const pages = Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
    const start = Math.max(1, Math.min(page - 2, totalPages - 4))
    return start + i
  })

  return (
    <div className="flex items-center justify-center gap-1 py-6">
      {page > 1 && (
        <Link
          href={buildUrl(page - 1)}
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          <ChevronLeft className="h-4 w-4" />
        </Link>
      )}
      {pages.map((p) => (
        <Link
          key={p}
          href={buildUrl(p)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            p === page
              ? "bg-blue-600 text-white"
              : "text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          {p}
        </Link>
      ))}
      {page < totalPages && (
        <Link
          href={buildUrl(page + 1)}
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          <ChevronRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  )
}
