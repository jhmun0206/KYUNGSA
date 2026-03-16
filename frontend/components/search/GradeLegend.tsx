/** 검색 결과 하단 리스크 범례 — 상시 표시 */
export function GradeLegend() {
  return (
    <div className="flex flex-wrap gap-4 px-4 py-3 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400">
      <span className="font-medium text-slate-700 dark:text-slate-300">리스크 기준:</span>
      <span>🟢 양호 — 주요 지표 긍정적</span>
      <span>🟡 주의 — 일부 확인 필요</span>
      <span>🔴 위험 — 다수 리스크 존재</span>
      <span>⚫ 미분류 — 데이터 수집 중</span>
      <span className="ml-auto text-slate-400 dark:text-slate-500">
        ※ 공공데이터 기반 참고 정보. 투자 추천 아님.
      </span>
    </div>
  )
}
