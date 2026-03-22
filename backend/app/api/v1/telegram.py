"""Phase J: 텔레그램 봇 Webhook 핸들러

텔레그램이 봇 메시지를 POST /telegram/webhook 으로 전달한다.
인증 코드 (/start XXXXXX) 수신 → users.telegram_chat_id 업데이트.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import settings
from app.models.db.user import TelegramVerification, User
from app.services.notifier import send_to_chat

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telegram"])


async def _send(chat_id: str, text: str) -> None:
    """텔레그램 메시지 발송 (내부 헬퍼)"""
    send_to_chat(chat_id, text)


@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """텔레그램 봇 Webhook 수신

    TELEGRAM_WEBHOOK_SECRET 설정 시 헤더 검증.
    미설정이면 검증 생략 (개발/테스트용).
    """
    # Webhook Secret 검증 (설정된 경우에만)
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403, detail="Webhook secret 불일치")

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message", {})
    if not message:
        return {"ok": True}

    text = message.get("text", "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not chat_id or not text:
        return {"ok": True}

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            await _handle_verify(db, chat_id, parts[1].strip())
        else:
            await _send(
                chat_id,
                "안녕하세요! KYUNGSA 경매 알림 봇입니다.\n\n"
                "kyungsa.com 에서 로그인 후 텔레그램 연동 메뉴에서\n"
                "인증 코드를 발급받아 아래 형식으로 입력해주세요.\n\n"
                "/start 123456",
            )
    elif text == "/stop":
        await _handle_disconnect(db, chat_id)
    elif text == "/status":
        await _handle_status(db, chat_id)
    else:
        await _send(chat_id, "명령어: /stop (연동 해제), /status (연동 정보 확인)")

    return {"ok": True}


async def _handle_verify(db: Session, chat_id: str, code: str) -> None:
    """인증 코드 검증 후 chat_id 연동"""
    now = datetime.now(timezone.utc)

    # 코드 조회
    verification = (
        db.query(TelegramVerification)
        .filter(TelegramVerification.code == code)
        .first()
    )

    if not verification:
        await _send(chat_id, "인증 코드가 올바르지 않습니다.\nkyungsa.com에서 코드를 다시 발급받아 주세요.")
        return

    if verification.expires_at.replace(tzinfo=timezone.utc) < now:
        db.delete(verification)
        db.commit()
        await _send(chat_id, "인증 코드가 만료되었습니다 (10분 유효).\nkyungsa.com에서 코드를 다시 발급받아 주세요.")
        return

    # 유저 업데이트
    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        await _send(chat_id, "연동 실패: 사용자를 찾을 수 없습니다.")
        return

    user.telegram_chat_id = chat_id
    user.telegram_verified_at = now
    db.delete(verification)
    db.commit()

    logger.info("텔레그램 연동 완료: user_id=%s chat_id=%s", user.id, chat_id)
    await _send(
        chat_id,
        f"✅ 연동 완료!\n\n"
        f"계정: {user.email}\n"
        f"저장한 검색 조건이 매칭되면 여기로 알림이 옵니다.\n\n"
        f"/stop 으로 언제든 연동 해제할 수 있습니다.",
    )


async def _handle_disconnect(db: Session, chat_id: str) -> None:
    """연동 해제"""
    user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    if not user:
        await _send(chat_id, "연동된 계정이 없습니다.")
        return
    user.telegram_chat_id = None
    user.telegram_verified_at = None
    db.commit()
    await _send(chat_id, "알림 연동이 해제되었습니다.")


async def _handle_status(db: Session, chat_id: str) -> None:
    """연동 상태 조회"""
    user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    if not user:
        await _send(chat_id, "연동된 계정이 없습니다.\nkyungsa.com에서 연동해주세요.")
        return
    saved_count = len(user.saved_searches)
    await _send(
        chat_id,
        f"📊 연동 정보\n"
        f"계정: {user.email}\n"
        f"저장된 검색 조건: {saved_count}개\n\n"
        f"/stop 으로 연동 해제",
    )
