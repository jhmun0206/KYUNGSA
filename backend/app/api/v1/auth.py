"""Phase I: 사용자 인증 엔드포인트

NextAuth.js OAuth 콜백 후 프론트엔드가 호출하는 upsert 엔드포인트.
Google OAuth 사용자 정보를 받아 users 테이블에 upsert 하고 backend JWT를 발급한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import settings
from app.models.db.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# ── JWT 헬퍼 ─────────────────────────────────────────────────────────────

_JWT_SECRET_DEFAULT = "change-me-in-production"


def _require_jwt_secret() -> str:
    """기본값/빈 시크릿으로는 절대 서명·검증하지 않는다 (토큰 위조 방지)."""
    secret = settings.JWT_SECRET
    if not secret or secret == _JWT_SECRET_DEFAULT:
        raise RuntimeError(
            "JWT_SECRET이 기본값입니다 — .env에 강한 랜덤 문자열을 설정하기 전까지 "
            "인증 기능을 사용할 수 없습니다."
        )
    return secret


def _create_token(user_id: str, email: str) -> str:
    """HS256 JWT 발급"""
    try:
        import jwt  # PyJWT
    except ImportError:
        raise RuntimeError("PyJWT가 설치되지 않았습니다: pip install PyJWT")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _require_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """JWT 검증 → payload dict 반환. 실패 시 ValueError."""
    try:
        import jwt  # PyJWT
    except ImportError:
        raise RuntimeError("PyJWT가 설치되지 않았습니다: pip install PyJWT")

    try:
        payload = jwt.decode(
            token,
            _require_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"토큰 검증 실패: {exc}") from exc


# ── 스키마 ────────────────────────────────────────────────────────────────

class UpsertRequest(BaseModel):
    """NextAuth.js → 백엔드로 전달되는 사용자 정보"""
    email: str
    name: str | None = None
    image: str | None = None
    google_id: str | None = None


class UpsertResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    image: str | None
    backend_token: str


# ── 엔드포인트 ─────────────────────────────────────────────────────────────

@router.post("/auth/upsert", response_model=UpsertResponse)
def upsert_user(
    body: UpsertRequest,
    db: Session = Depends(get_db),
) -> UpsertResponse:
    """OAuth 사용자 upsert + JWT 발급

    NextAuth.js jwt() 콜백에서 최초 로그인 시 한 번 호출.
    이메일 기준으로 users 테이블에 upsert 한다.
    """
    user = db.query(User).filter(User.email == body.email).first()

    if user is None:
        user = User(
            email=body.email,
            name=body.name,
            image=body.image,
            google_id=body.google_id,
        )
        db.add(user)
        logger.info("신규 사용자 생성: %s", body.email)
    else:
        # 이름/이미지/google_id 최신화
        if body.name:
            user.name = body.name
        if body.image:
            user.image = body.image
        if body.google_id and not user.google_id:
            user.google_id = body.google_id
        user.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    token = _create_token(user.id, user.email)
    return UpsertResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        image=user.image,
        backend_token=token,
    )
