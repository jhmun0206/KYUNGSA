"""등기부등본 데이터 모델

등기부등본 PDF 파싱 결과와 권리분석 결과를 담는 Pydantic 모델.
MVP 범위: 아파트/오피스텔, 근저당·가압류·경매개시결정 중심.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SectionType(str, Enum):
    """등기부등본 섹션 구분"""

    TITLE = "TITLE"   # 표제부
    GAPGU = "GAPGU"   # 갑구 (소유권)
    EULGU = "EULGU"   # 을구 (소유권 이외)


class EventType(str, Enum):
    """등기 이벤트 종류"""

    OWNERSHIP_TRANSFER = "소유권이전"
    OWNERSHIP_PRESERVATION = "소유권보존"
    SEIZURE = "압류"
    PROVISIONAL_SEIZURE = "가압류"
    PROVISIONAL_DISPOSITION = "가처분"
    MORTGAGE = "근저당권설정"
    MORTGAGE_TRANSFER = "근저당권이전"
    MORTGAGE_CANCEL = "근저당권말소"
    LEASE_RIGHT = "전세권설정"
    AUCTION_START = "경매개시결정"
    PRELIMINARY_NOTICE = "예고등기"
    TRUST = "신탁"
    REPURCHASE = "환매특약"
    PROVISIONAL_REGISTRATION = "가등기"     # 소유권이전청구권 가등기 (HS006)
    SUPERFICIES = "지상권설정"              # 지상권 (HS007)
    EASEMENT = "지역권설정"                 # 지역권 (HS008)
    CANCEL = "말소"
    CORRECTION = "경정"
    OTHER = "기타"


class Confidence(str, Enum):
    """파싱/분석 신뢰도"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RegistryEvent(BaseModel):
    """등기부등본의 개별 등기 이벤트 (핵심 단위)"""

    section: SectionType                    # GAPGU / EULGU
    rank_no: int | None = None              # 순위번호
    purpose: str                            # 등기목적 원문 (예: "근저당권설정")
    event_type: EventType = EventType.OTHER # 정규화된 이벤트 타입
    accepted_at: str | None = None          # 접수일자 (YYYY.MM.DD)
    receipt_no: str | None = None           # 접수번호
    cause: str | None = None                # 등기원인 (예: "2020년3월15일 설정계약")
    holder: str | None = None               # 권리자/소유자 (마스킹 가능)
    amount: int | None = None               # 금액 (채권최고액, 청구금액, 전세금 등)
    canceled: bool = False                  # 말소 여부
    raw_text: str                           # 원문 텍스트 (반드시 보존)


class TitleSection(BaseModel):
    """표제부 파싱 결과"""

    address: str | None = None              # 소재지
    building_type: str | None = None        # 건물 종류
    structure: str | None = None            # 구조
    area: float | None = None               # 면적 (㎡)
    raw_text: str = ""


class RegistryDocument(BaseModel):
    """등기부등본 전체 파싱 결과"""

    title: TitleSection | None = None
    gapgu_events: list[RegistryEvent] = Field(default_factory=list)
    eulgu_events: list[RegistryEvent] = Field(default_factory=list)
    all_events: list[RegistryEvent] = Field(default_factory=list)  # 갑구+을구 접수일 순
    parse_confidence: Confidence = Confidence.HIGH
    parse_warnings: list[str] = Field(default_factory=list)
    source: str = "unknown"                                   # "codef" | "pdf_upload" | "manual"


class RightClassification(str, Enum):
    """권리 분류 결과"""

    EXTINGUISHED = "소멸"   # 매각으로 소멸
    SURVIVING = "인수"      # 매수인이 인수
    UNCERTAIN = "불확실"    # 판단 불가 → 수동 검토


class AnalyzedRight(BaseModel):
    """분석된 개별 권리"""

    event: RegistryEvent
    classification: RightClassification
    reason: str                             # 분류 사유


class HardStopFlag(BaseModel):
    """Hard Stop 탐지 결과"""

    rule_id: str              # "HS001" 등
    name: str                 # "예고등기", "신탁등기" 등
    description: str          # 상세 설명
    event: RegistryEvent      # 트리거한 이벤트


class RegistryAnalysisResult(BaseModel):
    """등기부등본 분석 최종 결과"""

    document: RegistryDocument
    cancellation_base_event: RegistryEvent | None = None  # 말소기준권리
    cancellation_base_reason: str | None = None           # 판단 근거
    extinguished_rights: list[AnalyzedRight] = Field(default_factory=list)
    surviving_rights: list[AnalyzedRight] = Field(default_factory=list)
    uncertain_rights: list[AnalyzedRight] = Field(default_factory=list)
    hard_stop_flags: list[HardStopFlag] = Field(default_factory=list)
    has_hard_stop: bool = False
    confidence: Confidence = Confidence.HIGH
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""                                     # 사람이 읽을 요약
