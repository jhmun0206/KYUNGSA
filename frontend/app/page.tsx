import Link from "next/link"
import { ArrowRight, Building2 } from "lucide-react"
import { fetchAuctions } from "@/lib/api"
import { AuctionListRow } from "@/components/domain/AuctionListRow"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"

export const dynamic = "force-dynamic"

export default async function LandingPage() {
  let upcoming = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0 }
  let topPicks = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0 }
  let totalCount = 0
  let apiError = false

  try {
    const [upcomingRes, topPicksRes, allStats] = await Promise.all([
      fetchAuctions({ grade: "A,B", sort: "auction_date", size: 20 }),
      fetchAuctions({ grade: "A,B", sort: "grade", size: 12 }),
      fetchAuctions({ size: 1 }),
    ])
    upcoming = upcomingRes
    topPicks = topPicksRes
    totalCount = allStats.total
  } catch {
    apiError = true
  }

  // 섹션 1: 오늘~7일 이내 매각기일 필터링 (서버 컴포넌트에서)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const in7days = new Date(today)
  in7days.setDate(today.getDate() + 7)
  const thisWeek = upcoming.items
    .filter((item) => {
      if (!item.auction_date) return false
      const d = new Date(item.auction_date)
      return d >= today && d <= in7days
    })
    .slice(0, 8)

  const abCount = topPicks.total

  return (
    <div className="mx-auto max-w-4xl space-y-12 pb-16">
      {/* 에러 배너 */}
      {apiError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.
        </div>
      )}

      {/* Hero */}
      <section className="pt-8 text-center sm:pt-14">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
          <Building2 className="h-7 w-7 text-primary" />
        </div>
        <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">
          경매 리스크를
          <br className="sm:hidden" />
          {" "}자동으로 구조화합니다
        </h1>
        <p className="mt-3 text-base text-muted-foreground sm:text-lg">
          70%를 먼저 걸러내고, 볼 가치 있는 물건만 큐레이션합니다
        </p>
      </section>

      {/* 섹션 1: 이번 주 매각기일 */}
      {thisWeek.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-foreground">이번 주 매각기일</h2>
              <span className="inline-flex items-center rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-semibold text-destructive">
                {thisWeek.length}건
              </span>
            </div>
            <Link
              href="/search?sort=auction_date&grade=A,B"
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              검색에서 더 보기
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="rounded-lg border border-border bg-card overflow-hidden">
            {thisWeek.map((item) => (
              <AuctionListRow key={item.case_number} item={item} />
            ))}
          </div>
        </section>
      )}

      {/* 섹션 2: 높은 평가 물건 */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-foreground">높은 평가 물건</h2>
            {abCount > 0 && (
              <span className="text-xs text-muted-foreground">
                A/B등급 {abCount.toLocaleString()}건
              </span>
            )}
          </div>
          <Link
            href="/search?sort=grade&grade=A,B"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            전체 보기
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          {topPicks.items.slice(0, 12).map((item) => (
            <AuctionListRow key={item.case_number} item={item} />
          ))}
        </div>
      </section>

      {/* 섹션 3: 통계 위젯 */}
      <section className="flex flex-wrap items-center justify-center gap-6 sm:gap-10">
        <Stat label="수집 물건" value={totalCount > 0 ? `${totalCount.toLocaleString()}건` : "–"} />
        <div className="h-8 w-px bg-border" />
        <Stat label="A/B등급" value={abCount > 0 ? `${abCount.toLocaleString()}건` : "–"} accent />
        <div className="h-8 w-px bg-border" />
        <Stat label="서울 5개 법원" value="수집 중" />
      </section>

      <DisclaimerBanner />
    </div>
  )
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span
        className={`text-xl font-black tabular-nums ${
          accent ? "text-primary" : "text-foreground"
        }`}
      >
        {value}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}
