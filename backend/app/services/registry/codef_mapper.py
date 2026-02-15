"""CODEF JSON 응답 → RegistryDocument 변환

CODEF 등기부등본 API 응답(resRegisterEntriesList)을
기존 RegistryDocument 모델로 매핑한다.
RegistryParser의 정규식/분류 로직을 재사용한다.

실제 CODEF 응답 구조:
  resRegistrationHisList → 전체 등기 이력 (표제부 + 갑구 + 을구)
  resRegistrationSumList → 요약 (소유지분현황, 공시지가, 토지이용계획)
  각 섹션의 resContentsList:
    resType2="1" → 헤더 행 (순위번호, 등기목적, 접수, ...)
    resType2="2" → 데이터 행
    resDetailList[i].resNumber → 컬럼 위치 (0~4)
"""

import logging
import re

from app.models.registry import (
    Confidence,
    RegistryDocument,
    RegistryEvent,
    SectionType,
    TitleSection,
)
from app.services.parser.registry_parser import (
    RegistryParser,
    _RE_AMOUNT,
    _RE_AREA,
    _RE_DATE,
    _RE_HOLDER,
    _RE_RECEIPT_NO,
)

logger = logging.getLogger(__name__)

# 등기목적 추출용 패턴: resContents 앞부분의 한글 키워드
_RE_PURPOSE = re.compile(
    r"^(소유권보존|소유권이전|근저당권말소|근저당권이전|근저당권설정"
    r"|임의경매개시결정|강제경매개시결정|경매개시결정"
    r"|전세권설정|가처분|처분금지|가압류|압류"
    r"|예고등기|신탁|환매특약|환매|경정|말소"
    r"|[\w]+(?:말소|설정|이전|변경))"
)

# 갑구/을구 컬럼 매핑
COL_RANK = "0"       # 순위번호
COL_PURPOSE = "1"    # 등기목적
COL_RECEIPT = "2"    # 접수 (접수일 + 접수번호)
COL_CAUSE = "3"      # 등기원인
COL_HOLDER = "4"     # 권리자 및 기타사항


class CodefRegistryMapper:
    """CODEF API JSON 응답 → RegistryDocument 변환"""

    def map_response(self, data: dict) -> RegistryDocument:
        """CODEF JSON 전체 응답 → RegistryDocument

        Args:
            data: CODEF API 응답 dict (resRegisterEntriesList 포함)

        Returns:
            RegistryDocument (source="codef")
        """
        warnings: list[str] = []
        entries = data.get("resRegisterEntriesList", [])

        if not entries:
            warnings.append("CODEF 응답에 등기 데이터가 없습니다")
            return RegistryDocument(
                source="codef",
                parse_confidence=Confidence.LOW,
                parse_warnings=warnings,
            )

        entry = entries[0]

        # 1. 표제부 파싱: resRegistrationHisList에서 표제부 찾기
        title = self._parse_title_from_history(entry)
        # fallback: resRealty에서 파싱
        if title.address is None:
            title = self._parse_realty(entry)

        # 2. 갑구/을구 이벤트: resRegistrationHisList에서 추출
        all_events = self._parse_events_from_history(
            entry.get("resRegistrationHisList", [])
        )

        # 3. 섹션별 분리
        gapgu = [e for e in all_events if e.section == SectionType.GAPGU]
        eulgu = [e for e in all_events if e.section == SectionType.EULGU]

        # 4. 신뢰도
        confidence = Confidence.HIGH
        if not all_events:
            confidence = Confidence.LOW
            warnings.append("파싱된 이벤트가 없습니다")
        elif warnings:
            confidence = Confidence.MEDIUM

        return RegistryDocument(
            title=title,
            gapgu_events=gapgu,
            eulgu_events=eulgu,
            all_events=all_events,
            parse_confidence=confidence,
            parse_warnings=warnings,
            source="codef",
        )

    def _parse_events_from_history(
        self, history_list: list[dict]
    ) -> list[RegistryEvent]:
        """resRegistrationHisList → 갑구/을구 이벤트 리스트 (표제부 제외)"""
        events: list[RegistryEvent] = []

        for section_dict in history_list:
            res_type = section_dict.get("resType", "")

            # 표제부는 건물 정보 → 이벤트가 아니므로 스킵
            if "표제부" in res_type:
                continue

            section_type = self._detect_section_type(res_type)
            if section_type is None:
                logger.warning("알 수 없는 섹션 타입: %s", res_type)
                continue

            for content_item in section_dict.get("resContentsList", []):
                # 헤더 행(resType2="1")은 스킵
                if content_item.get("resType2") == "1":
                    continue

                event = self._parse_tabular_row(
                    content_item, section_type
                )
                if event is not None:
                    events.append(event)

        # 접수일 기준 정렬
        events.sort(key=lambda e: e.accepted_at or "")
        return events

    def _parse_tabular_row(
        self,
        content: dict,
        section: SectionType,
    ) -> RegistryEvent | None:
        """테이블 형식 데이터 행 → RegistryEvent

        CODEF 실제 응답에서 각 행은 컬럼별 resDetailList를 가짐:
          col 0: 순위번호
          col 1: 등기목적
          col 2: 접수 (날짜 + 접수번호)
          col 3: 등기원인
          col 4: 권리자 및 기타사항
        """
        # resDetailList를 컬럼 번호로 인덱싱
        columns: dict[str, str] = {}
        for detail in content.get("resDetailList", []):
            col_no = str(detail.get("resNumber", ""))
            col_text = detail.get("resContents", "")
            columns[col_no] = col_text

        # 순위번호
        rank_str = columns.get(COL_RANK, "")
        rank_no: int | None = None
        try:
            rank_no = int(rank_str)
        except (ValueError, TypeError):
            pass

        # 등기목적
        purpose_text = columns.get(COL_PURPOSE, "")
        if not purpose_text.strip():
            return None

        purpose = self._extract_purpose(purpose_text)
        event_type = RegistryParser._classify_event_type(purpose)

        # 접수 (날짜 + 접수번호)
        receipt_text = columns.get(COL_RECEIPT, "")
        accepted_at = None
        receipt_no = None

        date_match = _RE_DATE.search(receipt_text)
        if date_match:
            y, m, d = date_match.groups()
            accepted_at = f"{y}.{int(m):02d}.{int(d):02d}"

        receipt_match = _RE_RECEIPT_NO.search(receipt_text)
        if receipt_match:
            receipt_no = receipt_match.group(1)

        # 등기원인
        cause_text = columns.get(COL_CAUSE, "")

        # 권리자 및 기타사항
        holder_text = columns.get(COL_HOLDER, "")

        # 금액: 권리자 + 등기원인에서 추출
        combined_text = f"{holder_text} {cause_text}"
        amount = RegistryParser._extract_amount(combined_text)

        # 권리자
        holder = RegistryParser._extract_holder(holder_text)

        # 전체 raw_text 구성
        raw_text = " ".join(
            v for v in columns.values() if v.strip()
        )

        # 말소 감지: 등기목적에 "말소" 포함
        is_canceled = RegistryParser._detect_canceled(purpose, raw_text)

        return RegistryEvent(
            section=section,
            rank_no=rank_no,
            purpose=purpose,
            event_type=event_type,
            accepted_at=accepted_at,
            receipt_no=receipt_no,
            cause=cause_text if cause_text.strip() else None,
            holder=holder,
            amount=amount,
            canceled=is_canceled,
            raw_text=raw_text,
        )

    def _parse_title_from_history(self, entry: dict) -> TitleSection:
        """resRegistrationHisList의 표제부 → TitleSection"""
        for section_dict in entry.get("resRegistrationHisList", []):
            if "표제부" not in section_dict.get("resType", ""):
                continue

            address = None
            structure = None
            area = None
            raw_parts: list[str] = []

            for content_item in section_dict.get("resContentsList", []):
                # 헤더 행 스킵
                if content_item.get("resType2") == "1":
                    continue

                columns: dict[str, str] = {}
                for detail in content_item.get("resDetailList", []):
                    col_no = str(detail.get("resNumber", ""))
                    columns[col_no] = detail.get("resContents", "")

                # col 2: 소재지번 → 주소
                addr_text = columns.get("2", "")
                if addr_text and not address:
                    # 줄바꿈을 공백으로 치환
                    address = addr_text.replace("\n", " ").strip()

                # col 3: 건물내역 → 구조, 면적
                building_text = columns.get("3", "")
                if building_text:
                    raw_parts.append(building_text)
                    # 면적 추출
                    area_match = _RE_AREA.search(building_text)
                    if area_match:
                        area = float(area_match.group(1))
                    # 구조 추출 ("~구조" 또는 "~조")
                    for line in building_text.split("\n"):
                        line = line.strip()
                        if "구조" in line or (line.endswith("조") and len(line) > 2):
                            structure = line
                            break

            raw_text = " ".join(raw_parts)
            return TitleSection(
                address=address,
                building_type=None,
                structure=structure,
                area=area,
                raw_text=raw_text,
            )

        # 표제부가 없으면 빈 TitleSection
        return TitleSection(raw_text="")

    def _parse_realty(self, entry: dict) -> TitleSection:
        """resRealty 텍스트 → TitleSection (fallback)"""
        realty_text = entry.get("resRealty", "")

        address = None
        structure = None
        area = None

        if realty_text:
            # [건물] 또는 [집합건물] 접두사 제거
            clean_text = re.sub(r"^\[.*?\]\s*", "", realty_text)

            # 면적 추출
            area_match = _RE_AREA.search(clean_text)
            if area_match:
                area = float(area_match.group(1))
                pre_area = clean_text[:area_match.start()].strip()
                tokens = pre_area.rsplit(maxsplit=1)
                if len(tokens) > 1 and "조" in tokens[-1]:
                    structure = tokens[-1]

            if area_match:
                addr_part = clean_text[:area_match.start()].strip()
                if structure:
                    addr_part = addr_part[: addr_part.rfind(structure)].strip()
                address = addr_part if addr_part else clean_text
            else:
                address = clean_text

        return TitleSection(
            address=address,
            building_type=None,
            structure=structure,
            area=area,
            raw_text=realty_text,
        )

    @staticmethod
    def _detect_section_type(res_type: str) -> SectionType | None:
        """resType 텍스트 → SectionType"""
        if "갑구" in res_type:
            return SectionType.GAPGU
        if "을구" in res_type:
            return SectionType.EULGU
        return None

    @staticmethod
    def _extract_purpose(raw_text: str) -> str:
        """등기목적 텍스트에서 키워드 추출"""
        text = raw_text.strip()

        match = _RE_PURPOSE.match(text)
        if match:
            return match.group(1)

        first_token = text.split()[0] if text else ""
        return first_token
