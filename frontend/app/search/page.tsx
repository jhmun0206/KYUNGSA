import { Suspense } from "react"
import Link from "next/link"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { fetchAuctions } from "@/lib/api"
import { SearchFilters } from "@/components/search/SearchFilters"
import { SearchResultsGrid } from "@/components/search/SearchResultsGrid"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"

export const dynamic = "force-dynamic"

interface PageProps {
  searchParams: {
    grade?: string
    court?: string
    type?: string
    sort?: string
    page?: string
  }
}

export default async function SearchPage({ searchParams }: PageProps) {
  const page = Math.max(1, parseInt(searchParams.page ?? "1"))
  const size = 20

  let data = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0, page: 1, size }
  let apiError = false

  try {
    data = await fetchAuctions({
      grade: searchParams.grade,
      court_office_code: searchParams.court,
      property_type: searchParams.type,
      sort: searchParams.sort ?? "grade",
      page,
      size,
    })
  } catch {
    apiError = true
  }

  const totalPages = Math.ceil(data.total / size)

  return (
    <div className="mx-auto max-w-4xl pb-16">
      {/* 페이지 헤더 */}
      <div className="mb-2 pt-2">
        <h1 className="text-xl font-bold text-foreground">물건 검색</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">
          등급 · 법원 · 물건종류로 필터링하고 정렬하세요
        </p>
      </div>

      {/* 에러 배너 */}
      {apiError && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.
        </div>
      )}

      {/* 스티키 필터 바 */}
      <Suspense fallback={null}>
        <SearchFilters />
      </Suspense>

      {/* 결과 그리드 */}
      <div className="mt-4">
        <SearchResultsGrid items={data.items} total={data.total} />
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          searchParams={searchParams}
        />
      )}

      <div className="mt-8">
        <DisclaimerBanner compact />
      </div>
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
    if (searchParams.grade) params.set("grade", searchParams.grade)
    if (searchParams.court) params.set("court", searchParams.court)
    if (searchParams.type) params.set("type", searchParams.type)
    if (searchParams.sort) params.set("sort", searchParams.sort)
    params.set("page", String(p))
    return `/search?${params.toString()}`
  }

  const pages = Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
    // 현재 페이지 중심으로 5페이지 표시
    const start = Math.max(1, Math.min(page - 2, totalPages - 4))
    return start + i
  })

  return (
    <div className="mt-6 flex items-center justify-center gap-1">
      {page > 1 && (
        <Link href={buildUrl(page - 1)} className="rounded-md p-1.5 hover:bg-muted">
          <ChevronLeft className="h-4 w-4" />
        </Link>
      )}
      {pages.map((p) => (
        <Link
          key={p}
          href={buildUrl(p)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            p === page
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        >
          {p}
        </Link>
      ))}
      {page < totalPages && (
        <Link href={buildUrl(page + 1)} className="rounded-md p-1.5 hover:bg-muted">
          <ChevronRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  )
}
