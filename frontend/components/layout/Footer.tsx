export function Footer() {
  return (
    <footer className="border-t border-border bg-card mt-16">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 text-xs text-text-weak sm:flex-row sm:items-center sm:justify-between">
          <p className="font-semibold text-text-mid">KYUNGSA</p>
          <p className="leading-relaxed">
            이 서비스는 공공데이터 기반 필터링 정보를 제공하며, 투자 추천·법률 판단·입찰 조언이 아닙니다.
            개별 물건에 대한 최종 판단은 관련 전문가와 함께 확인하시기 바랍니다.
            데이터는 실시간이 아닐 수 있으며 오류가 포함될 수 있습니다.
          </p>
        </div>
        <p className="mt-3 text-[11px] text-text-weak">
          © {new Date().getFullYear()} KYUNGSA. 데이터 출처: 대법원 경매정보, 국토교통부, 카카오맵.
        </p>
      </div>
    </footer>
  )
}
