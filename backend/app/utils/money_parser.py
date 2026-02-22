"""한국어 금액 파서

법원 문서에서 사용되는 다양한 금액 표현을 원(int)으로 변환.
"""

from __future__ import annotations

import re


def parse_korean_money(text: str | None) -> int | None:
    """한국어 금액 표현을 원(int)으로 변환.

    지원 포맷:
        "2천만원" → 20_000_000
        "165만원" → 1_650_000
        "300,000,000" → 300_000_000
        "438,000,000원" → 438_000_000
        "3억원" → 300_000_000
        "4억 3,800만원" → 438_000_000
        "1억 5천만원" → 150_000_000
        "50만원" → 500_000
        "미상" → None
        "" → None
        None → None
        "없음" → 0

    Returns:
        파싱된 금액(원) 또는 None (파싱 불가)
    """
    if text is None:
        return None

    text = text.strip()

    if not text:
        return None

    if text == "없음":
        return 0

    if text in ("미상", "-", "불명"):
        return None

    # 순수 숫자 (쉼표/공백/원 제거)
    cleaned = text.replace(",", "").replace(" ", "").replace("원", "")
    if cleaned.isdigit():
        return int(cleaned)

    # 한글 금액 파싱: 억/천만/만/천 단위 분리
    total = _parse_korean_units(text)
    return total if total is not None and total > 0 else None


# 한글 숫자 매핑
_KOREAN_DIGITS = {
    "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
    "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10,
}


def _parse_number(s: str) -> int | None:
    """숫자 문자열(쉼표 포함) 또는 한글 숫자를 int로 변환."""
    s = s.strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    if s.isdigit():
        return int(s)
    # 한글 숫자: "삼" → 3 등 (단일 자리만)
    if s in _KOREAN_DIGITS:
        return _KOREAN_DIGITS[s]
    return None


def _parse_korean_units(text: str) -> int | None:
    """억/천만/만/천 단위의 한글 금액을 파싱."""
    text = text.replace(",", "").replace(" ", "").replace("원", "")

    total = 0
    found = False

    # 억 단위: "N억" 또는 "억"
    m = re.search(r"(\d+)억", text)
    if m:
        total += int(m.group(1)) * 100_000_000
        found = True
    elif "억" in text:
        # "억" 앞에 숫자가 없으면 1억
        total += 100_000_000
        found = True

    # 천만 단위: "N천만" — "만" 앞에 "천"이 있는 패턴
    m = re.search(r"(\d+)천만", text)
    if m:
        total += int(m.group(1)) * 10_000_000
        found = True
    elif "천만" in text:
        total += 10_000_000
        found = True

    # 만 단위: "N만" (단, "천만"은 이미 처리됨)
    # "천만" 제거 후 "만" 검색
    text_no_cheonman = re.sub(r"\d*천만", "", text)
    m = re.search(r"(\d+)만", text_no_cheonman)
    if m:
        total += int(m.group(1)) * 10_000
        found = True
    elif "만" in text_no_cheonman and "천만" not in text:
        total += 10_000
        found = True

    # 천 단위 (만 없이 단독): "N천" — 단, "N천만"은 제외
    text_no_man = re.sub(r"\d*천만", "", text)
    text_no_man = re.sub(r"\d*만", "", text_no_man)
    m = re.search(r"(\d+)천", text_no_man)
    if m:
        total += int(m.group(1)) * 1_000
        found = True

    return total if found else None
