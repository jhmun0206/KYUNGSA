const KEY = "kyungsa_favorites"

export function getFavorites(): string[] {
  if (typeof window === "undefined") return []
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]")
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
  localStorage.setItem(KEY, JSON.stringify(list))
  return idx === -1  // true = 추가됨
}

export function isFavorite(caseNumber: string): boolean {
  return getFavorites().includes(caseNumber)
}
