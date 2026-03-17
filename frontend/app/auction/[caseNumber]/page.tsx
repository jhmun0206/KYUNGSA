import { notFound } from "next/navigation"
import Link from "next/link"
import { ChevronLeft } from "lucide-react"
import { fetchAuctionDetail, ApiNotFoundError } from "@/lib/api"
import { DetailHeader } from "@/components/detail/DetailHeader"
import { BasicInfoGrid } from "@/components/detail/BasicInfoGrid"
import { RiskChecklist } from "@/components/detail/RiskChecklist"
import { RoundTimeline } from "@/components/detail/RoundTimeline"
import { CashflowCTA } from "@/components/detail/CashflowCTA"
import { RawDataAccordion } from "@/components/detail/RawDataAccordion"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"

interface PageProps {
  params: { caseNumber: string }
}

export default async function AuctionDetailPage({ params }: PageProps) {
  let auction
  let apiError = false

  try {
    auction = await fetchAuctionDetail(params.caseNumber)
  } catch (err) {
    if (err instanceof ApiNotFoundError) {
      notFound()
    }
    apiError = true
  }

  if (apiError || !auction) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10 space-y-4">
        <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950 px-5 py-4 text-sm text-amber-800 dark:text-amber-200">
          <p className="font-semibold">서버에 연결할 수 없습니다</p>
          <p className="mt-1 text-xs opacity-80">
            백엔드가 실행 중인지 확인하거나 잠시 후 다시 시도하세요.
          </p>
          <p className="mt-0.5 text-xs opacity-60">
            사건번호: {decodeURIComponent(params.caseNumber)}
          </p>
        </div>
        <Link
          href="/search"
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
        >
          <ChevronLeft className="h-4 w-4" />
          검색으로 돌아가기
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 pb-20">
      {/* 뒤로가기 */}
      <Link
        href="/search"
        className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 mb-5 transition-colors"
      >
        <ChevronLeft className="h-4 w-4" />
        목록으로
      </Link>

      {/* 1. 헤더: 신호등 + 주소 + 버튼 */}
      <DetailHeader auction={auction} />

      {/* 2. 기본정보 + 위치 */}
      <div className="mt-6">
        <BasicInfoGrid auction={auction} />
      </div>

      {/* 3. 리스크 체크리스트 */}
      <div className="mt-6">
        <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3">리스크 체크</h2>
        <RiskChecklist auction={auction} />
      </div>

      {/* 5. 기일 내역 */}
      {auction.rounds && auction.rounds.length > 0 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3">
            기일 내역
          </h2>
          <RoundTimeline rounds={auction.rounds} />
        </div>
      )}

      {/* 6. 현금흐름 분석 CTA */}
      <div className="mt-6">
        <CashflowCTA auction={auction} />
      </div>

      {/* 7. 원본 데이터 (접힘) */}
      <div className="mt-4">
        <RawDataAccordion auction={auction} />
      </div>

      {/* 8. 면책 */}
      <DisclaimerBanner className="mt-6" />
    </div>
  )
}
