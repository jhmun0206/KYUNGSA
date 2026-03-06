import { GRADE_BG } from "@/lib/constants"

const GRADES = [
  {
    grade: "A",
    range: "80점 이상",
    desc: "수익성·입지·명도 주요 지표 양호",
  },
  {
    grade: "B",
    range: "60~79점",
    desc: "대체로 양호, 일부 항목 확인 필요",
  },
  {
    grade: "C",
    range: "40~59점",
    desc: "복합 리스크 존재, 주의 필요",
  },
  {
    grade: "D",
    range: "40점 미만",
    desc: "다수 리스크 확인, 신중한 검토 필요",
  },
] as const

/** 검색 페이지 필터 영역 아래 등급 범례 — 상시 표시 */
export function GradeLegend() {
  return (
    <div className="flex flex-wrap items-start gap-x-4 gap-y-1.5 rounded-md bg-muted/50 px-3 py-2 text-[11px]">
      {GRADES.map((g) => {
        const bg = GRADE_BG[g.grade] ?? ""
        return (
          <div key={g.grade} className="flex items-center gap-1.5">
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ring-1 ${bg}`}
            >
              {g.grade}
            </span>
            <span className="text-muted-foreground">
              <span className="font-medium text-foreground">{g.range}</span>
              {" · "}
              {g.desc}
            </span>
          </div>
        )
      })}
      <span className="text-[10px] text-muted-foreground opacity-70">
        * 수익성·입지·명도 3축 가중합산, 권리분석은 등기부 열람 시 반영
      </span>
    </div>
  )
}
