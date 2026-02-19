import { notFound } from "next/navigation"
import Link from "next/link"
import { fetchAuctionDetail } from "@/lib/api"
import { DecisionSection } from "@/components/detail/DecisionSection"
import { PillarBreakdown } from "@/components/detail/PillarBreakdown"
import { BasicInfo } from "@/components/detail/BasicInfo"

interface PageProps {
  params: { caseNumber: string }
}

export default async function AuctionDetailPage({ params }: PageProps) {
  let auction
  try {
    auction = await fetchAuctionDetail(params.caseNumber)
  } catch {
    notFound()
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
