import { KakaoMap } from "@/components/map/KakaoMap"
import { fetchMapItems } from "@/lib/api"
import type { MapResponse } from "@/lib/types"

// 매 요청마다 SSR — 빌드 시 정적 생성 방지 (API 타임아웃 회피)
export const dynamic = "force-dynamic"

export default async function MapPage() {
  let data: MapResponse = { items: [] }
  let apiError = false

  try {
    data = await fetchMapItems({})
  } catch {
    apiError = true
  }

  const withCoords = data.items.filter((i) => i.lat && i.lng)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">지도 보기</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            좌표 확인된 물건{" "}
            <span className="font-semibold text-foreground">{withCoords.length}</span>건
          </p>
        </div>
      </div>

      {apiError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하세요.
        </div>
      )}

      <KakaoMap items={data.items} />

      <p className="text-xs text-muted-foreground">
        마커를 클릭하면 물건 정보가 표시됩니다. 지도를 클릭하면 팝업이 닫힙니다.
      </p>
    </div>
  )
}
