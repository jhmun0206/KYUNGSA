"""텔레그램 알림 전송

배치 수집 완료 후 신규 A/B등급 물건 요약을 텔레그램으로 전송한다.
python-telegram-bot 불필요, httpx로 직접 Bot API 호출.

환경변수:
  TELEGRAM_BOT_TOKEN — BotFather에서 발급받은 토큰
  TELEGRAM_CHAT_ID — 알림 받을 채팅 ID (개인 채팅 또는 그룹)
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send_telegram(message: str) -> bool:
    """텔레그램 메시지 전송

    Returns:
        True면 전송 성공, False면 실패 (환경변수 미설정 포함)
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        logger.debug("텔레그램 알림 스킵 (토큰/채팅ID 미설정)")
        return False

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("텔레그램 알림 전송 성공")
            return True
        logger.warning("텔레그램 알림 실패: %d %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.warning("텔레그램 알림 전송 오류: %s", e)
        return False


def send_to_chat(chat_id: str, message: str) -> bool:
    """특정 chat_id로 텔레그램 메시지 발송 (개인 알림용)"""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        return False

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning("개인 알림 발송 실패 chat_id=%s: %d %s", chat_id, resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.warning("개인 알림 발송 오류 chat_id=%s: %s", chat_id, e)
        return False


def send_personal_alert(
    chat_id: str,
    search_name: str,
    matched_auctions: list[dict],
) -> bool:
    """저장 검색 매칭 개인 알림 (상위 5건)"""
    if not matched_auctions:
        return False

    grade_emoji = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴"}
    lines = [f"🔔 <b>[{search_name}]</b> 신규 매칭 {len(matched_auctions)}건\n"]

    for i, a in enumerate(matched_auctions[:5], 1):
        grade = a.get("grade") or "-"
        emoji = grade_emoji.get(grade, "⚫")
        addr = (a.get("address") or "")[:30]
        min_bid = a.get("minimum_bid") or 0
        if min_bid >= 100_000_000:
            bid_str = f"{min_bid // 100_000_000}억"
        else:
            bid_str = f"{min_bid // 10_000}만"
        case_number = a.get("case_number", "")
        lines.append(
            f"{i}. {emoji} {grade}등급 | {bid_str}\n"
            f"   {addr}\n"
            f'   <a href="https://kyungsa.com/auction/{case_number}">{case_number}</a>'
        )

    return send_to_chat(chat_id, "\n".join(lines))


def format_batch_summary(
    *,
    court_code: str,
    court_label: str,
    total_searched: int,
    new_count: int,
    new_a: int,
    new_b: int,
    errors: int,
) -> str:
    """배치 수집 결과를 텔레그램 메시지 형식으로 변환"""
    lines = [
        "📊 <b>KYUNGSA 일일 수집 완료</b>",
        f"🏛 {court_label} ({court_code})",
        "━━━━━━━━━━━━━━━━━━",
        f"📌 총 검색: {total_searched}건",
        f"🆕 신규 저장: {new_count}건",
    ]
    if new_a > 0 or new_b > 0:
        lines.append(f"⭐ 신규 A등급: {new_a}건")
        lines.append(f"🔵 신규 B등급: {new_b}건")
    if errors > 0:
        lines.append(f"⚠️ 에러: {errors}건")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append('🔗 <a href="https://kyungsa.com/search?grade=A,B">A/B등급 보기</a>')
    return "\n".join(lines)
