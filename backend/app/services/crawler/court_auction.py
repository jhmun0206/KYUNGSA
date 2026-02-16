"""대법원 경매정보 크롤러 (HTTP 클라이언트)

courtauction.go.kr WebSquare API를 통한 경매 물건 수집.
- robots.txt 준수, 요청 간격 3초 이상
- 캡차 감지 시 CaptchaDetectedError 발생 (MVP: 수동 개입)
- 세션 쿠키 유지 관리
"""

import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.models.auction import (
    AuctionCaseDetail,
    AuctionCaseHistory,
    AuctionCaseListItem,
    AuctionDocuments,
)
from app.services.crawler.court_auction_parser import CourtAuctionParser

logger = logging.getLogger(__name__)

# 엔드포인트
BASE_URL = "https://www.courtauction.go.kr"
INIT_URL = f"{BASE_URL}/pgj/index.on"
SEARCH_URL = f"{BASE_URL}/pgj/pgjsearch/searchControllerMain.on"
DETAIL_URL = f"{BASE_URL}/pgj/pgj15B/selectAuctnCsSrchRslt.on"

# 기본 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# WebSquare 검색 필수 코드값
DEFAULT_BID_DVS_CD = "000331"  # 입찰구분: 기일입찰
DEFAULT_MVPRP_RLET_DVS_CD = "00031R"  # 부동산
DEFAULT_SRCH_COND_CD = "0004601"  # 검색조건코드
DEFAULT_PGM_ID = "PGJ151F01"  # 화면 ID


class CourtAuctionError(Exception):
    """대법원 경매정보 크롤링 오류"""

    def __init__(self, message: str, error_type: str = "UNKNOWN") -> None:
        self.error_type = error_type
        super().__init__(message)


class CaptchaDetectedError(CourtAuctionError):
    """캡차 감지 (수동 개입 필요)"""

    def __init__(self) -> None:
        super().__init__(
            "캡차가 감지되었습니다. 수동 개입이 필요합니다.",
            error_type="CAPTCHA",
        )


class CourtAuctionClient:
    """대법원 경매정보 HTTP 클라이언트

    WebSquare JSON-over-POST 방식으로 경매 물건 목록/상세/이력 수집.
    세션 쿠키를 유지하며, 요청 간격을 자동으로 조절한다.
    """

    def __init__(self) -> None:
        self._last_request_time: float = 0.0
        self._cookies: dict[str, str] = {}
        self._session_initialized = False
        self._parser = CourtAuctionParser()
        self._headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "Referer": f"{INIT_URL}?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml",
            "Origin": BASE_URL,
            "submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch",
            "sc-userid": "SYSTEM",
        }

    # === 세션 관리 ===

    def _init_session(self) -> None:
        """세션 초기화 (첫 요청 전 쿠키 획득)"""
        if self._session_initialized:
            return

        logger.info("세션 초기화: %s", INIT_URL)
        with httpx.Client(timeout=settings.COURT_AUCTION_TIMEOUT) as client:
            response = client.get(
                INIT_URL,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )

        # 세션 쿠키 저장
        for key, value in response.cookies.items():
            self._cookies[key] = value

        self._session_initialized = True
        self._last_request_time = time.time()
        logger.info("세션 초기화 완료: 쿠키 %d개", len(self._cookies))

    # === 요청 제어 ===

    def _wait_rate_limit(self) -> None:
        """요청 간격 제한"""
        interval = settings.COURT_AUCTION_REQUEST_INTERVAL
        elapsed = time.time() - self._last_request_time
        if elapsed < interval:
            wait_time = interval - elapsed
            logger.debug("Rate limit 대기: %.1f초", wait_time)
            time.sleep(wait_time)

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """공통 POST 요청 (재시도 + 캡차 감지 + 세션 유지)

        Args:
            url: 요청 URL
            payload: JSON payload

        Returns:
            JSON 응답 데이터

        Raises:
            CaptchaDetectedError: 캡차 감지 시
            CourtAuctionError: 네트워크/파싱 오류 시
        """
        self._init_session()

        max_retries = settings.COURT_AUCTION_MAX_RETRIES
        last_error = None

        for attempt in range(max_retries):
            self._wait_rate_limit()

            try:
                with httpx.Client(timeout=settings.COURT_AUCTION_TIMEOUT) as client:
                    response = client.post(
                        url,
                        json=payload,
                        headers=self._headers,
                        cookies=self._cookies,
                    )

                self._last_request_time = time.time()

                # 쿠키 업데이트
                for key, value in response.cookies.items():
                    self._cookies[key] = value

                # 캡차 감지
                if self._parser._detect_captcha(response.text):
                    logger.error("캡차 감지됨")
                    raise CaptchaDetectedError()

                # HTTP 상태코드 확인 (4xx/5xx)
                if response.status_code >= 400:
                    # 서버 에러 메시지 추출
                    err_msg = ""
                    try:
                        err_data = response.json()
                        err_msg = err_data.get("errors", {}).get("errorMessage", "")
                    except Exception:
                        pass
                    logger.warning(
                        "HTTP %d (attempt %d/%d): %s",
                        response.status_code, attempt + 1, max_retries, err_msg,
                    )
                    last_error = CourtAuctionError(
                        f"HTTP {response.status_code}: {err_msg}",
                        error_type="HTTP_ERROR",
                    )
                    if attempt < max_retries - 1:
                        backoff = settings.COURT_AUCTION_REQUEST_INTERVAL * (2 ** attempt)
                        time.sleep(backoff)
                    continue

                # JSON 파싱 시도
                try:
                    data = response.json()
                    # WebSquare 응답: {status, data: {...}} 구조에서 data 추출
                    if isinstance(data, dict) and "data" in data:
                        return data["data"]
                    return data
                except (ValueError, TypeError):
                    # JSON 파싱 실패 → HTML 응답일 수 있음
                    logger.warning("JSON 파싱 실패 (attempt %d/%d)", attempt + 1, max_retries)
                    last_error = CourtAuctionError(
                        "JSON 파싱 실패: 비정상 응답", error_type="PARSE_ERROR"
                    )
                    continue

            except CaptchaDetectedError:
                raise
            except httpx.HTTPError as e:
                logger.warning(
                    "네트워크 오류 (attempt %d/%d): %s", attempt + 1, max_retries, e
                )
                last_error = CourtAuctionError(
                    f"네트워크 오류: {e}", error_type="NETWORK_ERROR"
                )
                self._last_request_time = time.time()
                # 지수 백오프
                if attempt < max_retries - 1:
                    backoff = settings.COURT_AUCTION_REQUEST_INTERVAL * (2 ** attempt)
                    time.sleep(backoff)
                continue

        raise last_error or CourtAuctionError("최대 재시도 초과", error_type="MAX_RETRY")

    def _build_detail_payload(
        self,
        case_number: str,
        court_office_code: str,
        property_sequence: str,
    ) -> dict[str, Any]:
        """상세 조회 payload 생성"""
        return {
            "dma_srchGdsDtlSrch": {
                "csNo": case_number,
                "cortOfcCd": court_office_code,
                "dspslGdsSeq": property_sequence,
                "pgmId": DEFAULT_PGM_ID,
                "srchInfo": "",
            },
        }

    # === 공개 API ===

    def search_cases(
        self,
        court_code: str = "",
        province_code: str = "",
        usage_code: str = "",
        bid_start_date: str = "",
        bid_end_date: str = "",
        page_no: int = 1,
        page_size: int = 20,
    ) -> list[AuctionCaseListItem]:
        """경매 물건 목록 검색

        Args:
            court_code: 법원코드 (예: "B000210" 서울중앙지방법원)
            province_code: 시도코드
            usage_code: 물건용도 코드
            bid_start_date: 입찰 시작일 (YYYYMMDD)
            bid_end_date: 입찰 종료일 (YYYYMMDD)
            page_no: 페이지 번호 (1부터)
            page_size: 페이지 크기 (최대 40)

        Returns:
            경매 물건 목록
        """
        payload = {
            "dma_pageInfo": {
                "pageNo": page_no,
                "pageSize": min(page_size, 40),
                "bfPageNo": "",
                "startRowNo": "",
                "totalCnt": "",
                "totalYn": "Y" if page_no == 1 else "N",
                "groupTotalCount": "",
            },
            "dma_srchGdsDtlSrchInfo": {
                "cortOfcCd": court_code,
                "rprsAdongSdCd": province_code,
                "lclDspslGdsLstUsgCd": usage_code,
                "bidBgngYmd": bid_start_date,
                "bidEndYmd": bid_end_date,
                # WebSquare 필수 코드값
                "bidDvsCd": DEFAULT_BID_DVS_CD,
                "mvprpRletDvsCd": DEFAULT_MVPRP_RLET_DVS_CD,
                "cortAuctnSrchCondCd": DEFAULT_SRCH_COND_CD,
                "pgmId": DEFAULT_PGM_ID,
                "cortStDvs": "1",
                "statNum": 1,
                "notifyLoc": "off",
                # 빈 문자열 기본값 (서버 필수)
                "rprsAdongSggCd": "",
                "rprsAdongEmdCd": "",
                "rdnmSdCd": "",
                "rdnmSggCd": "",
                "rdnmNo": "",
                "mclDspslGdsLstUsgCd": "",
                "sclDspslGdsLstUsgCd": "",
                "cortAuctnMbrsId": "",
                "aeeEvlAmtMin": "",
                "aeeEvlAmtMax": "",
                "lwsDspslPrcRateMin": "",
                "lwsDspslPrcRateMax": "",
                "flbdNcntMin": "",
                "flbdNcntMax": "",
                "objctArDtsMin": "",
                "objctArDtsMax": "",
                "lafjOrderBy": "",
                "csNo": "",
                "dspslDxdyYmd": "",
                "lwsDspslPrcMin": "",
                "lwsDspslPrcMax": "",
                "sideDvsCd": "",
                "jdbnCd": "",
                "rletDspslSpcCondCd": "",
            },
        }

        logger.info("경매 물건 검색: 법원=%s, 페이지=%d", court_code, page_no)
        data = self._post(SEARCH_URL, payload)
        return self._parser.parse_list_response(data)

    def search_cases_with_total(
        self,
        court_code: str = "",
        page_no: int = 1,
        page_size: int = 40,
    ) -> tuple[list[AuctionCaseListItem], int]:
        """경매 물건 목록 검색 + 전체 건수 반환

        Args:
            court_code: 법원코드
            page_no: 페이지 번호 (1부터)
            page_size: 페이지 크기 (최대 40)

        Returns:
            (경매 물건 목록, 전체 건수) 튜플
        """
        payload = {
            "dma_pageInfo": {
                "pageNo": page_no,
                "pageSize": min(page_size, 40),
                "bfPageNo": "",
                "startRowNo": "",
                "totalCnt": "",
                "totalYn": "Y",
                "groupTotalCount": "",
            },
            "dma_srchGdsDtlSrchInfo": {
                "cortOfcCd": court_code,
                "rprsAdongSdCd": "",
                "lclDspslGdsLstUsgCd": "",
                "bidBgngYmd": "",
                "bidEndYmd": "",
                "bidDvsCd": DEFAULT_BID_DVS_CD,
                "mvprpRletDvsCd": DEFAULT_MVPRP_RLET_DVS_CD,
                "cortAuctnSrchCondCd": DEFAULT_SRCH_COND_CD,
                "pgmId": DEFAULT_PGM_ID,
                "cortStDvs": "1",
                "statNum": 1,
                "notifyLoc": "off",
                "rprsAdongSggCd": "",
                "rprsAdongEmdCd": "",
                "rdnmSdCd": "",
                "rdnmSggCd": "",
                "rdnmNo": "",
                "mclDspslGdsLstUsgCd": "",
                "sclDspslGdsLstUsgCd": "",
                "cortAuctnMbrsId": "",
                "aeeEvlAmtMin": "",
                "aeeEvlAmtMax": "",
                "lwsDspslPrcRateMin": "",
                "lwsDspslPrcRateMax": "",
                "flbdNcntMin": "",
                "flbdNcntMax": "",
                "objctArDtsMin": "",
                "objctArDtsMax": "",
                "lafjOrderBy": "",
                "csNo": "",
                "dspslDxdyYmd": "",
                "lwsDspslPrcMin": "",
                "lwsDspslPrcMax": "",
                "sideDvsCd": "",
                "jdbnCd": "",
                "rletDspslSpcCondCd": "",
            },
        }

        logger.info("경매 물건 검색(with total): 법원=%s, 페이지=%d", court_code, page_no)
        data = self._post(SEARCH_URL, payload)
        return self._parser.parse_list_with_total(data)

    def fetch_case_detail(
        self,
        case_number: str,
        court_office_code: str,
        property_sequence: str,
    ) -> AuctionCaseDetail:
        """경매 물건 상세 정보 조회

        Args:
            case_number: 사건번호 (예: "20220130112176")
            court_office_code: 법원코드 (예: "B000210")
            property_sequence: 물건순서 (예: "4")

        Returns:
            경매 물건 상세 정보
        """
        payload = self._build_detail_payload(
            case_number, court_office_code, property_sequence
        )

        logger.info("물건 상세 조회: %s", case_number)
        data = self._post(DETAIL_URL, payload)
        return self._parser.parse_detail_response(data)

    def fetch_case_history(
        self,
        case_number: str,
        court_office_code: str,
        property_sequence: str,
    ) -> AuctionCaseHistory:
        """경매 사건 내역 (회차별 진행 이력) 조회

        Args:
            case_number: 사건번호
            court_office_code: 법원코드
            property_sequence: 물건순서

        Returns:
            회차별 경매 진행 이력
        """
        payload = self._build_detail_payload(
            case_number, court_office_code, property_sequence
        )

        logger.info("사건내역 조회: %s", case_number)
        data = self._post(DETAIL_URL, payload)
        return self._parser.parse_history_response(data)

    def fetch_documents(
        self,
        case_number: str,
        court_office_code: str,
        property_sequence: str,
    ) -> AuctionDocuments:
        """경매 문건 목록 조회

        Args:
            case_number: 사건번호
            court_office_code: 법원코드
            property_sequence: 물건순서

        Returns:
            경매 문건 목록 (존재 여부 플래그)
        """
        payload = self._build_detail_payload(
            case_number, court_office_code, property_sequence
        )

        logger.info("문건 목록 조회: %s", case_number)
        data = self._post(DETAIL_URL, payload)
        return self._parser.parse_documents_response(data)

    def collect_full_case(
        self,
        case_number: str,
        court_office_code: str,
        property_sequence: str,
    ) -> tuple[AuctionCaseDetail, AuctionCaseHistory, AuctionDocuments]:
        """경매 물건 전체 데이터 수집 (단일 API 호출)

        상세 API는 모든 데이터를 한 번에 반환하므로,
        한 번의 호출로 상세/이력/문건 정보를 모두 파싱한다.

        Args:
            case_number: 사건번호
            court_office_code: 법원코드
            property_sequence: 물건순서

        Returns:
            (상세정보, 사건내역, 문건목록) 튜플
        """
        payload = self._build_detail_payload(
            case_number, court_office_code, property_sequence
        )

        logger.info("전체 데이터 수집: %s", case_number)
        data = self._post(DETAIL_URL, payload)

        detail = self._parser.parse_detail_response(data)
        history = self._parser.parse_history_response(data)
        documents = self._parser.parse_documents_response(data)

        return detail, history, documents
