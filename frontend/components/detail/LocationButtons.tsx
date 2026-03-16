"use client"

import { Map, Navigation, Building2 } from "lucide-react"
import type { AuctionDetailResponse } from "@/lib/types"

interface Props {
  auction: AuctionDetailResponse
}

export function LocationButtons({ auction }: Props) {
  const lat = auction.lat
  const lng = auction.lng
  const address = auction.address

  if (!lat || !lng) return null

  const roadviewUrl = `https://map.kakao.com/link/roadview/${lat},${lng}`
  const kakaoUrl = `https://map.kakao.com/link/map/${encodeURIComponent(address)},${lat},${lng}`
  const naverUrl = `https://map.naver.com/p/search/${encodeURIComponent(address)}`

  return (
    <div className="flex flex-wrap gap-2">
      <a
        href={roadviewUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground hover:bg-accent transition-colors"
      >
        <Navigation size={13} className="text-muted-foreground" />
        로드뷰
      </a>
      <a
        href={kakaoUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground hover:bg-accent transition-colors"
      >
        <Map size={13} className="text-muted-foreground" />
        카카오맵
      </a>
      <a
        href={naverUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground hover:bg-accent transition-colors"
      >
        <Building2 size={13} className="text-muted-foreground" />
        네이버 부동산
      </a>
    </div>
  )
}
