import { API_BASE } from "@/lib/constants"
import type {
  AuctionDetailResponse,
  AuctionListParams,
  AuctionListResponse,
  MapResponse,
} from "@/lib/types"

export class ApiNotFoundError extends Error {
  constructor(path: string) {
    super(`404: ${path}`)
  }
}

async function apiFetch<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v))
      }
    })
  }
  const res = await fetch(url.toString(), { next: { revalidate: 300 } }) // 5분 캐시
  if (!res.ok) {
    if (res.status === 404) throw new ApiNotFoundError(path)
    throw new Error(`API 오류 ${res.status}: ${path}`)
  }
  return res.json() as Promise<T>
}

export async function fetchAuctions(
  params: AuctionListParams
): Promise<AuctionListResponse> {
  return apiFetch<AuctionListResponse>("/api/v1/auctions", params as Record<string, string | number | undefined>)
}

export async function fetchAuctionDetail(
  caseNumber: string
): Promise<AuctionDetailResponse> {
  // Next.js App Router params may pass URL-encoded segments as-is.
  // Normalize: decode first (no-op if already decoded), then re-encode.
  let normalized = caseNumber
  try {
    normalized = decodeURIComponent(caseNumber)
  } catch {
    // invalid percent-encoding — use as-is
  }
  return apiFetch<AuctionDetailResponse>(`/api/v1/auctions/${encodeURIComponent(normalized)}`)
}

export async function fetchMapItems(
  params: Omit<AuctionListParams, "page" | "size" | "sort">
): Promise<MapResponse> {
  return apiFetch<MapResponse>("/api/v1/auctions/map", params as Record<string, string | number | undefined>)
}
