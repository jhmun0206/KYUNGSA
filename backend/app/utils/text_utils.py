"""텍스트 처리 유틸리티

법원 API 응답의 HTML 태그 제거 등.
"""

from __future__ import annotations

import re


def strip_html(text: str | None) -> str:
    """HTML 태그를 제거하고 공백 정리.

    법원 API 응답의 gdsPossCtt 필드 등에 <br />, <br/> 등이 포함됨.

    Examples:
        "내용...<br />" → "내용..."
        "<b>굵은</b> 텍스트" → "굵은 텍스트"
        None → ""
    """
    if text is None:
        return ""

    # HTML 태그 제거
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # 연속 공백 정리
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
