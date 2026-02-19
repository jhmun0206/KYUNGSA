import { notFound } from "next/navigation"
import Link from "next/link"
import { fetchAuctionDetail, ApiNotFoundError } from "@/lib/api"
import { DecisionSection } from "@/components/detail/DecisionSection"
import { PillarBreakdown } from "@/components/detail/PillarBreakdown"
import { BasicInfo } from "@/components/detail/BasicInfo"

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
    // 백엔드 연결 실패 등 기타 오류 → 에러 배너로 표시
    apiError = true
  }

  if (apiError || !auction) {
    return (
      <div className="mx-auto max-w-4xl space-y-6 pb-16">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          <p className="font-semibold">서버에 연결할 수 없습니다</p>
          <p className="mt-1 text-xs">
            백엔드가 실행 중인지 확인하거나 잠시 후 다시 시도하세요.
          </p>
          <p className="mt-0.5 text-xs opacity-70">사건번호: {decodeURIComponent(params.caseNumber)}</p>
        </div>
        <div className="text-center">
          <Link href="/" className="text-sm text-primary hover:underline">
            ← 목록으로 돌아가기
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 pb-16">
      {/* 섹션 1: 의사결정 — 등급 + 가격 + D-day + 면책 */}
      <DecisionSection auction={auction} />

      {/* 섹션 2: 상세 분석 — 레이더 + 바차트 + 가격비교 */}
      <PillarBreakdown auction={auction} />

      {/* 섹션 3: 원본 데이터 — 기일내역 + 기본정보 */}
      <BasicInfo auction={auction} />

      <div className="text-center">
        <Link href="/" className="text-sm text-primary hover:underline">
          ← 목록으로 돌아가기
        </Link>
      </div>
    </div>
  )
}
