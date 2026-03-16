import { AuctionTable } from "@/components/search/AuctionTable"
import type { AuctionListResponse } from "@/lib/types"

interface Props {
  initialData: AuctionListResponse
}

/** 모든 필터는 서버에서 처리됨. 클라이언트 필터링 없음. */
export function SearchResults({ initialData }: Props) {
  return <AuctionTable items={initialData.items} total={initialData.total} />
}
