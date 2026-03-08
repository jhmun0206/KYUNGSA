/**
 * NextAuth.js v5 설정 (Phase I)
 *
 * Google OAuth → 백엔드 upsert → backend_token 발급.
 * 모든 프론트엔드 인증 흐름의 진입점.
 */

import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    // NextAuth v5는 AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET 자동 바인딩
    Google,
  ],

  session: { strategy: "jwt" },

  callbacks: {
    /**
     * jwt() : 토큰 생성/갱신 시 호출
     * 최초 로그인(account 있을 때)에 백엔드 upsert 호출 후 backend_token 저장.
     */
    async jwt({ token, account, profile }) {
      // account는 최초 로그인 시에만 전달됨
      if (account && profile) {
        try {
          const res = await fetch(`${API_BASE}/api/v1/auth/upsert`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: token.email,
              name: token.name,
              image: token.picture,
              google_id: profile.sub,
            }),
          })
          if (res.ok) {
            const data = await res.json()
            token.backendToken = data.backend_token
            token.userId = data.user_id
          }
        } catch {
          // 백엔드 연결 실패 시 로그인은 유지 (backendToken 없음)
        }
      }
      return token
    },

    /**
     * session() : useSession() / getServerSession() 반환값 구성
     */
    async session({ session, token }) {
      if (token.backendToken) {
        session.backendToken = token.backendToken as string
      }
      if (token.userId) {
        session.userId = token.userId as string
      }
      return session
    },
  },

  pages: {
    signIn: "/",   // 로그인 페이지를 별도로 두지 않고 홈에서 모달 처리
  },
})
