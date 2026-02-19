import { Suspense } from "react"
import { fetchAuctions } from "@/lib/api"
import { AuctionCard } from "@/components/auction/AuctionCard"
import { AuctionFilters } from "@/components/auction/AuctionFilters"
import type { AuctionListResponse } from "@/lib/types"

interface PageProps {
  searchParams: {
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
        <a
          href={buildUrl(page - 1)}
          className="rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
        >
          이전
        </a>
      )}
      {pages.map((p) => (
        <a
          key={p}
          href={buildUrl(p)}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            p === page
              ? "bg-indigo-600 text-white"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          {p}
        </a>
      ))}
      {page < totalPages && (
        <a
          href={buildUrl(page + 1)}
          className="rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
        >
          다음
        </a>
      )}
    </nav>
  )
}

export default async function HomePage({ searchParams }: PageProps) {
  const page = Number(searchParams.page ?? 1)
  const params = {
    court_office_code: searchParams.court_office_code,
    grade: searchParams.grade,
    property_type: searchParams.property_type,
    sort: searchParams.sort,
    page,
    size: 20,
  }

  let data: AuctionListResponse = { total: 0, page: 1, size: 20, items: [] }
  let apiError = false
  try {
    data = await fetchAuctions(params)
  } catch {
    apiError = true
  }

  return (
    <div>
      <div className="mb-6 flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-gray-900">경매 물건 목록</h1>
        <p className="text-sm text-gray-500">
          총 <span className="font-semibold text-gray-700">{data.total.toLocaleString()}</span>건
        </p>
      </div>

      <Suspense>
        <AuctionFilters />
      </Suspense>

      {apiError && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.
        </div>
      )}

      {!apiError && data.items.length === 0 ? (
        <div className="mt-12 text-center text-gray-400">
          <p className="text-lg">해당 조건의 물건이 없습니다.</p>
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((item) => (
              <AuctionCard key={item.case_number} item={item} />
            ))}
          </div>

          <Pagination
            page={data.page}
            total={data.total}
            size={data.size}
            searchParams={searchParams}
          />
        </>
      )}
    </div>
  )
}
