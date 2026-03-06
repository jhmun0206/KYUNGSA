"use client"

import { Share2 } from "lucide-react"
import { FavoriteButton } from "@/components/domain/FavoriteButton"
import { CompareButton } from "@/components/domain/CompareButton"

interface Props {
  caseNumber: string
  address: string
}

export function MobileActionBar({ caseNumber, address }: Props) {
  function handleShare() {
    if (navigator.share) {
      navigator.share({ title: address, url: window.location.href }).catch(() => {})
    } else {
      navigator.clipboard?.writeText(window.location.href)
    }
  }

  return (
    <div className="fixed bottom-16 left-0 right-0 z-40 sm:hidden border-t border-border bg-card px-4 py-2">
      <div className="flex items-center gap-2">
        <div className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-border px-3 py-2 text-sm">
          <FavoriteButton caseNumber={caseNumber} />
          <span className="text-xs text-foreground">관심</span>
        </div>
        <div className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-border px-3 py-2 text-sm">
          <CompareButton caseNumber={caseNumber} />
          <span className="text-xs text-foreground">비교</span>
        </div>
        <button
          onClick={handleShare}
          className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-border px-3 py-2 text-sm"
        >
          <Share2 size={14} className="text-muted-foreground" />
          <span className="text-xs text-foreground">공유</span>
        </button>
      </div>
    </div>
  )
}
