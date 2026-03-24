import { notFound } from "next/navigation"
import Link from "next/link"
import { ChevronLeft } from "lucide-react"
import { fetchAuctionDetail, ApiNotFoundError } from "@/lib/api"
import CashflowClient from "./CashflowClient"

interface PageProps {
  params: { caseNumber: string }
}

export default async function CashflowPage({ params }: PageProps) {
  let auction
  try {
    auction = await fetchAuctionDetail(params.caseNumber)
  } catch (err) {
    if (err instanceof ApiNotFoundError) notFound()
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950 px-5 py-4 text-sm text-amber-800 dark:text-amber-200">
          <p className="font-semibold">서버에 연결할 수 없습니다</p>
          <p className="mt-1 text-xs opacity-80">잠시 후 다시 시도하세요.</p>
        </div>
      </div>
    )
  }

  const caseNum = decodeURIComponent(params.caseNumber)

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 pb-20">
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* 상단 헤더 */}
        <div className="mb-6">
          <Link
            href={`/auction/${encodeURIComponent(caseNum)}`}
            className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 mb-3 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            {auction.address}
          </Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                현금흐름 분석
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 space-y-0.5">
                <span className="block">참고용 시뮬레이션입니다. 실제 세금·수익과 다를 수 있으며 투자 판단의 근거로 사용할 수 없습니다.</span>
                <span className="block">· 취득세는 낙찰가 기준 계산. 실제 납부액은 시가표준액·보유 주택 수에 따라 다를 수 있습니다.</span>
                <span className="block">· LTV는 금융기관·물건·지역에 따라 크게 달라집니다. 필요 시 직접 수정하세요.</span>
                <span className="block">· 수도권 규제지역 아파트는 유주택자 경락대출이 제한될 수 있습니다.</span>
              </p>
            </div>
            <span className="shrink-0 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              {caseNum}
            </span>
          </div>
        </div>

        <CashflowClient auction={auction} />
      </div>
    </div>
  )
}
