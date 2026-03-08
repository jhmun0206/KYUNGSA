/**
 * NextAuth.js v5 App Router 핸들러
 *
 * GET  /api/auth/...  → 세션 조회, CSRF 토큰 등
 * POST /api/auth/...  → 로그인/로그아웃 콜백
 */

import { handlers } from "@/auth"

export const { GET, POST } = handlers
