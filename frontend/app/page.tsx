import { Suspense } from "react"
import Link from "next/link"
import { fetchAuctions } from "@/lib/api"
import { AuctionCard } from "@/components/domain/AuctionCard"
import { AuctionFilters } from "@/components/auction/AuctionFilters"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"
import type { AuctionListResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

interface PageProps {
  searchParams: {
    tab?: string
    court_office_code?: string
    grade?: string
    property_type?: string
    sort?: string
    page?: string
  }
}

function Pagination({
  page,
  total,
  size,
  searchParams,
}: {
  page: number
  total: number
  size: number
  searchParams: Record<string, string | undefined>
}) {
  const totalPages = Math.ceil(total / size)
  if (totalPages <= 1) return null

  function buildUrl(p: number) {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(searchParams)) {
      if (v) params.set(k, v)
    }
    params.set("page", String(p))
    return `/?${params.toString()}`
  }

  const pages: number[] = []
  const start = Math.max(1, page - 2)
  const end = Math.min(totalPages, page + 2)
  for (let i = start; i <= end; i++) pages.push(i)

  return (
    <nav className="mt-8 flex items-center justify-center gap-1">
      {page > 1 && (
        <a href={buildUrl(page - 1)} className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent">
          이전
        </a>
      )}
      {pages.map((p) => (
        <a
          key={p}
          href={buildUrl(p)}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium",
            p === page ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
          )}
        >
          {p}
        </a>
      ))}
      {page < totalPages && (
        <a href={buildUrl(page + 1)} className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent">
          다음
        </a>
      )}
    </nav>
  )
}

export default async function HomePage({ searchParams }: PageProps) {
  const tab = searchParams.tab ?? "top"
  const page = Number(searchParams.page ?? 1)

  // 높은 평가 탭: A/B 등급, 최신순
  const topParams = {
    grade: "A,B",
    sort: "grade",
    page: 1,
    size: 12,
  }

  // 검색 탭: 필터 적용
  const searchParamsForApi = {
    court_office_code: searchParams.court_office_code,
    grade: searchParams.grade,
    property_type: searchParams.property_type,
    sort: searchParams.sort ?? "grade",
    page,
    size: 20,
  }

  let topData: AuctionListResponse = { total: 0, page: 1, size: 12, items: [] }
  let searchData: AuctionListResponse = { total: 0, page: 1, size: 20, items: [] }
  let apiError = false

  try {
    if (tab === "top") {
      topData = await fetchAuctions(topParams)
    } else {
      searchData = await fetchAuctions(searchParamsForApi)
    }
  } catch {
    apiError = true
  }

  const tabClass = (active: boolean) =>
    cn(
      "rounded-lg px-4 py-2 text-sm font-semibold transition-colors",
      active
        ? "bg-primary text-primary-foreground"
        : "text-muted-foreground hover:bg-accent hover:text-foreground"
    )

  function tabUrl(t: string) {
    return `/?tab=${t}`
  }

  return (
    <div>
      {/* 탭 네비게이션 */}
      <div className="mb-6 flex items-center gap-2">
        <Link href={tabUrl("top")} className={tabClass(tab === "top")}>
          높은 평가
        </Link>
        <Link href={tabUrl("search")} className={tabClass(tab === "search")}>
          검색
        </Link>
      </div>

      {apiError && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.
        </div>
      )}

      {/* 높은 평가 탭 */}
      {tab === "top" && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-foreground">A·B 등급 물건</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                정량 분석 기준 상위 등급. 총{" "}
                <span className="font-semibold text-foreground">{topData.total.toLocaleString()}</span>건
              </p>
            </div>
            <Link
              href="/?tab=search"
              className="text-xs text-primary hover:underline"
            >
              전체 검색 →
            </Link>
          </div>

          {topData.items.length === 0 && !apiError ? (
            <div className="py-16 text-center text-muted-foreground">
              <p>분석된 물건이 없습니다.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {topData.items.map((item) => (
                <AuctionCard key={item.case_number} item={item} />
              ))}
            </div>
          )}

          <div className="mt-8">
            <DisclaimerBanner compact />
          </div>
        </div>
      )}

      {/* 검색 탭 */}
      {tab === "search" && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              총{" "}
              <span className="font-semibold text-foreground">{searchData.total.toLocaleString()}</span>건
            </p>
          </div>

          <Suspense>
            <AuctionFilters />
          </Suspense>

          {searchData.items.length === 0 && !apiError ? (
            <div className="mt-12 py-8 text-center text-muted-foreground">
              <p>해당 조건의 물건이 없습니다.</p>
            </div>
          ) : (
            <>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {searchData.items.map((item) => (
                  <AuctionCard key={item.case_number} item={item} />
                ))}
              </div>
              <Pagination
                page={searchData.page}
                total={searchData.total}
                size={searchData.size}
                searchParams={searchParams}
              />
            </>
          )}

          <div className="mt-8">
            <DisclaimerBanner compact />
          </div>
        </div>
      )}
    </div>
  )
}
