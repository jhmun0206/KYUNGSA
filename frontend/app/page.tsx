import Link from "next/link"
import { ArrowRight, Building2 } from "lucide-react"
import { fetchAuctions } from "@/lib/api"
import { TopPicksGrid } from "@/components/landing/TopPicksGrid"
import { DisclaimerBanner } from "@/components/domain/DisclaimerBanner"

export const dynamic = "force-dynamic"

export default async function LandingPage() {
  let topPicks = { items: [] as Awaited<ReturnType<typeof fetchAuctions>>["items"], total: 0 }
  let totalCount = 0
  let apiError = false

  try {
    const [picks, all] = await Promise.all([
      fetchAuctions({ grade: "A,B", sort: "grade", size: 4 }),
      fetchAuctions({ size: 1 }),
    ])
    topPicks = picks
    totalCount = all.total
  } catch {
    apiError = true
  }

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

        {/* 통계 strip */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-6 sm:gap-10">
          <Stat label="수집 물건" value={totalCount > 0 ? `${totalCount.toLocaleString()}건` : "–"} />
          <div className="h-8 w-px bg-border" />
          <Stat label="A/B등급" value={abCount > 0 ? `${abCount.toLocaleString()}건` : "–"} accent />
          <div className="h-8 w-px bg-border" />
          <Stat label="서울 5개 법원" value="수집 중" />
        </div>
      </section>

      {/* Top Picks */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-foreground">이번 주 주목할 만한 물건</h2>
          {abCount > 4 && (
            <span className="text-xs text-muted-foreground">
              A/B등급 {abCount}건 중 상위 4건
            </span>
          )}
        </div>
        <TopPicksGrid items={topPicks.items.slice(0, 4)} />
      </section>

      {/* CTA */}
      <section className="text-center">
        <Link
          href="/search"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
        >
          전체 물건 검색하기
          <ArrowRight className="h-4 w-4" />
        </Link>
        <p className="mt-3 text-xs text-muted-foreground">
          등급 · 법원 · 물건종류로 필터링할 수 있습니다
        </p>
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
