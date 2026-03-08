/**
 * NextAuth.js 세션 타입 확장 (Phase I)
 *
 * backendToken / userId 필드를 Session에 추가.
 */

import "next-auth"

declare module "next-auth" {
  interface Session {
    backendToken?: string
    userId?: string
  }
}
