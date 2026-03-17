interface Props {
  address: string
  propertyCategory: string | null | undefined
}

export function NearbyRentLink({ address, propertyCategory }: Props) {
  const encoded = encodeURIComponent(address)

  const links: Record<string, { label: string; url: string }> = {
    '상가/근린':  { label: '부동산플래닛', url: 'https://www.bdsplanet.com' },
    '근린1종':   { label: '부동산플래닛', url: 'https://www.bdsplanet.com' },
    '근린2종':   { label: '부동산플래닛', url: 'https://www.bdsplanet.com' },
    '아파트':    { label: '호갱노노', url: `https://hogangnono.com/search?q=${encoded}` },
    '다세대/빌라': { label: '다방', url: 'https://www.dabangapp.com' },
    '오피스텔':  { label: '다방', url: 'https://www.dabangapp.com' },
    '단독/다가구': { label: '네이버 부동산', url: `https://land.naver.com/search?searchQuery=${encoded}` },
  }

  const link = links[propertyCategory ?? '']
  if (!link) return null

  return (
    <a
      href={link.url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-xs text-blue-600 dark:text-blue-400 hover:underline whitespace-nowrap"
    >
      인근 시세 ({link.label}) ↗
    </a>
  )
}
