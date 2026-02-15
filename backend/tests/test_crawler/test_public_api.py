"""공공데이터포털 API 클라이언트 단위 테스트 (mock 기반)"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.crawler.public_api import PublicDataClient

# apis.data.go.kr 실거래가 API 실제 응답 형식 (영문 필드명)
SAMPLE_XML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<response>
    <header>
        <resultCode>00</resultCode>
        <resultMsg>NORMAL SERVICE.</resultMsg>
    </header>
    <body>
        <items>
            <item>
                <dealAmount>    80,000</dealAmount>
                <umdNm>역삼동</umdNm>
                <aptNm>래미안</aptNm>
                <excluUseAr>84.99</excluUseAr>
                <dealYear>2026</dealYear>
                <dealMonth>1</dealMonth>
                <dealDay>14</dealDay>
                <floor>10</floor>
                <sggCd>11680</sggCd>
                <jibun>123-4</jibun>
            </item>
            <item>
                <dealAmount>    75,000</dealAmount>
                <umdNm>역삼동</umdNm>
                <aptNm>타워팰리스</aptNm>
                <excluUseAr>59.88</excluUseAr>
                <dealYear>2026</dealYear>
                <dealMonth>1</dealMonth>
                <dealDay>20</dealDay>
                <floor>15</floor>
                <sggCd>11680</sggCd>
                <jibun>456-7</jibun>
            </item>
        </items>
        <numOfRows>100</numOfRows>
        <pageNo>1</pageNo>
        <totalCount>2</totalCount>
    </body>
</response>"""


@pytest.fixture
def client():
    """테스트용 공공데이터 클라이언트"""
    with patch("app.services.crawler.public_api.settings") as mock_settings:
        mock_settings.PUBLIC_DATA_API_KEY = "test_api_key"
        yield PublicDataClient()


class TestXmlParsing:
    """XML 파싱 테스트"""

    def test_parse_xml_items_정상(self):
        """XML 응답에서 item 목록을 올바르게 추출한다"""
        items = PublicDataClient._parse_xml_items(SAMPLE_XML_RESPONSE)

        assert len(items) == 2
        assert items[0]["umdNm"] == "역삼동"
        assert items[0]["aptNm"] == "래미안"
        assert items[1]["aptNm"] == "타워팰리스"

    def test_parse_xml_items_빈응답(self):
        """item이 없는 XML 응답은 빈 리스트를 반환한다"""
        empty_xml = "<response><body><items></items></body></response>"
        items = PublicDataClient._parse_xml_items(empty_xml)
        assert items == []


class TestAptTrade:
    """아파트 매매 실거래가 테스트"""

    @patch.object(PublicDataClient, "_get")
    def test_fetch_apt_trade_성공(self, mock_get, client):
        """강남구(11680) 2026년 1월 매매 실거래가를 조회한다"""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XML_RESPONSE
        mock_get.return_value = mock_response

        result = client.fetch_apt_trade("11680", "202601")

        assert len(result) == 2
        assert result[0]["umdNm"] == "역삼동"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][1]["LAWD_CD"] == "11680"
        assert call_args[0][1]["DEAL_YMD"] == "202601"


class TestAptRent:
    """아파트 전월세 실거래가 테스트"""

    @patch.object(PublicDataClient, "_get")
    def test_fetch_apt_rent_성공(self, mock_get, client):
        """전월세 실거래가 조회"""
        mock_response = MagicMock()
        mock_response.text = SAMPLE_XML_RESPONSE
        mock_get.return_value = mock_response

        result = client.fetch_apt_rent("11680", "202601")

        assert len(result) == 2


class TestBuildingRegister:
    """건축물대장 테스트"""

    @patch.object(PublicDataClient, "_get")
    def test_fetch_building_register_파라미터(self, mock_get, client):
        """건축물대장 조회 시 시군구·법정동·본번·부번이 올바르게 전달된다"""
        mock_response = MagicMock()
        mock_response.text = "<response><body><items></items></body></response>"
        mock_get.return_value = mock_response

        client.fetch_building_register("11680", "10300", "0123", "0004")

        call_args = mock_get.call_args
        params = call_args[0][1]
        assert params["sigunguCd"] == "11680"
        assert params["bjdongCd"] == "10300"
        assert params["bun"] == "0123"
        assert params["ji"] == "0004"


class TestLandPrice:
    """개별공시지가 테스트"""

    @patch.object(PublicDataClient, "_get")
    def test_fetch_land_price_json응답(self, mock_get, client):
        """JSON 응답을 올바르게 파싱한다"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "indvdLandPrices": {
                "field": [{"pnu": "1168010300101230004", "pblntfPclnd": "5000000"}]
            }
        }
        mock_get.return_value = mock_response

        result = client.fetch_land_price("1168010300101230004", "2025")

        assert len(result) == 1
        assert result[0]["pblntfPclnd"] == "5000000"
