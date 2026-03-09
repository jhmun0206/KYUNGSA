import { notFound } from "next/navigation"
import Link from "next/link"
import { fetchAuctionDetail, ApiNotFoundError } from "@/lib/api"
import { DecisionSection } from "@/components/detail/DecisionSection"
import { PillarBreakdown } from "@/components/detail/PillarBreakdown"
import { BasicInfo } from "@/components/detail/BasicInfo"
import { LocationButtons } from "@/components/detail/LocationButtons"
import { DetailSidePanel } from "@/components/detail/DetailSidePanel"

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
    // 모바일: pb-32 (MobileNav 64 + 액션바 ~52 + 여유)
    // 데스크탑(sm+): pb-16
    <div className="mx-auto max-w-7xl pb-32 sm:pb-16">
      <div className="lg:flex lg:gap-6 lg:items-start">

        {/* ── 좌측: 메인 컨텐츠 ── */}
        <div className="flex-1 min-w-0 space-y-6 lg:space-y-8">

          {/* 섹션 1: 의사결정 — 등급 + 가격 + D-day + 면책 */}
          <DecisionSection auction={auction} />

          {/* 앵커 네비게이션 */}
          <nav className="flex gap-4 border-b border-border pb-2 text-sm overflow-x-auto">
            <a href="#analysis" className="text-primary font-medium whitespace-nowrap">상세 분석</a>
            <a href="#raw-data" className="text-muted-foreground hover:text-primary whitespace-nowrap">원본 데이터</a>
          </nav>

          {/* 로드뷰 / 위치 버튼 (좌표 있을 때만 렌더) */}
          <LocationButtons auction={auction} />

          {/* 섹션 2: 상세 분석 — 레이더 + 바차트 + 가격비교 */}
          <div id="analysis">
            <PillarBreakdown auction={auction} />
          </div>

          {/* 섹션 3: 원본 데이터 — 기일내역 + 기본정보 */}
          <div id="raw-data">
            <BasicInfo auction={auction} />
          </div>

          <div className="text-center">
            <Link href="/" className="text-sm text-primary hover:underline">
              ← 목록으로 돌아가기
            </Link>
          </div>
        </div>

        {/* ── 우측: 투자분석 사이드패널 (데스크탑) + 모바일 액션바 + 드로어 ── */}
        <DetailSidePanel auction={auction} />
      </div>
    </div>
  )
}
