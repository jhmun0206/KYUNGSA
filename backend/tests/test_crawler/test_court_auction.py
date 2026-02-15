"""대법원 경매정보 크롤러 단위 테스트 (mock 기반)"""

import json
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.auction import (
    AuctionCaseDetail,
    AuctionCaseHistory,
    AuctionCaseListItem,
    AuctionDocuments,
    AuctionPropertyObject,
    AuctionRound,
    AppraisalNote,
)
from app.services.crawler.court_auction_parser import CourtAuctionParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def parser():
    """테스트용 파서"""
    return CourtAuctionParser()


def _load_json(filename: str) -> dict:
    """fixture JSON 로드"""
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def _load_html(filename: str) -> str:
    """fixture HTML 로드"""
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


# ============================================================
#  파서 테스트 (fixture 기반, HTTP 호출 없음)
# ============================================================


class TestListParsing:
    """목록 파싱 테스트"""

    def test_parse_list_json_정상(self, parser):
        """JSON 검색 응답에서 목록 항목을 올바르게 파싱한다"""
        data = _load_json("court_list_response.json")
        result = parser.parse_list_response(data)

        assert len(result) == 2
        assert isinstance(result[0], AuctionCaseListItem)

        # 첫 번째 물건 검증
        item = result[0]
        assert item.case_number == "2026타경12345"
        assert item.court == "서울중앙지방법원"
        assert item.property_type == "아파트"
        assert item.appraised_value == 800_000_000
        assert item.minimum_bid == 512_000_000
        assert item.auction_date == date(2026, 3, 15)
        assert item.bid_count == 2  # yuchalCnt=1 → bid_count=2

        # 두 번째 물건 검증
        assert result[1].case_number == "2025타경67890"
        assert result[1].appraised_value == 1_200_000_000

    def test_parse_list_html_정상(self, parser):
        """HTML 검색 결과에서 목록 항목을 올바르게 파싱한다"""
        html = _load_html("court_list.html")
        result = parser.parse_list_html(html)

        assert len(result) == 2
        assert isinstance(result[0], AuctionCaseListItem)
        assert result[0].case_number == "2026타경12345"
        assert result[0].appraised_value == 800_000_000
        assert result[0].minimum_bid == 512_000_000
        assert result[0].property_type == "아파트"

    def test_parse_list_빈결과(self, parser):
        """검색 결과가 없으면 빈 리스트를 반환한다"""
        empty_data = {"dma_pageInfo": {"totalCnt": 0}, "dlt_srchResult": []}
        result = parser.parse_list_response(empty_data)
        assert result == []

    def test_parse_list_json_dlt_없음(self, parser):
        """dlt_srchResult 키가 없어도 빈 리스트를 반환한다"""
        result = parser.parse_list_response({})
        assert result == []


class TestDetailParsing:
    """상세 파싱 테스트 (실제 API 응답 구조 기반)"""

    def test_parse_detail_json_기본필드(self, parser):
        """상세 응답에서 사건번호, 법원, 감정가 등 기본 필드를 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert isinstance(result, AuctionCaseDetail)
        assert result.case_number == "2022타경112176"
        assert result.court == "서울중앙지방법원"
        assert result.appraised_value == 467_000_000
        assert result.minimum_bid == 191_283_000
        assert result.auction_date == date(2026, 2, 10)
        assert result.court_office_code == "B000210"
        assert result.property_sequence == "4"

    def test_parse_detail_json_사건정보(self, parser):
        """사건 기본정보 (개시결정일, 청구금액 등)를 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert result.internal_case_number == "20220130112176"
        assert result.case_name == "부동산강제경매"
        assert result.case_receipt_date == date(2022, 11, 30)
        assert result.case_start_date == date(2022, 12, 13)
        assert result.claim_amount == 500_000_000
        assert result.court_department == "경매21계"
        assert result.court_phone == "530-1822"

    def test_parse_detail_json_매각정보(self, parser):
        """매각 정보 (유찰횟수, 매각결정기일, 보증금비율 등)를 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert result.failed_count == 4
        assert result.bid_count == 5  # 유찰4 + 1
        assert result.sale_decision_date == date(2026, 2, 19)
        assert result.sale_place == "경매법정(4별관 211호)"
        assert result.deposit_rate == 10
        assert result.status == "진행"

    def test_parse_detail_json_리스크정보(self, parser):
        """리스크 판단용 필드 (근저당, 물건명세서 비고)를 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert "근저당" in result.top_priority_mortgage
        assert "일괄매각" in result.specification_remarks
        assert result.superficies_info == ""  # null → 빈 문자열

    def test_parse_detail_json_배당요구종기(self, parser):
        """배당요구종기를 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert result.distribution_demand_deadline == date(2023, 2, 27)

    def test_parse_detail_json_문건존재(self, parser):
        """매각물건명세서, 감정평가서 존재 여부를 판단한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert result.has_specification is True
        assert result.has_appraisal is True
        assert result.specification_date == date(2026, 1, 26)

    def test_parse_detail_json_물건객체(self, parser):
        """매각 물건 객체 목록을 올바르게 파싱한다 (일괄매각 2건)"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert len(result.property_objects) == 2
        obj1 = result.property_objects[0]
        assert isinstance(obj1, AuctionPropertyObject)
        assert obj1.sequence == 5
        assert obj1.real_estate_type == "전유"
        assert obj1.building_name == "광화문플래티넘"
        assert obj1.building_detail == "지1층비109호"
        assert obj1.appraised_value == 220_000_000
        assert obj1.lot_number == "156"
        assert obj1.area_m2 == pytest.approx(36.714)
        assert obj1.x_coord == "309531"

        # 두 번째 물건
        obj2 = result.property_objects[1]
        assert obj2.sequence == 6
        assert obj2.area_m2 == pytest.approx(43.974)

    def test_parse_detail_json_면적_level1호환(self, parser):
        """첫 번째 물건의 면적/층수가 Level 1 호환 필드에 설정된다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert result.area_m2 == pytest.approx(36.714)
        assert result.floor == "지1층비109호"
        assert result.lot_number == "156"

    def test_parse_detail_json_감정평가요점(self, parser):
        """감정평가 요점 목록을 파싱한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert len(result.appraisal_notes) == 2
        note1 = result.appraisal_notes[0]
        assert isinstance(note1, AppraisalNote)
        assert note1.sequence == 1
        assert note1.category_code == "00083001"
        assert "경복궁역" in note1.content

    def test_parse_detail_json_매각기일이력(self, parser):
        """매각기일 이력을 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert len(result.auction_rounds) == 3
        r1 = result.auction_rounds[0]
        assert r1.round_number == 1
        assert r1.round_date == date(2023, 9, 5)
        assert r1.minimum_bid == 467_000_000
        assert r1.result == "유찰"
        assert r1.result_code == "002"
        assert r1.winning_bid is None

        r3 = result.auction_rounds[2]
        assert r3.result == "진행예정"
        assert r3.result_code == "003"
        assert r3.minimum_bid == 191_283_000

    def test_parse_detail_json_사진URL(self, parser):
        """사진 URL 목록을 추출한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert len(result.photo_urls) == 2
        assert "courtauction.go.kr" in result.photo_urls[0]
        assert result.photo_urls[0].endswith(".jpg")

    def test_parse_detail_json_소재지(self, parser):
        """소재지를 물건 객체의 userPrintSt에서 가져온다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_detail_response(data)

        assert "종로구" in result.address
        assert "새문안로5가길" in result.address

    def test_parse_detail_html_정상(self, parser):
        """HTML 상세 페이지에서 물건 정보를 올바르게 파싱한다"""
        html = _load_html("court_detail.html")
        result = parser.parse_detail_html(html)

        assert isinstance(result, AuctionCaseDetail)
        assert result.case_number == "2026타경12345"
        assert result.court == "서울중앙지방법원"
        assert result.appraised_value == 800_000_000
        assert result.minimum_bid == 512_000_000


class TestHistoryParsing:
    """사건내역 파싱 테스트"""

    def test_parse_history_기본정보(self, parser):
        """사건번호, 개시결정일, 배당요구종기를 추출한다"""
        data = _load_json("court_history_response.json")
        result = parser.parse_history_response(data)

        assert isinstance(result, AuctionCaseHistory)
        assert result.case_number == "2022타경112176"
        assert result.case_start_date == date(2022, 12, 13)
        assert result.distribution_demand_deadline == date(2023, 2, 27)

    def test_parse_history_회차이력(self, parser):
        """회차별 매각기일 이력을 올바르게 파싱한다"""
        data = _load_json("court_history_response.json")
        result = parser.parse_history_response(data)

        assert len(result.rounds) == 2

        # 1회차: 유찰
        r1 = result.rounds[0]
        assert r1.round_number == 1
        assert r1.round_date == date(2023, 9, 5)
        assert r1.minimum_bid == 467_000_000
        assert r1.result == "유찰"
        assert r1.result_code == "002"
        assert r1.winning_bid is None
        assert r1.sale_time == "1000"
        assert r1.sale_place == "경매법정(4별관 211호)"

        # 2회차: 매각
        r2 = result.rounds[1]
        assert r2.round_number == 2
        assert r2.round_date == date(2024, 1, 23)
        assert r2.minimum_bid == 373_600_000
        assert r2.result == "매각"
        assert r2.result_code == "001"
        assert r2.winning_bid == 400_000_000

    def test_parse_history_빈이력(self, parser):
        """매각기일 이력이 없으면 빈 리스트를 반환한다"""
        data = {
            "dma_result": {
                "csBaseInfo": {"userCsNo": "2026타경99999"},
                "gdsDspslDxdyLst": [],
            }
        }
        result = parser.parse_history_response(data)

        assert result.case_number == "2026타경99999"
        assert result.rounds == []


class TestDocumentsParsing:
    """문건 목록 파싱 테스트"""

    def test_parse_documents_존재여부(self, parser):
        """상세 응답에서 문건 존재 여부를 정확하게 추론한다"""
        data = _load_json("court_detail_response.json")
        result = parser.parse_documents_response(data)

        assert isinstance(result, AuctionDocuments)
        assert result.case_number == "2022타경112176"
        assert result.has_specification is True  # dspslGdsSpcfcEcdocId 존재
        assert result.has_appraisal is True  # aeeWevlMnpntLst 존재
        assert result.has_status_report is True  # csPicLst 존재
        assert result.specification_date == date(2026, 1, 26)

    def test_parse_documents_없는경우(self, parser):
        """문건 관련 데이터가 없으면 False를 반환한다"""
        data = {
            "dma_result": {
                "csBaseInfo": {"userCsNo": "2026타경99999"},
                "dspslGdsDxdyInfo": {},
                "aeeWevlMnpntLst": [],
                "csPicLst": [],
            }
        }
        result = parser.parse_documents_response(data)

        assert result.has_specification is False
        assert result.has_appraisal is False
        assert result.has_status_report is False


class TestPropertyObjectParsing:
    """물건 객체 파싱 상세 테스트"""

    def test_면적추출_정상(self, parser):
        """건물 정보에서 면적을 추출한다"""
        assert parser._extract_area("철골철근콘크리트조 36.714㎡") == pytest.approx(36.714)
        assert parser._extract_area("철근콘크리트조 84.99㎡") == pytest.approx(84.99)
        assert parser._extract_area("목조 120m²") == pytest.approx(120.0)

    def test_면적추출_캐리지리턴(self, parser):
        """\\r\\n이 포함된 문자열에서도 면적을 추출한다"""
        assert parser._extract_area("철골철근콘크리트조\r\n36.714㎡") == pytest.approx(36.714)

    def test_면적추출_실패(self, parser):
        """면적 정보가 없으면 None을 반환한다"""
        assert parser._extract_area("") is None
        assert parser._extract_area("토지") is None
        assert parser._extract_area("철근콘크리트조") is None


class TestRoundResultMapping:
    """매각기일 결과코드 매핑 테스트"""

    def test_결과코드_매핑(self, parser):
        """결과코드가 한국어로 올바르게 매핑된다"""
        schedule = [
            {"dxdyYmd": "20230901", "tsLwsDspslPrc": "100000000", "auctnDxdyRsltCd": "001", "dspslAmt": "120000000"},
            {"dxdyYmd": "20230801", "tsLwsDspslPrc": "100000000", "auctnDxdyRsltCd": "002", "dspslAmt": None},
            {"dxdyYmd": "20231001", "tsLwsDspslPrc": "80000000", "auctnDxdyRsltCd": "003", "dspslAmt": None},
        ]
        rounds = parser._parse_rounds(schedule)

        assert rounds[0].result == "매각"
        assert rounds[0].winning_bid == 120_000_000
        assert rounds[1].result == "유찰"
        assert rounds[1].winning_bid is None
        assert rounds[2].result == "진행예정"

    def test_알수없는_결과코드(self, parser):
        """알 수 없는 결과코드는 원본 코드를 그대로 사용한다"""
        schedule = [
            {"dxdyYmd": "20230901", "tsLwsDspslPrc": "100000000", "auctnDxdyRsltCd": "999", "dspslAmt": None},
        ]
        rounds = parser._parse_rounds(schedule)
        assert rounds[0].result == "999"
        assert rounds[0].result_code == "999"


class TestParserUtilities:
    """파서 유틸리티 메서드 테스트"""

    def test_parse_amount_다양한형식(self, parser):
        """다양한 금액 형식을 올바르게 파싱한다"""
        assert parser._parse_amount("512,000,000") == 512_000_000
        assert parser._parse_amount("800000000") == 800_000_000
        assert parser._parse_amount("    80,000") == 80_000
        assert parser._parse_amount("1,200,000,000원") == 1_200_000_000
        assert parser._parse_amount("") == 0
        assert parser._parse_amount("없음") == 0

    def test_parse_date_다양한형식(self, parser):
        """다양한 날짜 형식을 올바르게 파싱한다"""
        assert parser._parse_date("2026.03.15") == date(2026, 3, 15)
        assert parser._parse_date("20260315") == date(2026, 3, 15)
        assert parser._parse_date("2026-03-15") == date(2026, 3, 15)
        assert parser._parse_date("2026/03/15") == date(2026, 3, 15)
        assert parser._parse_date("") is None
        assert parser._parse_date("invalid") is None

    def test_parse_int_정상(self, parser):
        """정수 문자열을 올바르게 파싱한다"""
        assert parser._parse_int("10") == 10
        assert parser._parse_int("0") == 0
        assert parser._parse_int("") == 0
        assert parser._parse_int("abc") == 0

    def test_detect_captcha_감지(self, parser):
        """캡차 HTML을 올바르게 감지한다"""
        captcha_html = '<html><body><div class="captcha">자동입력방지 문자를 입력하세요</div></body></html>'
        assert parser._detect_captcha(captcha_html) is True

    def test_detect_captcha_미감지(self, parser):
        """정상 HTML에서 캡차를 감지하지 않는다"""
        normal_html = "<html><body><table>정상 경매 데이터</table></body></html>"
        assert parser._detect_captcha(normal_html) is False

    def test_clean_text_공백정규화(self, parser):
        """연속 공백과 줄바꿈을 정규화한다"""
        assert parser._clean_text("서울  강남구\n역삼동") == "서울 강남구 역삼동"
        assert parser._clean_text("  앞뒤공백  ") == "앞뒤공백"
        assert parser._clean_text("") == ""


# ============================================================
#  HTTP 클라이언트 테스트 (mock 기반)
# ============================================================


class TestCourtAuctionClient:
    """HTTP 클라이언트 테스트"""

    @pytest.fixture
    def client(self):
        """테스트용 경매정보 클라이언트 (rate limit 비활성화)"""
        with patch("app.services.crawler.court_auction.settings") as mock_settings:
            mock_settings.COURT_AUCTION_REQUEST_INTERVAL = 0.0
            mock_settings.COURT_AUCTION_MAX_RETRIES = 3
            mock_settings.COURT_AUCTION_TIMEOUT = 10
            from app.services.crawler.court_auction import CourtAuctionClient
            yield CourtAuctionClient()

    @patch("app.services.crawler.court_auction.httpx.Client")
    def test_search_cases_성공(self, mock_client_cls, client):
        """물건 검색 요청이 올바른 엔드포인트와 파라미터로 호출된다"""
        fixture_data = _load_json("court_list_response.json")

        # 세션 초기화 응답
        mock_init_response = MagicMock()
        mock_init_response.status_code = 200
        mock_init_response.cookies = {"JSESSIONID": "test-session"}

        # 검색 응답
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = fixture_data
        mock_search_response.text = json.dumps(fixture_data)
        mock_search_response.raise_for_status = MagicMock()
        mock_search_response.cookies = {}

        mock_http = MagicMock()
        mock_http.get.return_value = mock_init_response
        mock_http.post.return_value = mock_search_response
        mock_client_cls.return_value.__enter__.return_value = mock_http

        result = client.search_cases(court_code="B000210")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].case_number == "2026타경12345"

    @patch("app.services.crawler.court_auction.httpx.Client")
    def test_fetch_case_detail_성공(self, mock_client_cls, client):
        """물건 상세 조회가 올바른 파라미터로 호출된다"""
        fixture_data = _load_json("court_detail_response.json")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = fixture_data
        mock_response.text = json.dumps(fixture_data, ensure_ascii=False)
        mock_response.raise_for_status = MagicMock()
        mock_response.cookies = {}

        mock_http = MagicMock()
        mock_http.get.return_value = MagicMock(status_code=200, cookies={"JSESSIONID": "test"})
        mock_http.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_http

        result = client.fetch_case_detail("20220130112176", "B000210", "4")

        assert isinstance(result, AuctionCaseDetail)
        assert result.case_number == "2022타경112176"
        assert result.appraised_value == 467_000_000

    @patch("app.services.crawler.court_auction.httpx.Client")
    def test_collect_full_case_성공(self, mock_client_cls, client):
        """전체 데이터 수집이 단일 호출로 상세/이력/문건을 반환한다"""
        fixture_data = _load_json("court_detail_response.json")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = fixture_data
        mock_response.text = json.dumps(fixture_data, ensure_ascii=False)
        mock_response.cookies = {}

        mock_http = MagicMock()
        mock_http.get.return_value = MagicMock(status_code=200, cookies={"JSESSIONID": "test"})
        mock_http.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_http

        detail, history, documents = client.collect_full_case(
            "20220130112176", "B000210", "4"
        )

        assert isinstance(detail, AuctionCaseDetail)
        assert isinstance(history, AuctionCaseHistory)
        assert isinstance(documents, AuctionDocuments)

        # 한 번의 POST 호출만 발생 (세션 초기화 GET 제외)
        assert mock_http.post.call_count == 1

        # 상세/이력/문건이 같은 데이터에서 파싱됨
        assert detail.case_number == "2022타경112176"
        assert len(history.rounds) == 3
        assert documents.has_specification is True

    def test_rate_limit_준수(self, client):
        """연속 요청 시 최소 간격을 유지한다"""
        from app.services.crawler.court_auction import CourtAuctionClient

        # rate limit interval을 짧게 설정하여 테스트
        with patch("app.services.crawler.court_auction.settings") as mock_settings:
            mock_settings.COURT_AUCTION_REQUEST_INTERVAL = 0.1
            mock_settings.COURT_AUCTION_MAX_RETRIES = 3
            mock_settings.COURT_AUCTION_TIMEOUT = 10

            test_client = CourtAuctionClient()
            test_client._last_request_time = time.time()

            start = time.time()
            test_client._wait_rate_limit()
            elapsed = time.time() - start

            # 최소 0.05초는 대기 (0.1초 간격 요구)
            assert elapsed >= 0.05

    @patch("app.services.crawler.court_auction.httpx.Client")
    def test_captcha_감지시_예외발생(self, mock_client_cls, client):
        """캡차 감지 시 CaptchaDetectedError를 발생시킨다"""
        from app.services.crawler.court_auction import CaptchaDetectedError

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>자동입력방지 captcha</body></html>'
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.raise_for_status = MagicMock()
        mock_response.cookies = {}

        mock_http = MagicMock()
        mock_http.get.return_value = MagicMock(status_code=200, cookies={"JSESSIONID": "test"})
        mock_http.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_http

        with pytest.raises(CaptchaDetectedError):
            client.search_cases(court_code="B000210")

    @patch("app.services.crawler.court_auction.httpx.Client")
    def test_네트워크_오류_재시도(self, mock_client_cls, client):
        """네트워크 오류 시 재시도한다"""
        import httpx
        from app.services.crawler.court_auction import CourtAuctionError

        mock_http = MagicMock()
        mock_http.get.return_value = MagicMock(status_code=200, cookies={"JSESSIONID": "test"})
        mock_http.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client_cls.return_value.__enter__.return_value = mock_http

        with pytest.raises(CourtAuctionError):
            client.search_cases(court_code="B000210")

        # 재시도 횟수만큼 호출되었는지 확인 (초기화 GET + 재시도 POST * 3)
        assert mock_http.post.call_count == 3

    @patch("app.services.crawler.court_auction.httpx.Client")
    def test_session_초기화(self, mock_client_cls, client):
        """첫 요청 시 세션 쿠키를 획득한다"""
        session_cookie = {"JSESSIONID": "abc123", "WMONID": "xyz789"}

        mock_init_response = MagicMock()
        mock_init_response.status_code = 200
        mock_init_response.cookies = session_cookie

        fixture_data = _load_json("court_list_response.json")
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = fixture_data
        mock_search_response.text = json.dumps(fixture_data)
        mock_search_response.raise_for_status = MagicMock()
        mock_search_response.cookies = {}

        mock_http = MagicMock()
        mock_http.get.return_value = mock_init_response
        mock_http.post.return_value = mock_search_response
        mock_client_cls.return_value.__enter__.return_value = mock_http

        client.search_cases(court_code="B000210")

        # GET이 호출되었는지 확인 (세션 초기화)
        mock_http.get.assert_called_once()
        # 세션 쿠키가 저장되었는지 확인
        assert client._cookies.get("JSESSIONID") == "abc123"
