"use client"

import { useState } from "react"
import { Map, Navigation, Building2, MapPin } from "lucide-react"
import { MapModal } from "./MapModal"

interface Props {
  lat: number | null
  lng: number | null
  address: string
}

export function SkyviewMap({ lat, lng, address }: Props) {
  const [showModal, setShowModal] = useState(false)

  if (!lat || !lng) {
    return (
      <div className="h-44 bg-slate-100 dark:bg-slate-800 rounded-xl flex flex-col items-center justify-center gap-2 border border-slate-200 dark:border-slate-700">
        <MapPin className="h-8 w-8 text-slate-300 dark:text-slate-600" />
        <p className="text-sm text-slate-400 dark:text-slate-500">위치 정보 없음</p>
      </div>
    )
  }

  const kakaoUrl = `https://map.kakao.com/link/map/${encodeURIComponent(address)},${lat},${lng}`
  const naverUrl = `https://map.naver.com/p/search/${encodeURIComponent(address)}`
  const roadviewUrl = `https://map.kakao.com/link/roadview/${lat},${lng}`

  return (
    <>
      {/* 지도 썸네일 (iframe) */}
      <div
        className="relative rounded-xl overflow-hidden h-44 cursor-pointer border border-slate-200 dark:border-slate-700 group"
        onClick={() => setShowModal(true)}
        title="클릭하면 지도가 확대됩니다"
      >
        <iframe
          src={kakaoUrl}
          className="w-full h-full border-0 pointer-events-none"
          loading="lazy"
          title={`위치: ${address}`}
        />
        {/* 클릭 캡처용 오버레이 */}
        <div className="absolute inset-0 bg-transparent group-hover:bg-black/5 transition-colors" />
        <div className="absolute bottom-2 right-2 bg-white/90 dark:bg-slate-900/90 rounded-md px-2 py-1 text-xs text-slate-600 dark:text-slate-300 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity">
          클릭하여 확대
        </div>
      </div>

      {/* 외부 링크 버튼들 */}
      <div className="flex gap-2 mt-2">
        <a
          href={roadviewUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => e.stopPropagation()}
          className="flex items-center gap-1.5 flex-1 justify-center px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          <Navigation className="h-3 w-3" />
          로드뷰
        </a>
        <a
          href={kakaoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 flex-1 justify-center px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          <Map className="h-3 w-3" />
          카카오맵
        </a>
        <a
          href={naverUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 flex-1 justify-center px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          <Building2 className="h-3 w-3" />
          네이버
        </a>
      </div>

      {/* 확대 모달 */}
      {showModal && (
        <MapModal
          address={address}
          lat={lat}
          lng={lng}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  )
}
