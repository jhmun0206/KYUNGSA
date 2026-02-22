"""한국어 날짜 파서

법원 문서에서 사용되는 다양한 날짜 표현을 date 객체로 변환.
"""

from __future__ import annotations

import re
from datetime import date


def parse_korean_date(text: str | None) -> date | None:
    """한국어 날짜 표현을 date 객체로 변환.

    지원 포맷:
        "2011.08.23" → date(2011, 8, 23)
        "2021.04.13." → date(2021, 4, 13)
        "2022년12월09일" → date(2022, 12, 9)
        "2022년12월09일16시10분" → date(2022, 12, 9)
        "미상" → None
        "" → None
        None → None

    Returns:
        파싱된 date 또는 None
    """
    if text is None:
        return None

    text = text.strip()

    if not text or text in ("미상", "-", "불명"):
        return None

    # 패턴 1: "YYYY.MM.DD" (마침표 포함/미포함)
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 패턴 2: "YYYY년MM월DD일" (시분 등 뒤에 붙을 수 있음)
    m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 패턴 3: "YYYY-MM-DD" (ISO 형식)
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    """유효하지 않은 날짜는 None 반환."""
    try:
        return date(year, month, day)
    except ValueError:
        return None
