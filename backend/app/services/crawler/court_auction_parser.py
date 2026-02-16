"""대법원 경매정보 파서

courtauction.go.kr WebSquare API 응답(JSON) 및 HTML 페이지 파싱.
HTTP 클라이언트와 분리하여 단독 테스트 가능.
"""

import logging
import re
from datetime import date, datetime
from typing import Any

from bs4 import BeautifulSoup

from app.models.auction import (
    AppraisalNote,
    AuctionCaseDetail,
    AuctionCaseHistory,
    AuctionCaseListItem,
    AuctionDocuments,
    AuctionPropertyObject,
    AuctionRound,
)

logger = logging.getLogger(__name__)

# WebSquare JSON 응답 필드명 상수
# 검색 결과 (dlt_srchResult)
F_CASE_NO = "srnSaNo"  # 사건번호 (예: "2022타경112176")
F_COURT_CODE = "boCd"  # 법원코드 (예: "B000210")
F_COURT_NAME = "jiwonNm"  # 법원명 (예: "서울중앙지방법원")
F_PROPERTY_SEQ = "maemulSer"  # 물건순서
F_ADDRESS = "printSt"  # 소재지
F_APPRAISED = "gamevalAmt"  # 감정평가액
F_MIN_PRICE = "notifyMinmaePrice1"  # 공고최저매각가격 (1차)
F_MIN_PRICE_ORIG = "minmaePrice"  # 최저매각가격 (전체)
F_USAGE = "dspslUsgNm"  # 물건 용도
F_AUCTION_DATE = "maeGiil"  # 매각기일 (YYYYMMDD)
F_BID_COUNT = "yuchalCnt"  # 유찰횟수
F_STATUS = "mulStatcd"  # 물건상태코드 (01=진행)
F_SA_NO = "saNo"  # 원본 사건번호 (20220130112176)
F_BUILDING_NAME = "buldNm"  # 건물명
F_BUILDING_LIST = "buldList"  # 건물 상세 (층/호)
F_JIN_STAT_CD = "jinstatCd"  # 진행상태코드 (예: "0002100001")

# 물건상태코드 → 한국어 매핑
STATUS_MAP = {
    "01": "진행",
    "02": "매각",
    "03": "유찰",
    "04": "취하",
    "05": "변경",
    "06": "납부",
}

# 경매기일 결과코드 → 한국어 매핑
ROUND_RESULT_MAP = {
    "001": "매각",
    "002": "유찰",
    "003": "진행예정",
    "004": "취소",
    "005": "변경",
    "006": "취하",
}

# 상세 정보 (dma_result) 키 상수
F_DMA_RESULT = "dma_result"
F_CS_BASE_INFO = "csBaseInfo"
F_DSTRT_DEMN_INFO = "dstrtDemnInfo"
F_DSPSL_GDS_DXDY_INFO = "dspslGdsDxdyInfo"
F_GDS_DSPSL_DXDY_LST = "gdsDspslDxdyLst"
F_GDS_DSPSL_OBJCT_LST = "gdsDspslObjctLst"
F_AEE_WEVL_MNPNT_LST = "aeeWevlMnpntLst"
F_CS_PIC_LST = "csPicLst"

# 사진 기본 URL
PHOTO_BASE_URL = "https://www.courtauction.go.kr"

# 캡차 감지 패턴
CAPTCHA_PATTERNS = [
    "captcha",
    "CAPTCHA",
    "자동입력방지",
    "보안문자",
    "robot",
]


class CourtAuctionParser:
    """대법원 경매정보 응답 파서

    WebSquare JSON 응답 또는 HTML을 Pydantic 모델로 변환.
    파싱 실패 시 경고 로그를 남기고 가능한 데이터만 반환한다.
    """

    # === 목록 파싱 ===

    def parse_list_response(
        self, response_data: dict[str, Any]
    ) -> list[AuctionCaseListItem]:
        """검색 결과 JSON → AuctionCaseListItem 목록

        Args:
            response_data: WebSquare JSON 응답 (data 래퍼 제거 후)

        Returns:
            경매 물건 목록 (빈 결과 시 빈 리스트)
        """
        items = response_data.get("dlt_srchResult", [])
        if not items:
            logger.info("검색 결과 없음")
            return []

        results = []
        for item in items:
            try:
                # 유찰횟수 + 1 = 현재 회차
                yuchal = item.get(F_BID_COUNT, "0")
                bid_count = int(yuchal) + 1 if yuchal else 1

                # 최저매각가: notifyMinmaePrice1 우선, 없으면 minmaePrice
                min_price = item.get(F_MIN_PRICE, "")
                if not min_price or min_price == "0":
                    min_price = item.get(F_MIN_PRICE_ORIG, "0")

                case = AuctionCaseListItem(
                    case_number=item.get(F_CASE_NO, ""),
                    court=item.get(F_COURT_NAME, ""),
                    property_type=item.get(F_USAGE, ""),
                    address=self._clean_text(item.get(F_ADDRESS, "")),
                    appraised_value=self._parse_amount(
                        item.get(F_APPRAISED, "0")
                    ),
                    minimum_bid=self._parse_amount(min_price),
                    auction_date=self._parse_date(
                        item.get(F_AUCTION_DATE, "")
                    ),
                    status=STATUS_MAP.get(
                        item.get(F_STATUS, ""), item.get(F_STATUS, "")
                    ),
                    bid_count=bid_count,
                    court_office_code=item.get(F_COURT_CODE, ""),
                    internal_case_number=item.get(F_SA_NO, ""),
                    property_sequence=item.get(F_PROPERTY_SEQ, ""),
                )
                results.append(case)
            except Exception:
                logger.warning("목록 항목 파싱 실패: %s", item.get(F_CASE_NO, "알 수 없음"))
                continue

        logger.info("목록 파싱 완료: %d건", len(results))
        return results

    def parse_list_with_total(
        self, response_data: dict[str, Any]
    ) -> tuple[list[AuctionCaseListItem], int]:
        """검색 결과 JSON → (물건 목록, 전체 건수)

        Args:
            response_data: WebSquare JSON 응답 (data 래퍼 제거 후)

        Returns:
            (경매 물건 목록, 전체 건수) 튜플
        """
        items = self.parse_list_response(response_data)
        total = 0
        page_info = response_data.get("dma_pageInfo", {})
        total_str = page_info.get("totalCnt", "0")
        try:
            total = int(total_str) if total_str else 0
        except (ValueError, TypeError):
            total = len(items)
        return items, total

    def parse_list_html(self, html: str) -> list[AuctionCaseListItem]:
        """목록 페이지 HTML → AuctionCaseListItem 목록 (fallback)

        Args:
            html: 검색 결과 HTML 문자열

        Returns:
            경매 물건 목록
        """
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.Ltbl_list tbody tr")
        if not rows:
            return []

        results = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            try:
                # 사건번호 링크에서 데이터 속성 추출
                link = cells[0].find("a")
                case_number = self._clean_text(cells[0].get_text())

                case = AuctionCaseListItem(
                    case_number=case_number,
                    court="",  # HTML 목록에는 법원명이 별도로 없을 수 있음
                    property_type=self._clean_text(cells[6].get_text()),
                    address=self._clean_text(cells[2].get_text()),
                    appraised_value=self._parse_amount(cells[3].get_text()),
                    minimum_bid=self._parse_amount(cells[4].get_text()),
                    auction_date=self._parse_date(cells[5].get_text()),
                    status=self._clean_text(cells[7].get_text()) if len(cells) > 7 else "",
                )

                # 링크 data 속성에서 법원코드, 물건순서 추출
                if link:
                    case.court = link.get("data-court", "")

                results.append(case)
            except Exception:
                logger.warning("HTML 목록 행 파싱 실패")
                continue

        return results

    # === 상세 파싱 ===

    def _unwrap_dma_result(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """dma_result 래퍼 언래핑

        상세 API 응답은 {dma_result: {csBaseInfo, ...}} 구조.
        dma_result이 있으면 언래핑, 없으면 원본 반환 (하위 호환).
        """
        if F_DMA_RESULT in response_data:
            return response_data[F_DMA_RESULT]
        return response_data

    def parse_detail_response(
        self, response_data: dict[str, Any]
    ) -> AuctionCaseDetail:
        """상세 정보 JSON → AuctionCaseDetail

        Args:
            response_data: WebSquare 상세 응답 ({dma_result: {...}} 또는 직접)

        Returns:
            경매 물건 상세 정보
        """
        dma = self._unwrap_dma_result(response_data)

        cs_info = dma.get(F_CS_BASE_INFO, {})
        prop_info = dma.get(F_DSPSL_GDS_DXDY_INFO, {})
        objects = dma.get(F_GDS_DSPSL_OBJCT_LST, [])
        appraisal_list = dma.get(F_AEE_WEVL_MNPNT_LST, [])
        schedule_list = dma.get(F_GDS_DSPSL_DXDY_LST, [])
        pic_list = dma.get(F_CS_PIC_LST, [])
        demn_info_list = dma.get(F_DSTRT_DEMN_INFO, [])

        # 사건번호: userCsNo 우선, 없으면 csNo에서 생성
        case_number = cs_info.get("userCsNo", "")
        if not case_number:
            case_number = cs_info.get("csNo", "")

        # 소재지: 물건 목록의 첫 번째 userPrintSt 또는 prop_info의 address 관련 필드
        address = ""
        if objects:
            address = objects[0].get("userPrintSt", "")
        if not address:
            # fallback: printSt가 있으면 사용 (이전 호환)
            address = prop_info.get("printSt", "")

        # 물건 객체 파싱
        property_objects = self._parse_property_objects(objects)

        # 면적/층수 (첫 번째 물건에서 추출 → Level 1 호환)
        area_m2 = None
        floor_info = ""
        lot_number = ""
        if property_objects:
            first_obj = property_objects[0]
            area_m2 = first_obj.area_m2
            floor_info = first_obj.building_detail
            lot_number = first_obj.lot_number

        # 감정평가 요점 파싱
        appraisal_notes = self._parse_appraisal_notes(appraisal_list)

        # 매각기일 이력 파싱
        auction_rounds = self._parse_rounds(schedule_list)

        # 사진 URL 추출
        photo_urls = self._extract_photo_urls(pic_list)

        # 배당요구종기
        demn_deadline = None
        if demn_info_list:
            demn_deadline = self._parse_date(
                demn_info_list[0].get("dstrtDemnLstprdYmd", "")
            )

        # 문건 존재 여부
        spec_doc_id = prop_info.get("dspslGdsSpcfcEcdocId", "")
        has_specification = bool(spec_doc_id)
        has_appraisal = bool(appraisal_list)
        spec_date = self._parse_date(prop_info.get("gdsSpcfcWrtYmd", ""))

        # 유찰횟수
        failed_count = self._parse_int(prop_info.get("flbdNcnt", "0"))

        return AuctionCaseDetail(
            # 기본 필드 (AuctionCaseListItem)
            case_number=case_number,
            court=cs_info.get("cortOfcNm", ""),
            property_type=prop_info.get("dspslUsgNm", ""),
            address=self._clean_text(address),
            appraised_value=self._parse_amount(
                prop_info.get("aeeEvlAmt", "0")
            ),
            minimum_bid=self._parse_amount(
                prop_info.get("fstPbancLwsDspslPrc", "0")
            ),
            auction_date=self._parse_date(
                prop_info.get("dspslDxdyYmd", "")
            ),
            status=STATUS_MAP.get(
                prop_info.get("auctnGdsStatCd", ""),
                prop_info.get("auctnGdsStatCd", ""),
            ),
            bid_count=failed_count + 1,
            # 사건 기본정보
            internal_case_number=cs_info.get("csNo", ""),
            case_name=cs_info.get("csNm", ""),
            case_receipt_date=self._parse_date(cs_info.get("csRcptYmd", "")),
            case_start_date=self._parse_date(cs_info.get("csCmdcYmd", "")),
            claim_amount=self._parse_amount(cs_info.get("clmAmt", "0")),
            court_department=cs_info.get("cortAuctnJdbnNm", ""),
            court_phone=cs_info.get("jdbnTelno", ""),
            # 매각 정보
            sale_decision_date=self._parse_date(
                prop_info.get("dspslDcsnDxdyYmd", "")
            ),
            sale_place=prop_info.get("dspslPlcNm", ""),
            deposit_rate=self._parse_int(prop_info.get("prchDposRate", "10")),
            failed_count=failed_count,
            specification_remarks=prop_info.get("gdsSpcfcRmk", "") or "",
            top_priority_mortgage=prop_info.get("tprtyRnkHypthcStngDts", "") or "",
            superficies_info=prop_info.get("sprfcExstcDts", "") or "",
            sale_remarks=prop_info.get("dspslGdsRmk", "") or "",
            # 배당요구종기
            distribution_demand_deadline=demn_deadline,
            # 문건 존재 여부
            has_specification=has_specification,
            has_appraisal=has_appraisal,
            specification_date=spec_date,
            # 하위 데이터
            property_objects=property_objects,
            appraisal_notes=appraisal_notes,
            auction_rounds=auction_rounds,
            photo_urls=photo_urls,
            # API 후속 호출용
            court_office_code=cs_info.get("cortOfcCd", ""),
            property_sequence=prop_info.get("maemulSer", ""),
            # Level 1 호환
            lot_number=lot_number,
            area_m2=area_m2,
            floor=floor_info,
        )

    def parse_detail_html(self, html: str) -> AuctionCaseDetail:
        """상세 페이지 HTML → AuctionCaseDetail (fallback)

        Args:
            html: 상세 페이지 HTML 문자열

        Returns:
            경매 물건 상세 정보
        """
        soup = BeautifulSoup(html, "html.parser")

        # 기본 정보 테이블에서 추출
        case_number = ""
        court = ""
        address = ""
        appraised_value = 0
        minimum_bid = 0

        # 사건번호
        cs_el = soup.find("td", {"id": "csNo"})
        if cs_el:
            case_number = self._clean_text(cs_el.get_text())

        # 법원
        court_el = soup.find("td", {"id": "cortOfcNm"})
        if court_el:
            court = self._clean_text(court_el.get_text())

        # 소재지
        addr_el = soup.find("td", {"id": "printSt"})
        if addr_el:
            address = self._clean_text(addr_el.get_text())

        # 감정가
        appr_el = soup.find("td", {"id": "aeeEvlAmt"})
        if appr_el:
            appraised_value = self._parse_amount(appr_el.get_text())

        # 최저매각가
        min_el = soup.find("td", {"id": "lwsDspslPrc"})
        if min_el:
            minimum_bid = self._parse_amount(min_el.get_text())

        return AuctionCaseDetail(
            case_number=case_number,
            court=court,
            property_type="",
            address=address,
            appraised_value=appraised_value,
            minimum_bid=minimum_bid,
        )

    # === 사건내역 파싱 ===

    def parse_history_response(
        self, response_data: dict[str, Any]
    ) -> AuctionCaseHistory:
        """사건내역 JSON → AuctionCaseHistory

        Args:
            response_data: 상세 응답 데이터 ({dma_result: {...}} 또는 직접)

        Returns:
            회차별 경매 진행 이력
        """
        dma = self._unwrap_dma_result(response_data)

        cs_info = dma.get(F_CS_BASE_INFO, {})
        schedule_list = dma.get(F_GDS_DSPSL_DXDY_LST, [])
        demn_info_list = dma.get(F_DSTRT_DEMN_INFO, [])

        # 사건번호
        case_number = cs_info.get("userCsNo", "") or cs_info.get("csNo", "")

        # 개시결정일
        case_start_date = self._parse_date(cs_info.get("csCmdcYmd", ""))

        # 배당요구종기
        demn_deadline = None
        if demn_info_list:
            demn_deadline = self._parse_date(
                demn_info_list[0].get("dstrtDemnLstprdYmd", "")
            )

        # 매각기일 이력
        rounds = self._parse_rounds(schedule_list)

        return AuctionCaseHistory(
            case_number=case_number,
            case_start_date=case_start_date,
            distribution_demand_deadline=demn_deadline,
            rounds=rounds,
        )

    # === 문건 목록 파싱 ===

    def parse_documents_response(
        self, response_data: dict[str, Any]
    ) -> AuctionDocuments:
        """문건 존재 여부 추출 → AuctionDocuments

        실제 API는 별도 문건 목록 엔드포인트가 없으므로,
        상세 응답의 필드에서 문건 존재 여부를 추론한다.

        Args:
            response_data: 상세 응답 데이터 ({dma_result: {...}} 또는 직접)

        Returns:
            경매 문건 목록 (존재 여부 플래그)
        """
        dma = self._unwrap_dma_result(response_data)

        cs_info = dma.get(F_CS_BASE_INFO, {})
        prop_info = dma.get(F_DSPSL_GDS_DXDY_INFO, {})
        appraisal_list = dma.get(F_AEE_WEVL_MNPNT_LST, [])
        pic_list = dma.get(F_CS_PIC_LST, [])

        case_number = cs_info.get("userCsNo", "") or cs_info.get("csNo", "")

        # 매각물건명세서 존재 여부
        spec_doc_id = prop_info.get("dspslGdsSpcfcEcdocId", "")
        has_specification = bool(spec_doc_id)
        spec_date = self._parse_date(prop_info.get("gdsSpcfcWrtYmd", ""))

        # 감정평가서 존재 여부 (평가 요점이 있으면 감정평가서 존재)
        has_appraisal = bool(appraisal_list)

        # 현황조사서 존재 여부 (사진이 있으면 현황조사 수행됨으로 추정)
        has_status_report = bool(pic_list)

        return AuctionDocuments(
            case_number=case_number,
            has_specification=has_specification,
            has_appraisal=has_appraisal,
            has_status_report=has_status_report,
            specification_date=spec_date,
        )

    # === 하위 파싱 헬퍼 ===

    def _parse_property_objects(
        self, objects: list[dict[str, Any]]
    ) -> list[AuctionPropertyObject]:
        """gdsDspslObjctLst → AuctionPropertyObject 목록"""
        results = []
        for obj in objects:
            try:
                building_info = obj.get("pjbBuldList", "") or ""
                area_m2 = self._extract_area(building_info)

                prop_obj = AuctionPropertyObject(
                    sequence=self._parse_int(obj.get("dspslObjctSeq", "0")),
                    real_estate_type=obj.get("rletDvsDts", "") or "",
                    building_info=building_info,
                    building_detail=obj.get("bldDtlDts", "") or "",
                    building_name=obj.get("bldNm", "") or "",
                    appraised_value=self._parse_amount(
                        obj.get("aeeEvlAmt", "0")
                    ),
                    address=obj.get("userPrintSt", "") or "",
                    lot_number=obj.get("rprsLtnoAddr", "") or "",
                    area_m2=area_m2,
                    x_coord=obj.get("stXcrd", "") or "",
                    y_coord=obj.get("stYcrd", "") or "",
                )
                results.append(prop_obj)
            except Exception:
                logger.warning("물건 객체 파싱 실패: seq=%s", obj.get("dspslObjctSeq", "?"))
                continue
        return results

    def _parse_appraisal_notes(
        self, notes: list[dict[str, Any]]
    ) -> list[AppraisalNote]:
        """aeeWevlMnpntLst → AppraisalNote 목록"""
        results = []
        for note in notes:
            try:
                appraisal = AppraisalNote(
                    sequence=self._parse_int(
                        note.get("aeeWevlMnpntDtlSeq", "0")
                    ),
                    category_code=note.get("aeeWevlMnpntItmCd", "") or "",
                    content=note.get("aeeWevlMnpntCtt", "") or "",
                )
                results.append(appraisal)
            except Exception:
                logger.warning("감정평가 요점 파싱 실패")
                continue
        return results

    def _parse_rounds(
        self, schedule_list: list[dict[str, Any]]
    ) -> list[AuctionRound]:
        """gdsDspslDxdyLst → AuctionRound 목록"""
        rounds = []
        for idx, item in enumerate(schedule_list, start=1):
            try:
                result_code = item.get("auctnDxdyRsltCd", "")
                result_name = ROUND_RESULT_MAP.get(result_code, result_code)

                winning_bid = None
                winning_str = item.get("dspslAmt")
                if winning_str:
                    winning_bid = self._parse_amount(str(winning_str))

                round_info = AuctionRound(
                    round_number=idx,
                    round_date=self._parse_date(item.get("dxdyYmd", "")),
                    minimum_bid=self._parse_amount(
                        item.get("tsLwsDspslPrc", "0")
                    ),
                    result=result_name,
                    result_code=result_code,
                    winning_bid=winning_bid,
                    sale_time=item.get("dxdyHm", "") or "",
                    sale_place=item.get("dxdyPlcNm", "") or "",
                )
                rounds.append(round_info)
            except Exception:
                logger.warning("매각기일 파싱 실패: idx=%d", idx)
                continue
        return rounds

    def _extract_photo_urls(
        self, pic_list: list[dict[str, Any]]
    ) -> list[str]:
        """csPicLst → 사진 URL 목록 (base64 데이터 제외)"""
        urls = []
        for pic in pic_list:
            file_url = pic.get("picFileUrl", "")
            file_name = pic.get("picTitlNm", "")
            if file_url and file_name:
                urls.append(f"{PHOTO_BASE_URL}{file_url}{file_name}")
        return urls

    # === 유틸리티 ===

    @staticmethod
    def _extract_area(building_info: str) -> float | None:
        """건물 정보 문자열에서 면적 추출

        "철골철근콘크리트조 36.714㎡" → 36.714
        "철골철근콘크리트조\\r\\n36.714㎡" → 36.714

        Args:
            building_info: 건물 구조/면적 문자열

        Returns:
            면적 (㎡) 또는 None
        """
        if not building_info:
            return None
        match = re.search(r"([\d.]+)\s*[㎡m²]", building_info)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_amount(text: str) -> int:
        """금액 문자열 파싱

        "512,000,000" → 512000000
        "80000000" → 80000000
        "    80,000" → 80000

        Args:
            text: 금액 문자열

        Returns:
            정수 금액 (파싱 실패 시 0)
        """
        if not text:
            return 0
        # 숫자와 쉼표만 남기고 제거
        cleaned = re.sub(r"[^\d]", "", str(text).strip())
        if not cleaned:
            return 0
        return int(cleaned)

    @staticmethod
    def _parse_int(text: str) -> int:
        """정수 문자열 파싱 (실패 시 0)"""
        if not text:
            return 0
        try:
            return int(str(text).strip())
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_date(text: str) -> date | None:
        """날짜 문자열 파싱

        "2026.03.15" → date(2026, 3, 15)
        "20260315" → date(2026, 3, 15)
        "2026-03-15" → date(2026, 3, 15)

        Args:
            text: 날짜 문자열

        Returns:
            date 객체 (파싱 실패 시 None)
        """
        if not text:
            return None

        cleaned = text.strip()
        if not cleaned:
            return None

        # 형식별 파싱 시도
        formats = ["%Y.%m.%d", "%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue

        logger.warning("날짜 파싱 실패: '%s'", text)
        return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """HTML 엔티티 제거 및 공백 정규화

        Args:
            text: 원본 텍스트

        Returns:
            정규화된 텍스트
        """
        if not text:
            return ""
        # 연속 공백/줄바꿈을 공백 하나로
        cleaned = re.sub(r"\s+", " ", str(text))
        return cleaned.strip()

    @staticmethod
    def _detect_captcha(html: str) -> bool:
        """캡차 페이지 감지

        Args:
            html: 응답 HTML 문자열

        Returns:
            캡차 감지 여부
        """
        if not html:
            return False
        for pattern in CAPTCHA_PATTERNS:
            if pattern in html:
                return True
        return False
