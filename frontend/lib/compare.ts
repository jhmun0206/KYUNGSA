const KEY = "kyungsa_compare"
const MAX = 3

export function getCompareList(): string[] {
  if (typeof window === "undefined") return []
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]")
  } catch {
    return []
  }
}

/** 비교 목록에 추가/제거. 최대 3건 */
export function toggleCompare(caseNumber: string): { added: boolean; overLimit: boolean } {
  const list = getCompareList()
  const idx = list.indexOf(caseNumber)
  if (idx !== -1) {
    list.splice(idx, 1)
    localStorage.setItem(KEY, JSON.stringify(list))
    return { added: false, overLimit: false }
  }
  if (list.length >= MAX) {
    return { added: false, overLimit: true }
  }
  list.push(caseNumber)
  localStorage.setItem(KEY, JSON.stringify(list))
  return { added: true, overLimit: false }
}

export function isInCompare(caseNumber: string): boolean {
  return getCompareList().includes(caseNumber)
}

export function clearCompare(): void {
  localStorage.removeItem(KEY)
}
