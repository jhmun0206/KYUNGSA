/**
 * Phase I: 인증이 필요한 백엔드 API 호출 헬퍼
 *
 * backendToken을 Authorization Bearer로 전달한다.
 */

import { API_BASE } from "@/lib/constants"

async function authFetch<T>(
  path: string,
  token: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  })
  if (!res.ok) {
    throw new Error(`API 오류 ${res.status}: ${path}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── 즐겨찾기 ──────────────────────────────────────────────────────────────

export async function fetchFavorites(token: string): Promise<string[]> {
  const data = await authFetch<{ case_numbers: string[] }>("/api/v1/users/me/favorites", token)
  return data.case_numbers
}

export async function addFavorite(token: string, caseNumber: string): Promise<void> {
  await authFetch<void>(`/api/v1/users/me/favorites/${encodeURIComponent(caseNumber)}`, token, {
    method: "PUT",
  })
}

export async function removeFavorite(token: string, caseNumber: string): Promise<void> {
  await authFetch<void>(`/api/v1/users/me/favorites/${encodeURIComponent(caseNumber)}`, token, {
    method: "DELETE",
  })
}

export async function bulkSyncFavorites(token: string, caseNumbers: string[]): Promise<void> {
  await authFetch<void>("/api/v1/users/me/favorites/bulk", token, {
    method: "POST",
    body: JSON.stringify({ case_numbers: caseNumbers }),
  })
}

// ── 저장 검색 ──────────────────────────────────────────────────────────────

export interface SavedSearch {
  id: string
  name: string
  params_json: Record<string, string>
  created_at: string
}

export async function fetchSavedSearches(token: string): Promise<SavedSearch[]> {
  return authFetch<SavedSearch[]>("/api/v1/users/me/saved-searches", token)
}

export async function saveSearch(
  token: string,
  name: string,
  params_json: Record<string, string>,
): Promise<SavedSearch> {
  return authFetch<SavedSearch>("/api/v1/users/me/saved-searches", token, {
    method: "POST",
    body: JSON.stringify({ name, params_json }),
  })
}

export async function deleteSavedSearch(token: string, id: string): Promise<void> {
  await authFetch<void>(`/api/v1/users/me/saved-searches/${id}`, token, {
    method: "DELETE",
  })
}

// ── 텔레그램 연동 (Phase J) ───────────────────────────────────────────────

export interface TelegramStatus {
  connected: boolean
  verified_at: string | null
}

export async function fetchTelegramStatus(token: string): Promise<TelegramStatus> {
  return authFetch<TelegramStatus>("/api/v1/users/me/telegram", token)
}

export async function issueTelegramCode(token: string): Promise<{ code: string; expires_in: number }> {
  return authFetch<{ code: string; expires_in: number }>("/api/v1/users/me/telegram/code", token, {
    method: "POST",
  })
}

export async function disconnectTelegram(token: string): Promise<void> {
  await authFetch<void>("/api/v1/users/me/telegram", token, {
    method: "DELETE",
  })
}
