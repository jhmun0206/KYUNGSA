import { MapPin } from "lucide-react"

interface Props {
  lat: number | null
  lng: number | null
  address: string
}

export function SkyviewMap({ lat, lng, address }: Props) {
  const hasCoords = !!(lat && lng)

  const roadviewUrl = hasCoords
    ? `https://map.kakao.com/link/roadview/${lat},${lng}`
    : undefined
  const kakaoUrl = hasCoords
    ? `https://map.kakao.com/link/map/${encodeURIComponent(address)},${lat},${lng}`
    : undefined
  const naverUrl = `https://map.naver.com/p/search/${encodeURIComponent(address)}`

  const btnBase =
    "flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors"
  const btnActive =
    "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800"
  const btnDisabled =
    "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-400 dark:text-slate-600 cursor-not-allowed"

  return (
    <div className="flex flex-col gap-3">
      {/* 주소 표시 */}
      <div className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
        <MapPin className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{address}</span>
      </div>

      {/* 외부 지도 링크 버튼 3개 */}
      <div className="flex gap-2 flex-wrap">
        {hasCoords ? (
          <a
            href={roadviewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={`${btnBase} ${btnActive}`}
          >
            📷 로드뷰로 보기 ↗
          </a>
        ) : (
          <span className={`${btnBase} ${btnDisabled}`}>📷 로드뷰로 보기</span>
        )}

        {hasCoords ? (
          <a
            href={kakaoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={`${btnBase} ${btnActive}`}
          >
            🗺 카카오맵 ↗
          </a>
        ) : (
          <span className={`${btnBase} ${btnDisabled}`}>🗺 카카오맵</span>
        )}

        <a
          href={naverUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={`${btnBase} ${btnActive}`}
        >
          🏢 네이버 부동산 ↗
        </a>
      </div>

      {!hasCoords && (
        <p className="text-xs text-slate-400 dark:text-slate-500">
          좌표 미확인 — 주소 검색으로 네이버 부동산을 이용하세요
        </p>
      )}
    </div>
  )
}
