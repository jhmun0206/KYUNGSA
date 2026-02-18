import { notFound } from "next/navigation"
import Link from "next/link"
import { fetchAuctionDetail } from "@/lib/api"
import { GradeBadge } from "@/components/auction/GradeBadge"
import { ScoreRadar } from "@/components/auction/ScoreRadar"
import { PriceComparison } from "@/components/auction/PriceComparison"
import { RoundTimeline } from "@/components/auction/RoundTimeline"
import { FavoriteButton } from "@/components/common/FavoriteButton"

interface PageProps {
  params: { caseNumber: string }
}

function formatAmount(v: number | null): string {
  if (v === null) return "-"
  const uk = Math.round(v / 10000)
  if (uk >= 10000) return `${(uk / 10000).toFixed(1)}억`
  return `${uk.toLocaleString()}만원`
}

function formatDate(d: string | null): string {
  if (!d) return "-"
  return d.replace(/-/g, ".")
}

export default async function AuctionDetailPage({ params }: PageProps) {
  let auction
  try {
    auction = await fetchAuctionDetail(params.caseNumber)
  } catch {
    notFound()
  }

  const score = auction.score
  const failCount = Math.max(0, auction.bid_count - 1)

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      {/* 상단 헤더 */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            {score?.grade && (
              <GradeBadge
                grade={score.grade}
                provisional={score.grade_provisional}
                size="lg"
              />
            )}
            <span className="text-sm text-gray-500">{auction.property_type}</span>
            {failCount > 0 && (
              <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-600">
                {failCount}회 유찰
              </span>
            )}
          </div>
          <h1 className="text-xl font-bold text-gray-900">{auction.address}</h1>
          <p className="text-sm text-gray-500">
            {auction.court} · {auction.case_number}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <FavoriteButton caseNumber={auction.case_number} />
          <a
            href={`https://www.courtauction.go.kr`}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
          >
            대법원 →
          </a>
        </div>
      </div>

      {/* A: 점수 섹션 */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* 레이더 차트 */}
        <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">리스크 분석</h2>
          {score ? (
            <ScoreRadar score={score} />
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-gray-400">
              점수 분석 대기 중
            </div>
          )}
        </div>

        {/* 점수 요약 */}
        <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">종합 점수</h2>
          {score ? (
            <div className="space-y-3">
              {/* 총점 */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">총점</span>
                <span className="text-2xl font-bold text-indigo-600">
                  {score.total_score?.toFixed(1) ?? "-"}
                </span>
              </div>

              {/* pillar 점수 */}
              {[
                { label: "권리분석", value: score.legal_score },
                { label: "수익성", value: score.price_score },
                { label: "입지", value: score.location_score },
                { label: "명도", value: score.occupancy_score },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div className="mb-0.5 flex justify-between text-xs text-gray-500">
                    <span>{label}</span>
                    <span>{value !== null ? `${value.toFixed(0)}점` : "분석 대기"}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-gray-100">
                    <div
                      className="h-1.5 rounded-full bg-indigo-400"
                      style={{ width: `${value ?? 0}%` }}
                    />
                  </div>
                </div>
              ))}

              {/* coverage 경고 */}
              {score.grade_provisional && (
                <p className="text-xs text-amber-600">
                  ⚠ 일부 항목 미분석 — 등급 잠정
                </p>
              )}

              {/* 경고 */}
              {score.warnings.length > 0 && (
                <ul className="space-y-0.5">
                  {score.warnings.map((w, i) => (
                    <li key={i} className="text-xs text-gray-500">
                      · {w}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">점수 없음</p>
          )}
        </div>
      </section>

      {/* B: 가격 비교 */}
      <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">가격 비교</h2>
        <PriceComparison auction={auction} />
        {score?.predicted_winning_ratio && (
          <p className="mt-1 text-right text-xs text-gray-400">
            유사 사례 참고 낙찰가율: {(score.predicted_winning_ratio * 100).toFixed(0)}%
            <span className="ml-1 text-gray-300">
              ({score.prediction_method ?? "rule_v1"})
            </span>
          </p>
        )}
      </section>

      {/* C: 기본 정보 */}
      <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">기본 정보</h2>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          {[
            { label: "매각기일", value: formatDate(auction.auction_date) },
            { label: "상태", value: auction.status || "-" },
            { label: "감정가", value: formatAmount(auction.appraised_value) },
            { label: "최저입찰가", value: formatAmount(auction.minimum_bid) },
            {
              label: "낙찰가",
              value: auction.winning_bid
                ? `${formatAmount(auction.winning_bid)} (${((auction.winning_ratio ?? 0) * 100).toFixed(1)}%)`
                : "-",
            },
            { label: "낙찰일", value: formatDate(auction.winning_date ?? null) },
            { label: "유찰횟수", value: failCount > 0 ? `${failCount}회` : "없음" },
            { label: "물건 유형", value: auction.property_type || "-" },
          ].map(({ label, value }) => (
            <div key={label}>
              <dt className="text-xs text-gray-400">{label}</dt>
              <dd className="mt-0.5 text-sm font-medium text-gray-800">{value}</dd>
            </div>
          ))}
        </dl>

        {auction.specification_remarks && (
          <div className="mt-4 rounded-lg bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-700 mb-1">주요 특이사항</p>
            <p className="text-sm text-amber-800 whitespace-pre-line">
              {auction.specification_remarks}
            </p>
          </div>
        )}
      </section>

      {/* D: 기일 내역 */}
      <section className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold text-gray-700">기일 내역</h2>
        <RoundTimeline rounds={auction.rounds} />
      </section>

      <div className="text-center">
        <Link
          href="/"
          className="text-sm text-indigo-600 hover:underline"
        >
          ← 목록으로 돌아가기
        </Link>
      </div>
    </div>
  )
}
