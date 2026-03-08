/**
 * 즐겨찾기 스토리지 (Phase I — 하이브리드)
 *
 * - 비로그인: localStorage (기존 API 유지)
 * - 로그인: DB API + localStorage 병렬 유지 (캐시 역할)
 * - 로그인 시 localStorage → DB 마이그레이션 (bulkSync 1회)
 */

import { addFavorite, removeFavorite, bulkSyncFavorites, fetchFavorites } from "@/lib/auth-api"

const LS_KEY = "kyungsa_favorites"
const LS_MIGRATED_KEY = "kyungsa_fav_migrated"   // 마이그레이션 완료 여부

// ── localStorage 기본 API (기존 코드 호환) ─────────────────────────────────

export function getFavorites(): string[] {
  if (typeof window === "undefined") return []
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || "[]")
  } catch {
    return []
  }
}

export function toggleFavorite(caseNumber: string): boolean {
  const list = getFavorites()
  const idx = list.indexOf(caseNumber)
  if (idx === -1) {
    list.push(caseNumber)
  } else {
    list.splice(idx, 1)
  }
  localStorage.setItem(LS_KEY, JSON.stringify(list))
  return idx === -1   // true = 추가됨
}

export function isFavorite(caseNumber: string): boolean {
  return getFavorites().includes(caseNumber)
}

// ── DB 모드 헬퍼 ──────────────────────────────────────────────────────────

/**
 * DB 즐겨찾기 추가 + localStorage에도 반영
 */
export async function addFavoriteDB(caseNumber: string, token: string): Promise<void> {
  await addFavorite(token, caseNumber)
  const list = getFavorites()
  if (!list.includes(caseNumber)) {
    list.push(caseNumber)
    localStorage.setItem(LS_KEY, JSON.stringify(list))
  }
}

/**
 * DB 즐겨찾기 제거 + localStorage에도 반영
 */
export async function removeFavoriteDB(caseNumber: string, token: string): Promise<void> {
  await removeFavorite(token, caseNumber)
  const list = getFavorites().filter((cn) => cn !== caseNumber)
  localStorage.setItem(LS_KEY, JSON.stringify(list))
}

/**
 * DB에서 즐겨찾기 목록 조회 + localStorage 갱신
 */
export async function syncFavoritesFromDB(token: string): Promise<string[]> {
  const caseNumbers = await fetchFavorites(token)
  localStorage.setItem(LS_KEY, JSON.stringify(caseNumbers))
  return caseNumbers
}

/**
 * 로그인 시 localStorage → DB 마이그레이션 (1회)
 * 완료 플래그는 로그아웃 시 리셋하지 않음 (재로그인해도 재동기화 안 함).
 */
export async function migrateLocalFavoritesToDB(token: string): Promise<void> {
  if (typeof window === "undefined") return
  if (localStorage.getItem(LS_MIGRATED_KEY) === "1") return

  const list = getFavorites()
  try {
    if (list.length > 0) {
      await bulkSyncFavorites(token, list)
    }
    // DB에서 최신 목록을 가져와 localStorage 갱신
    const dbList = await fetchFavorites(token)
    localStorage.setItem(LS_KEY, JSON.stringify(dbList))
    localStorage.setItem(LS_MIGRATED_KEY, "1")
  } catch {
    // 실패해도 localStorage 유지 (다음 로그인 시 재시도)
  }
}
