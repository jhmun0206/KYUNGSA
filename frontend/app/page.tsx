import Link from "next/link"
import { ArrowRight, Building2 } from "lucide-react"
import { fetchAuctions, fetchStats } from "@/lib/api"
import type { HomeStats } from "@/lib/types"
import { AuctionListRow } from "@/components/domain/AuctionListRow"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"
import { HeroSearch } from "@/components/home/HeroSearch"

export const dynamic = "force-dynamic"

const DEFAULT_STATS: HomeStats = {
  total_active: 0,
  this_week: 0,
  grade_a: 0,
  grade_b: 0,
  grade_c: 0,
  grade_d: 0,
}

export default async function LandingPage() {
  let upcoming = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0 }
  let topPicks = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0 }
  let stats: HomeStats = DEFAULT_STATS
  let apiError = false

  // 서버사이드에서 오늘~7일 범위 계산
  const today = new Date()
  const in7days = new Date(today)
  in7days.setDate(today.getDate() + 7)
  const todayStr = today.toISOString().slice(0, 10)
  const in7daysStr = in7days.toISOString().slice(0, 10)

  try {
    const [upcomingRes, topPicksRes, statsRes] = await Promise.all([
      fetchAuctions({
        grade: "A,B",
        sort: "auction_date",
        auction_date_from: todayStr,
        auction_date_to: in7daysStr,
        size: 8,
      }),
      fetchAuctions({ grade: "A,B", sort: "grade", size: 12 }),
      fetchStats(),
    ])
    upcoming = upcomingRes
    topPicks = topPicksRes
    stats = statsRes
  } catch {
    apiError = true
  }

  const abCount = stats.grade_a + stats.grade_b

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
          서울 경매 물건,
          <br />
          AI가 먼저 걸러드립니다
        </h1>
        <p className="mt-3 text-base text-muted-foreground sm:text-lg">
          서울 5개 법원 경매 물건을 매일 수집·등급화합니다.
          <br className="hidden sm:block" />
          상가·근린·꼬마빌딩 투자자를 위한 리스크 필터링 서비스.
        </p>
        <HeroSearch />
      </section>

      {/* 섹션 1: 통계 위젯 */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
        <Stat
          label="진행중 물건"
          value={stats.total_active > 0 ? `${stats.total_active.toLocaleString()}건` : "–"}
        />
        <Stat
          label="이번 주 기일"
          value={stats.this_week > 0 ? `${stats.this_week}건` : "–"}
          accent
        />
        <Stat
          label="A·B등급"
          value={abCount > 0 ? `${abCount.toLocaleString()}건` : "–"}
          accent
        />
        <div className="flex flex-col items-center gap-0.5 py-3 rounded-lg border border-border bg-card">
          <div className="flex justify-center gap-2 text-sm">
            <span className="font-semibold text-green-600 dark:text-green-400">A {stats.grade_a}</span>
            <span className="font-semibold text-blue-600 dark:text-blue-400">B {stats.grade_b}</span>
            <span className="font-semibold text-amber-600 dark:text-amber-400">C {stats.grade_c}</span>
          </div>
          <span className="text-xs text-muted-foreground">등급 분포</span>
        </div>
      </section>

      {/* 섹션 2: 이번 주 매각기일 */}
      {upcoming.items.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-foreground">이번 주 매각기일</h2>
              <span className="inline-flex items-center rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-semibold text-destructive">
                {upcoming.items.length}건
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
            {upcoming.items.map((item) => (
              <AuctionListRow key={item.case_number} item={item} />
            ))}
          </div>
        </section>
      )}

      {/* 섹션 3: 높은 평가 물건 */}
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

      <DisclaimerBanner />
    </div>
  )
}

function Stat({
  label,
  value,
  accent = false,
  small = false,
}: {
  label: string
  value: string
  accent?: boolean
  small?: boolean
}) {
  return (
    <div className="flex flex-col items-center gap-0.5 py-3 rounded-lg border border-border bg-card">
      <span
        className={`tabular-nums ${
          small
            ? "text-sm font-semibold text-foreground"
            : `font-black ${accent ? "text-xl text-primary" : "text-xl text-foreground"}`
        }`}
      >
        {value}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}
