// frontend/lib/property-category.ts

export const PROPERTY_CATEGORY_MAP: Record<string, string | null> = {
  '근린생활시설': '상가/근린',
  '제1종근린생활시설': '근린1종',
  '제2종근린생활시설': '근린2종',
  '근린시설': '상가/근린',
  '상가': '상가/근린',
  '상가,오피스텔,근린시설': '상가/근린',
  '오피스텔': '오피스텔',
  '아파트': '아파트',
  '다세대': '다세대/빌라',
  '연립주택': '다세대/빌라',
  '연립주택,다세대,빌라': '다세대/빌라',
  '빌라': '다세대/빌라',
  '다세대주택': '다세대/빌라',
  '단독주택': '단독/다가구',
  '단독주택다가구': '단독/다가구',
  '다가구주택': '단독/다가구',
  '대지': '토지',
  '전답': '토지',
  '임야': '토지',
  '대지,임야,전답': '토지',
  '자동차': null,
  '중기': null,
  '자동차,중기': null,
  '': null,
}

export function normalizePropertyType(propertyType: string | null | undefined): string | null {
  if (!propertyType) return null
  const pt = propertyType.trim()
  if (pt in PROPERTY_CATEGORY_MAP) return PROPERTY_CATEGORY_MAP[pt]
  if (pt.includes('근린')) return '상가/근린'
  if (pt.includes('상가')) return '상가/근린'
  if (pt.includes('오피스텔')) return '오피스텔'
  if (pt.includes('아파트')) return '아파트'
  if (pt.includes('다세대') || pt.includes('연립') || pt.includes('빌라')) return '다세대/빌라'
  if (pt.includes('단독') || pt.includes('다가구')) return '단독/다가구'
  if (pt.includes('대지') || pt.includes('임야') || pt.includes('전') || pt.includes('답')) return '토지'
  return '기타'
}

export const LTV_BY_CATEGORY: Record<string, number> = {
  '상가/근린': 0.80,
  '근린1종': 0.80,
  '근린2종': 0.80,
  '오피스텔': 0.65,
  '아파트': 0.70,
  '다세대/빌라': 0.60,
  '단독/다가구': 0.60,
  '토지': 0.40,
}

// 필터용 카테고리 목록 (순서 유지)
export const PROPERTY_CATEGORIES = [
  { value: '상가/근린', label: '상가/근린' },
  { value: '근린1종', label: '근린1종' },
  { value: '근린2종', label: '근린2종' },
  { value: '오피스텔', label: '오피스텔' },
  { value: '아파트', label: '아파트' },
  { value: '다세대/빌라', label: '다세대/빌라' },
  { value: '단독/다가구', label: '단독/다가구' },
  { value: '토지', label: '토지' },
]
