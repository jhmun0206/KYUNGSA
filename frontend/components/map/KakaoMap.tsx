"use client"

import { useEffect, useRef } from "react"
import { GRADE_COLORS } from "@/lib/constants"
import { formatPrice } from "@/lib/utils"
import type { MapItem } from "@/lib/types"

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    kakao: any
  }
}

interface Props {
  items: MapItem[]
}

export function KakaoMap({ items }: Props) {
  const mapKey = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!mapKey || !containerRef.current) return

    const script = document.createElement("script")
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${mapKey}&autoload=false&libraries=clusterer`
    script.async = true
    document.head.appendChild(script)

    script.onload = () => {
      window.kakao.maps.load(() => {
        const center = new window.kakao.maps.LatLng(37.5665, 126.9780)
        const map = new window.kakao.maps.Map(containerRef.current, {
          center,
          level: 7,
        })

        const clusterer = new window.kakao.maps.MarkerClusterer({
          map,
          averageCenter: true,
          minLevel: 5,
        })

        const markers = items
          .filter((item) => item.lat && item.lng)
          .map((item) => {
            const position = new window.kakao.maps.LatLng(item.lat!, item.lng!)
            const grade = item.grade ?? ""
            const color = GRADE_COLORS[grade] ?? "#9CA3AF"

            // 마커: 등급별 semantic color 원형 SVG
            const svgContent = `
              <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28">
                <circle cx="14" cy="14" r="12" fill="${color}" stroke="white" stroke-width="2" opacity="0.9"/>
                <text x="14" y="19" font-size="11" font-weight="bold" fill="white" text-anchor="middle" font-family="sans-serif">${grade || "?"}</text>
              </svg>`

            const markerImage = new window.kakao.maps.MarkerImage(
              `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgContent)}`,
              new window.kakao.maps.Size(28, 28),
              { offset: new window.kakao.maps.Point(14, 14) }
            )

            const marker = new window.kakao.maps.Marker({ position, image: markerImage })

            // 오버레이 팝업
            const overlayContent = `
              <div style="background:white;border:1px solid #e5e7eb;border-radius:10px;padding:10px 14px;min-width:180px;box-shadow:0 2px 8px rgba(0,0,0,0.12);font-family:sans-serif;">
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                  <span style="background:${color};color:white;font-size:11px;font-weight:700;border-radius:6px;padding:2px 7px;">${grade || "?"}</span>
                  <span style="font-size:11px;color:#6b7280;">${item.property_type}</span>
                </div>
                <p style="font-size:12px;font-weight:600;color:#111827;margin:0 0 4px;line-height:1.4;">${item.address}</p>
                <p style="font-size:11px;color:#6b7280;margin:0 0 6px;">감정가 ${formatPrice(item.appraised_value)}</p>
                ${item.auction_date ? `<p style="font-size:11px;color:#6b7280;margin:0 0 8px;">매각기일 ${item.auction_date.replace(/-/g, ".")}</p>` : ""}
                <a href="/auction/${encodeURIComponent(item.case_number)}" style="display:block;text-align:center;background:#2563eb;color:white;font-size:12px;font-weight:600;border-radius:6px;padding:5px 0;text-decoration:none;">상세보기</a>
              </div>`

            const overlay = new window.kakao.maps.CustomOverlay({
              content: overlayContent,
              position,
              yAnchor: 1.3,
              zIndex: 3,
            })
            overlay.setMap(null)

            window.kakao.maps.event.addListener(marker, "click", () => {
              overlay.setMap(overlay.getMap() ? null : map)
            })

            // 지도 클릭 시 오버레이 닫기
            window.kakao.maps.event.addListener(map, "click", () => {
              overlay.setMap(null)
            })

            return marker
          })

        clusterer.addMarkers(markers)
      })
    }

    return () => {
      document.head.removeChild(script)
    }
  }, [mapKey, items])

  if (!mapKey) {
    return (
      <div className="flex h-96 items-center justify-center rounded-lg border border-border bg-muted text-sm text-muted-foreground">
        <p>카카오맵 키가 설정되지 않았습니다. (NEXT_PUBLIC_KAKAO_MAP_KEY)</p>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="h-[70vh] min-h-[400px] w-full overflow-hidden rounded-lg border border-border"
    />
  )
}
