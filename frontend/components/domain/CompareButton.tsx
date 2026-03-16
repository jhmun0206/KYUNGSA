"use client"

import { useEffect, useState } from "react"
import { Scale } from "lucide-react"
import { isInCompare, toggleCompare } from "@/lib/compare"
import { cn } from "@/lib/utils"

interface Props {
  caseNumber: string
  className?: string
  label?: string
}

export function CompareButton({ caseNumber, className, label }: Props) {
  const [active, setActive] = useState(false)

  useEffect(() => {
    setActive(isInCompare(caseNumber))
  }, [caseNumber])

  function handleClick(e: React.MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    const result = toggleCompare(caseNumber)
    if (result.overLimit) {
      alert("최대 3건까지 비교 가능합니다")
      return
    }
    setActive(result.added)
    // storage 이벤트로 다른 컴포넌트(CompareBar) 동기화
    window.dispatchEvent(new Event("compare-change"))
  }

  return (
    <button
      onClick={handleClick}
      title={active ? "비교 해제" : "비교 추가"}
      className={cn(
        "flex items-center gap-1 rounded border px-2 py-1 transition-colors",
        active
          ? "border-blue-200 bg-blue-50 text-blue-500"
          : "border-slate-200 text-slate-400 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-500",
        className
      )}
    >
      <Scale className="h-3.5 w-3.5" />
      {label && <span className="text-[11px]">{label}</span>}
    </button>
  )
}
