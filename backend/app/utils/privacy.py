"""개인정보 마스킹 유틸리티

법원 문서의 이름 등 개인정보를 마스킹하여 저장.
"""

from __future__ import annotations


def mask_name(name: str | None) -> str:
    """이름을 마스킹하여 반환.

    규칙:
        "김미미" → "김OO"
        "이상익" → "이OO"
        "김란" → "김O"
        "김미미미" → "김OOO"
        "미상" → "미상"
        "" → ""
        None → ""
    """
    if name is None:
        return ""

    name = name.strip()

    if not name or name in ("미상", "-", "불명"):
        return name

    if len(name) < 2:
        return name

    return name[0] + "O" * (len(name) - 1)
