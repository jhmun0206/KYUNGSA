import type { Metadata } from "next"
import "./globals.css"
import { Header } from "@/components/layout/Header"
import { Footer } from "@/components/layout/Footer"
import { MobileNav } from "@/components/layout/MobileNav"
import { CompareBar } from "@/components/domain/CompareBar"
import { ThemeProvider } from "@/components/layout/ThemeProvider"

export const metadata: Metadata = {
  title: "KYUNGSA — 경매 물건 분석",
  description:
    "부동산 경매 물건 리스크 자동 분석 서비스. 공공데이터 기반 필터링 결과를 제공합니다.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <div className="flex min-h-screen flex-col">
            <Header />
            <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 pb-20 sm:px-6 sm:pb-6 lg:px-8">
              {children}
            </main>
            <Footer />
            <CompareBar />
            <MobileNav />
          </div>
        </ThemeProvider>
      </body>
    </html>
  )
}
