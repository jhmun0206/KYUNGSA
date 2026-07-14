import {
  SIGNAL_EMOJI,
  SIGNAL_TEXT_CLASS,
  SIGNAL_BG_CLASS,
  calcOccupancySignal,
  calcPriceSignal,
  calcLocationSignal,
} from "@/lib/risk-signals"
import type { RiskSignal } from "@/lib/risk-signals"
import type { AuctionDetailResponse } from "@/lib/types"
import { RegistryButton } from "./RegistryButton"

interface Props {
  auction: AuctionDetailResponse
}

function RiskRow({ risk }: { risk: RiskSignal }) {
  return (
    <div className={`p-4 rounded-xl border ${SIGNAL_BG_CLASS[risk.color]}`}>
      <div className="flex items-start gap-3">
        <span className="text-base mt-0.5 shrink-0">{SIGNAL_EMOJI[risk.color]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {risk.category}
            </span>
            <span className={`text-xs font-medium ${SIGNAL_TEXT_CLASS[risk.color]}`}>
              {risk.label}
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
            {risk.reason}
          </p>
          {risk.detail && risk.detail.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {risk.detail.map((d, i) => (
                <li key={i} className="text-xs text-slate-600 dark:text-slate-300">
                  • {d}
                </li>
              ))}
            </ul>
          )}
        </div>
        {risk.actionUrl && (
          <a
            href={risk.actionUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap shrink-0"
          >
            {risk.actionLabel ?? '바로가기'} ↗
          </a>
        )}
      </div>
    </div>
  )
}

/** 직접 확인 항목 행 — 자동 분석 대상이 아닌 체크리스트.
 *  '데이터 부족(⚫)'과 구분되는 시각 언어(📋 + 파란 톤)를 사용한다. */
function CheckItemRow({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/30">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-base shrink-0">📋</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {title}
            </span>
            <span className="text-xs font-medium text-blue-700 dark:text-blue-300">
              입찰 전 직접 확인
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
            {description}
          </p>
        </div>
        {action}
      </div>
    </div>
  )
}

/** legal_score 기반 선순위권리 신호 (등기 분석 완료 물건) */
function legalSignal(score: number): RiskSignal {
  const color = score >= 70 ? 'green' : score >= 45 ? 'yellow' : 'red'
  const label = color === 'green' ? '양호' : color === 'yellow' ? '주의' : '위험'
  return {
    category: '선순위권리',
    color,
    label: `${label} (권리분석 완료)`,
    reason: `등기부 자동 분석 점수 ${score.toFixed(0)}점 — 인수/소멸 상세는 아래 등기 분석 결과 참조`,
  }
}

export function RiskChecklist({ auction }: Props) {
  const legal = auction.score?.legal_score ?? null

  const scoreRisks: RiskSignal[] = [
    calcOccupancySignal(auction),
    calcPriceSignal(auction),
    calcLocationSignal(auction),
  ]

  return (
    <div className="space-y-2">
      {/* 선순위권리 — 등기 분석 보유 시 실신호, 미보유 시 직접 확인 항목 + 열람 CTA */}
      {legal != null ? (
        <>
          <RiskRow risk={legalSignal(legal)} />
          <div className="flex justify-end">
            <RegistryButton caseNumber={auction.case_number} seq={auction.property_sequence} />
          </div>
        </>
      ) : (
        <CheckItemRow
          title="선순위권리"
          description="근저당·가압류·가처분 등 인수 권리 여부 — 등기부 자동 분석을 실행하거나 직접 열람하세요"
          action={<RegistryButton caseNumber={auction.case_number} seq={auction.property_sequence} />}
        />
      )}

      {/* 유치권/법정지상권 — 자동 분석 범위 밖 (매각물건명세서 파싱 미구현) */}
      <CheckItemRow
        title="유치권/법정지상권"
        description="유치권 신고 여부·법정지상권 성립 가능성은 매각물건명세서와 현황조사서에서 직접 확인해야 합니다"
        action={
          <a
            href="https://www.courtauction.go.kr"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap shrink-0"
          >
            대법원경매 ↗
          </a>
        }
      />

      {scoreRisks.map((risk) => (
        <RiskRow key={risk.category} risk={risk} />
      ))}
    </div>
  )
}
