"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"
import { X } from "lucide-react"
import { getCompareList, clearCompare } from "@/lib/compare"

export function CompareBar() {
  const [count, setCount] = useState(0)
  const router = useRouter()

  function sync() {
    setCount(getCompareList().length)
  }

  useEffect(() => {
    sync()
    // CompareButton에서 발생시키는 커스텀 이벤트 수신
    window.addEventListener("compare-change", sync)
    // 다른 탭에서 localStorage 변경 시 (storage 이벤트)
    window.addEventListener("storage", sync)
    return () => {
      window.removeEventListener("compare-change", sync)
      window.removeEventListener("storage", sync)
    }
  }, [])

  function handleClear() {
    clearCompare()
    setCount(0)
    window.dispatchEvent(new Event("compare-change"))
  }

  return (
    <AnimatePresence>
      {count > 0 && (
        <motion.div
          initial={{ y: 60, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 60, opacity: 0 }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="fixed bottom-20 left-4 right-4 z-40 sm:bottom-4"
        >
          <div className="mx-auto flex max-w-lg items-center justify-between rounded-xl bg-primary px-4 py-3 shadow-lg">
            <span className="text-sm font-semibold text-primary-foreground">
              {count}건 선택됨
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => router.push("/compare")}
                className="rounded-lg bg-primary-foreground/20 px-3 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-foreground/30"
              >
                비교하기 →
              </button>
              <button
                onClick={handleClear}
                className="rounded-lg p-1.5 text-primary-foreground/70 transition-colors hover:bg-primary-foreground/20 hover:text-primary-foreground"
                title="초기화"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
