"use client"

import { useState } from "react"
import { SlidersHorizontal, X } from "lucide-react"
import { SearchSidebar } from "./SearchSidebar"

/** 모바일에서 사이드바를 하단 드로어로 표시 */
export function MobileFilterDrawer() {
  const [open, setOpen] = useState(false)

  return (
    <>
      {/* 하단 고정 필터 버튼 (모바일에서만) */}
      <button
        onClick={() => setOpen(true)}
        className="lg:hidden fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 rounded-full bg-blue-600 px-5 py-3 text-sm font-medium text-white shadow-lg shadow-blue-600/25 active:scale-95 transition-transform"
      >
        <SlidersHorizontal size={16} />
        필터
      </button>

      {/* 오버레이 */}
      {open && (
        <div
          className="lg:hidden fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        />
      )}

      {/* 드로어 패널 */}
      <div
        className={`lg:hidden fixed inset-x-0 bottom-0 z-50 transform transition-transform duration-300 ease-out ${
          open ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <div className="max-h-[80vh] overflow-y-auto rounded-t-2xl bg-white dark:bg-slate-950 border-t border-slate-200 dark:border-slate-800 shadow-xl">
          {/* 드래그 핸들 + 닫기 */}
          <div className="sticky top-0 z-10 bg-white dark:bg-slate-950 px-4 pt-3 pb-2 flex items-center justify-between border-b border-slate-100 dark:border-slate-800">
            <div className="w-10 h-1 rounded-full bg-slate-300 dark:bg-slate-600 mx-auto absolute left-1/2 -translate-x-1/2 top-2" />
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">필터</h2>
            <button
              onClick={() => setOpen(false)}
              className="rounded-full p-1 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500"
            >
              <X size={18} />
            </button>
          </div>

          {/* 사이드바 콘텐츠 재사용 */}
          <div className="p-4">
            <SearchSidebar />
          </div>
        </div>
      </div>
    </>
  )
}
