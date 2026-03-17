"use client"

interface Props {
  address: string
  lat: number
  lng: number
  onClose: () => void
}

export function MapModal({ address, lat, lng, onClose }: Props) {
  const kakaoUrl = `https://map.kakao.com/link/map/${encodeURIComponent(address)},${lat},${lng}`
  const naverUrl = `https://map.naver.com/p/search/${encodeURIComponent(address)}`
  const roadviewUrl = `https://map.kakao.com/link/roadview/${lat},${lng}`

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-slate-900 rounded-xl w-full max-w-2xl overflow-hidden shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <h3 className="font-medium text-slate-900 dark:text-slate-100 text-sm truncate pr-4">
            {address}
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 text-xl leading-none shrink-0"
          >
            ✕
          </button>
        </div>

        {/* 지도 iframe */}
        <iframe
          src={kakaoUrl}
          className="w-full border-0"
          style={{ height: '400px' }}
          title={`지도: ${address}`}
        />

        {/* 외부 링크 */}
        <div className="flex gap-2 p-3 border-t border-slate-200 dark:border-slate-700">
          <a
            href={roadviewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 text-center py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            로드뷰 ↗
          </a>
          <a
            href={kakaoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 text-center py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            카카오맵 ↗
          </a>
          <a
            href={naverUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 text-center py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            네이버 부동산 ↗
          </a>
        </div>
      </div>
    </div>
  )
}
