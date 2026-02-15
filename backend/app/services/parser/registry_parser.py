"""등기부등본 PDF/텍스트 → RegistryDocument 파싱

등기부등본 텍스트를 표제부/갑구/을구로 분리하고,
각 섹션에서 등기 이벤트를 추출하여 RegistryDocument를 생성한다.

파싱 전략:
- 행 기반 텍스트 파싱 (표 파싱 라이브러리 사용 금지)
- 순위번호를 이벤트 경계로 사용
- 정규식으로 필드 추출
- raw_text 반드시 보존
- LLM 호출 없음, 100% 룰/정규식 기반
"""

import logging
import re

from app.models.registry import (
    Confidence,
    EventType,
    RegistryDocument,
    RegistryEvent,
    SectionType,
    TitleSection,
)

logger = logging.getLogger(__name__)

# EventType 매핑 테이블 (purpose 키워드 → EventType)
_EVENT_TYPE_MAP: list[tuple[str, EventType]] = [
    ("소유권보존", EventType.OWNERSHIP_PRESERVATION),
    ("소유권이전", EventType.OWNERSHIP_TRANSFER),
    ("근저당권말소", EventType.MORTGAGE_CANCEL),
    ("근저당권이전", EventType.MORTGAGE_TRANSFER),
    ("근저당권설정", EventType.MORTGAGE),
    ("임의경매개시결정", EventType.AUCTION_START),
    ("강제경매개시결정", EventType.AUCTION_START),
    ("경매개시결정", EventType.AUCTION_START),
    ("전세권설정", EventType.LEASE_RIGHT),
    ("가처분", EventType.PROVISIONAL_DISPOSITION),
    ("처분금지", EventType.PROVISIONAL_DISPOSITION),
    ("가압류", EventType.PROVISIONAL_SEIZURE),
    ("압류", EventType.SEIZURE),
    ("예고등기", EventType.PRELIMINARY_NOTICE),
    ("신탁", EventType.TRUST),
    ("환매특약", EventType.REPURCHASE),
    ("환매", EventType.REPURCHASE),
    ("경정", EventType.CORRECTION),
    ("말소", EventType.CANCEL),
]

# 정규식 패턴
_RE_DATE = re.compile(
    r"(\d{4})년\s?(\d{1,2})월\s?(\d{1,2})일"
)
_RE_RECEIPT_NO = re.compile(r"제(\d+)호")
_RE_AMOUNT = re.compile(r"금\s?([\d,]+)원")
_RE_HOLDER = re.compile(
    r"(?:소유자|근저당권자|채권자|전세권자|권리자|수탁자)\s+(.+?)(?:\s|$)"
)
_RE_AREA = re.compile(r"([\d.]+)\s*㎡")
_RE_RANK_LINE = re.compile(r"^(\d+)\s*\|", re.MULTILINE)

# 섹션 구분자 패턴
_RE_SECTION_TITLE = re.compile(r"【\s*표제부\s*】")
_RE_SECTION_GAPGU = re.compile(r"【\s*갑\s*구\s*】")
_RE_SECTION_EULGU = re.compile(r"【\s*을\s*구\s*】")


class RegistryParser:
    """등기부등본 PDF/텍스트 → RegistryDocument 파싱"""

    def parse_pdf(self, pdf_path: str) -> RegistryDocument:
        """PDF 파일 → RegistryDocument"""
        text = self._extract_text_from_pdf(pdf_path)
        return self.parse_text(text)

    def parse_text(self, text: str) -> RegistryDocument:
        """텍스트 → RegistryDocument (테스트/디버깅용 핵심 메서드)"""
        warnings: list[str] = []

        # 1. 섹션 분리
        sections = self._split_sections(text)

        # 2. 표제부 파싱
        title = None
        if sections["title"]:
            title = self._parse_title_section(sections["title"])

        # 3. 갑구 파싱
        gapgu_events: list[RegistryEvent] = []
        if sections["gapgu"]:
            gapgu_events = self._parse_events(
                sections["gapgu"], SectionType.GAPGU
            )
        else:
            warnings.append("갑구 섹션을 찾을 수 없습니다")

        # 4. 을구 파싱
        eulgu_events: list[RegistryEvent] = []
        if sections["eulgu"]:
            eulgu_events = self._parse_events(
                sections["eulgu"], SectionType.EULGU
            )

        # 5. 전체 이벤트 정렬 (접수일 기준)
        all_events = sorted(
            gapgu_events + eulgu_events,
            key=lambda e: e.accepted_at or "",
        )

        # 6. 신뢰도 판단
        confidence = Confidence.HIGH
        if warnings:
            confidence = Confidence.MEDIUM
        if not gapgu_events and not eulgu_events:
            confidence = Confidence.LOW
            warnings.append("파싱된 이벤트가 없습니다")

        return RegistryDocument(
            title=title,
            gapgu_events=gapgu_events,
            eulgu_events=eulgu_events,
            all_events=all_events,
            parse_confidence=confidence,
            parse_warnings=warnings,
        )

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """PyMuPDF(fitz)로 텍스트 추출. 실패 시 pdfplumber fallback."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(pdf_path)
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            return "\n".join(pages)
        except ImportError:
            logger.warning("PyMuPDF 미설치, pdfplumber fallback 시도")
        except Exception as e:
            logger.warning("PyMuPDF 텍스트 추출 실패: %s, pdfplumber fallback", e)

        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n".join(pages)
        except ImportError:
            raise RuntimeError(
                "PDF 파싱에 PyMuPDF 또는 pdfplumber가 필요합니다. "
                "pip install PyMuPDF 또는 pip install pdfplumber"
            )

    def _split_sections(self, text: str) -> dict[str, str]:
        """텍스트를 표제부/갑구/을구로 분리"""
        result: dict[str, str] = {"title": "", "gapgu": "", "eulgu": ""}

        # 각 섹션 시작 위치 찾기
        title_match = _RE_SECTION_TITLE.search(text)
        gapgu_match = _RE_SECTION_GAPGU.search(text)
        eulgu_match = _RE_SECTION_EULGU.search(text)

        positions: list[tuple[str, int]] = []
        if title_match:
            positions.append(("title", title_match.start()))
        if gapgu_match:
            positions.append(("gapgu", gapgu_match.start()))
        if eulgu_match:
            positions.append(("eulgu", eulgu_match.start()))

        # 위치 순 정렬
        positions.sort(key=lambda x: x[1])

        # 각 섹션 텍스트 추출
        for i, (name, start) in enumerate(positions):
            if i + 1 < len(positions):
                end = positions[i + 1][1]
            else:
                end = len(text)
            result[name] = text[start:end]

        return result

    def _parse_title_section(self, text: str) -> TitleSection:
        """표제부 텍스트 → TitleSection"""
        # 소재지번 및 건물번호에서 주소 추출
        # 표제부 데이터 행에서 추출 (순위번호 | ... 패턴)
        address = None
        building_type = None
        structure = None
        area = None

        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            # 헤더 행 건너뛰기
            if not line or "표시번호" in line or "【" in line:
                continue
            # 데이터 행: "1 | | 서울특별시 ... | 철근콘크리트조 85.12㎡ | |"
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                # 소재지번 (보통 3번째 셀)
                for part in parts:
                    if part and ("시" in part or "도" in part) and len(part) > 5:
                        address = part
                        break
                # 건물내역 (구조 + 면적)
                for part in parts:
                    area_match = _RE_AREA.search(part)
                    if area_match:
                        area = float(area_match.group(1))
                        # 면적 앞의 텍스트가 구조
                        struct_text = part[:area_match.start()].strip()
                        if struct_text:
                            structure = struct_text
                        break

        return TitleSection(
            address=address,
            building_type=building_type,
            structure=structure,
            area=area,
            raw_text=text,
        )

    def _parse_events(
        self, text: str, section: SectionType
    ) -> list[RegistryEvent]:
        """갑구/을구 텍스트 → RegistryEvent 리스트"""
        events: list[RegistryEvent] = []

        # 순위번호 라인 찾기 (데이터 행만, 헤더 제외)
        lines = text.split("\n")
        data_lines: list[str] = []
        header_passed = False
        for line in lines:
            stripped = line.strip()
            if "순위번호" in stripped:
                header_passed = True
                continue
            if header_passed and stripped:
                data_lines.append(stripped)

        if not data_lines:
            return events

        # 순위번호별로 이벤트 블록 분리
        event_blocks: list[tuple[int, str]] = []
        current_rank: int | None = None
        current_lines: list[str] = []

        for line in data_lines:
            # 순위번호로 시작하는 행 감지
            rank_match = re.match(r"^(\d+)\s*\|", line)
            if rank_match:
                # 이전 블록 저장
                if current_rank is not None and current_lines:
                    event_blocks.append(
                        (current_rank, "\n".join(current_lines))
                    )
                current_rank = int(rank_match.group(1))
                current_lines = [line]
            elif current_rank is not None:
                # 연속 행 추가
                current_lines.append(line)

        # 마지막 블록 저장
        if current_rank is not None and current_lines:
            event_blocks.append((current_rank, "\n".join(current_lines)))

        # 각 블록 파싱
        for rank_no, block_text in event_blocks:
            event = self._parse_single_event(block_text, rank_no, section)
            events.append(event)

        return events

    def _parse_single_event(
        self, text: str, rank_no: int, section: SectionType
    ) -> RegistryEvent:
        """단일 이벤트 블록 → RegistryEvent"""
        # 파이프 구분 셀 분리
        cells = [c.strip() for c in text.split("|")]
        full_text = " ".join(cells)

        # 등기목적 추출 (보통 2번째 셀)
        purpose = cells[1] if len(cells) > 1 else ""

        # EventType 매핑
        event_type = self._classify_event_type(purpose)

        # 접수일자 추출
        accepted_at = None
        date_match = _RE_DATE.search(full_text)
        if date_match:
            y, m, d = date_match.groups()
            accepted_at = f"{y}.{int(m):02d}.{int(d):02d}"

        # 접수번호 추출
        receipt_no = None
        receipt_match = _RE_RECEIPT_NO.search(full_text)
        if receipt_match:
            receipt_no = receipt_match.group(1)

        # 등기원인 추출 (보통 4번째 셀)
        cause = cells[3] if len(cells) > 3 else None

        # 금액 추출
        amount = self._extract_amount(full_text)

        # 권리자 추출
        holder = self._extract_holder(full_text)

        # 말소 감지
        canceled = self._detect_canceled(purpose, full_text)

        return RegistryEvent(
            section=section,
            rank_no=rank_no,
            purpose=purpose,
            event_type=event_type,
            accepted_at=accepted_at,
            receipt_no=receipt_no,
            cause=cause,
            holder=holder,
            amount=amount,
            canceled=canceled,
            raw_text=text,
        )

    @staticmethod
    def _classify_event_type(purpose: str) -> EventType:
        """등기목적 텍스트 → EventType 매핑"""
        purpose_clean = purpose.strip()
        for keyword, etype in _EVENT_TYPE_MAP:
            if keyword in purpose_clean:
                return etype
        return EventType.OTHER

    @staticmethod
    def _extract_amount(text: str) -> int | None:
        """텍스트에서 금액 추출"""
        match = _RE_AMOUNT.search(text)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                return int(amount_str)
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_holder(text: str) -> str | None:
        """텍스트에서 권리자 추출"""
        match = _RE_HOLDER.search(text)
        if match:
            holder = match.group(1).strip()
            # 마스킹 문자나 불필요한 후행 텍스트 정리
            holder = re.split(r"\s{2,}", holder)[0]
            return holder if holder else None
        return None

    @staticmethod
    def _detect_canceled(purpose: str, full_text: str) -> bool:
        """말소 여부 판단"""
        # 등기목적에 "말소"가 포함된 경우
        if "말소" in purpose:
            return True
        # 권리자 및 기타사항에 "말소" 단독 기재
        # (단, "근저당권말소" 같은 목적이 아닌 별도 기재)
        return False
