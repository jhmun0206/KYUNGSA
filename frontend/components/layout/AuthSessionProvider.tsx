"use client"

/**
 * NextAuth SessionProvider 래퍼 (Phase I)
 *
 * "use client" 지시어가 필요하므로 별도 컴포넌트로 분리.
 * app/layout.tsx에서 ThemeProvider 내부에 배치.
 */

import { SessionProvider } from "next-auth/react"

export function AuthSessionProvider({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>
}
