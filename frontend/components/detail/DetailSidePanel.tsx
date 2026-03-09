"use client"

import { useState } from "react"
import { X, Share2 } from "lucide-react"
import { InvestmentCalculator } from "./InvestmentCalculator"
import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { CompareButton } from "@/components/domain/CompareButton"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

export function DetailSidePanel({ auction }: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  const minBid = auction.minimum_bid ?? 0
  const appraised = auction.appraised_value ?? 0
  const hasCalc = minBid > 0 && appraised > 0

  function handleShare() {
    if (navigator.share) {
      navigator.share({ title: auction.address, url: window.location.href }).catch(() => {})
    } else {
      navigator.clipboard?.writeText(window.location.href)
    }
  }

  return (
    <>
      {/* ── 데스크탑: sticky 사이드패널 ── */}
      {hasCalc && (
        <div className="hidden lg:block w-[420px] shrink-0">
          <div className="sticky top-20 max-h-[calc(100vh-5.5rem)] overflow-y-auto rounded-lg">
            <InvestmentCalculator auction={auction} defaultOpen />
          </div>
        </div>
      )}

      {/* ── 모바일: 하단 고정 액션바 (MobileNav 위) ── */}
      <div className="fixed bottom-16 left-0 right-0 z-40 sm:hidden border-t border-border bg-card/95 backdrop-blur-sm px-4 py-2">
        <div className="flex items-center gap-2">
          {/* 관심 */}
          <div className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-border px-3 py-2">
            <FavoriteButton caseNumber={auction.case_number} />
            <span className="text-xs text-foreground">관심</span>
          </div>

          {/* 비교 */}
          <div className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-border px-3 py-2">
            <CompareButton caseNumber={auction.case_number} />
            <span className="text-xs text-foreground">비교</span>
          </div>

          {/* 투자분석 (계산기 있을 때) / 공유 (없을 때) */}
          {hasCalc ? (
            <button
              onClick={() => setDrawerOpen(true)}
              className="flex flex-1 items-center justify-center rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground"
            >
              투자 분석
            </button>
          ) : (
            <button
              onClick={handleShare}
              className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-border px-3 py-2"
            >
              <Share2 size={13} className="text-muted-foreground" />
              <span className="text-xs text-foreground">공유</span>
            </button>
          )}
        </div>
      </div>

      {/* ── 모바일: 투자분석 드로어 ── */}
      {drawerOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          {/* 백드롭 */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setDrawerOpen(false)}
          />
          {/* 드로어 패널 */}
          <div className="absolute bottom-0 left-0 right-0 bg-background rounded-t-2xl max-h-[90vh] overflow-y-auto">
            {/* 핸들 + 헤더 */}
            <div className="sticky top-0 z-10 bg-background border-b border-border">
              <div className="flex justify-center pt-2 pb-1">
                <div className="w-8 h-1 rounded-full bg-muted-foreground/30" />
              </div>
              <div className="flex items-center justify-between px-4 pb-3">
                <h3 className="text-base font-semibold text-foreground">투자 분석</h3>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="rounded-full p-1 text-muted-foreground hover:bg-accent transition-colors"
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            {/* 계산기 본문 */}
            <InvestmentCalculator auction={auction} defaultOpen />
          </div>
        </div>
      )}
    </>
  )
}
