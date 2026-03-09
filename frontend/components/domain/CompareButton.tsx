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
        "flex items-center gap-1 rounded-full px-1.5 py-1 transition-colors hover:bg-accent",
        className
      )}
    >
      <Scale
        size={14}
        className={active ? "fill-primary text-primary" : "text-text-weak"}
      />
      {label && (
        <span className="text-[10px] text-muted-foreground">{label}</span>
      )}
    </button>
  )
}
