"""등기부등본 Hard Stop 룰 정의

등기부등본 분석 시 즉시 제외(REJECT) 사유 8종.
canceled=True인 이벤트는 매칭하지 않는다.

필드 규칙:
- event_types: EventType 목록. 하나라도 매칭되면 탐지.
- keywords: raw_text 포함 여부 검사.
- exclude_keywords: 매칭 후 이 키워드가 있으면 제외 (HS006 담보가등기 제외에 사용).
- requires_before_base: True이면 말소기준권리 이전 설정 이벤트만 Hard Stop (HS007~008).
"""

from app.models.registry import EventType


HARD_STOP_RULES: list[dict] = [
    {
        "id": "HS001",
        "name": "예고등기",
        "description": "예고등기가 존재합니다. 소유권 분쟁 가능성이 높아 전문가 상담이 필요합니다.",
        "event_types": [EventType.PRELIMINARY_NOTICE],
        "keywords": ["예고등기"],
    },
    {
        "id": "HS002",
        "name": "신탁등기",
        "description": "신탁등기가 존재합니다. 수탁자와의 관계 확인이 필요하며 권리관계가 복잡합니다.",
        "event_types": [EventType.TRUST],
        "keywords": ["신탁"],
    },
    {
        "id": "HS003",
        "name": "가처분",
        "description": "가처분등기가 존재합니다. 소유권 이전에 제한이 있을 수 있습니다.",
        "event_types": [EventType.PROVISIONAL_DISPOSITION],
        "keywords": ["가처분", "처분금지"],
    },
    {
        "id": "HS004",
        "name": "환매특약",
        "description": "환매특약이 존재합니다. 일정 기간 내 원소유자가 환매할 수 있습니다.",
        "event_types": [EventType.REPURCHASE],
        "keywords": ["환매", "환매특약"],
    },
    {
        "id": "HS005",
        "name": "법정지상권",
        "description": "법정지상권 관련 기재가 있습니다. 토지와 건물의 소유자 불일치를 확인하세요.",
        "event_types": [],
        "keywords": ["법정지상권"],
    },
    {
        "id": "HS006",
        "name": "소유권이전청구권가등기",
        "description": (
            "소유권이전청구권 가등기가 존재합니다. "
            "본등기 시 현재 소유자가 소유권을 잃을 수 있습니다."
        ),
        "event_types": [EventType.PROVISIONAL_REGISTRATION],
        "keywords": ["가등기"],
        "exclude_keywords": ["담보"],  # 담보가등기(말소 대상)는 Hard Stop 아님
    },
    {
        "id": "HS007",
        "name": "인수되는지상권",
        "description": (
            "말소기준권리 이전에 설정된 지상권이 있습니다. "
            "매수인이 그 부담을 인수하므로 건물 철거·임료 청구에 노출됩니다."
        ),
        "event_types": [EventType.SUPERFICIES],
        "keywords": ["지상권"],
        "requires_before_base": True,  # 말소기준 이전 설정만 Hard Stop
    },
    {
        "id": "HS008",
        "name": "인수되는지역권",
        "description": (
            "말소기준권리 이전에 설정된 지역권이 있습니다. "
            "매수인이 해당 용익 제한을 인수합니다."
        ),
        "event_types": [EventType.EASEMENT],
        "keywords": ["지역권"],
        "requires_before_base": True,  # 말소기준 이전 설정만 Hard Stop
    },
]
