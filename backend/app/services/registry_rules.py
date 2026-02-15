"""등기부등본 Hard Stop 룰 정의

등기부등본 분석 시 즉시 제외(REJECT) 사유 5종.
canceled=True인 이벤트는 매칭하지 않는다.
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
]
