import Link from "next/link"
import { Calculator } from "lucide-react"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

export function CashflowCTA({ auction }: Props) {
  const hasCalcData = !!(auction.minimum_bid && auction.appraised_value)
  if (!hasCalcData) return null

  return (
    <div className="p-5 bg-gradient-to-r from-blue-50 to-teal-50 dark:from-blue-950/40 dark:to-teal-950/40 rounded-xl border border-blue-200 dark:border-blue-800">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-100 dark:bg-blue-900/60 rounded-lg shrink-0">
            <Calculator className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
              현금흐름 분석
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">
              예상 매입비용·대출·임대수익·수익률을 자동으로 계산합니다
            </p>
          </div>
        </div>
        <Link
          href={`/cashflow/${encodeURIComponent(auction.case_number)}`}
          className="shrink-0 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 text-white rounded-lg text-sm font-semibold transition-colors whitespace-nowrap"
        >
          분석 시작 →
        </Link>
      </div>
    </div>
  )
}
