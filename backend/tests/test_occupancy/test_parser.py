"""OccupancyParser 테스트"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.services.occupancy.parser import OccupancyParser

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def parser():
    return OccupancyParser()


@pytest.fixture
def sample_response():
    with open(FIXTURE_DIR / "occupancy_response.json", encoding="utf-8") as f:
        return json.load(f)


class TestParseBasic:
    """기본 파싱 테스트"""

    def test_parse_basic(self, parser, sample_response):
        """fixture 기본 파싱: 임차인 3명 + 물건 1개"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")

        assert dto.case_number == "2022타경112169"
        assert dto.court_code == "B000210"
        assert len(dto.tenants) == 3
        assert len(dto.properties) == 1
        assert dto.raw_json == sample_response

    def test_investigation_date(self, parser, sample_response):
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.investigation_date == "2022년12월09일16시10분"

    def test_etc_note_html_stripped(self, parser, sample_response):
        """기타사항 HTML 태그 제거"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.etc_note is not None
        assert "<br" not in dto.etc_note
        assert "일응 임차인으로 보고함." in dto.etc_note


class TestParseTenant:
    """임차인 파싱 테스트"""

    def test_tenant_masking(self, parser, sample_response):
        """이름 마스킹 (김미미 → 김OO)"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.tenants[0].tenant_name == "김OO"
        assert dto.tenants[1].tenant_name == "이OO"

    def test_tenant_party_type(self, parser, sample_response):
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.tenants[0].party_type == "임차인"
        assert dto.tenants[0].party_type_code == "01"

    def test_tenant_money_fields(self, parser, sample_response):
        """보증금/월세 파싱"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        t0 = dto.tenants[0]
        assert t0.deposit == 20_000_000
        assert t0.deposit_raw == "2천만원"
        assert t0.monthly_rent == 1_650_000
        assert t0.monthly_rent_raw == "165만원"

        t1 = dto.tenants[1]
        assert t1.deposit == 438_000_000
        assert t1.deposit_raw == "4억 3,800만원"
        assert t1.monthly_rent is None  # 빈 문자열

    def test_tenant_date_fields(self, parser, sample_response):
        """전입일/확정일 파싱"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        t0 = dto.tenants[0]
        assert t0.move_in_date == date(2011, 8, 23)
        assert t0.fixed_date == date(2011, 9, 1)

        t1 = dto.tenants[1]
        assert t1.move_in_date == date(2017, 1, 5)

    def test_tenant_unknown(self, parser, sample_response):
        """미상 임차인"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        t2 = dto.tenants[2]
        assert t2.is_unknown is True
        assert t2.tenant_name == "미상"
        assert t2.deposit is None
        assert t2.move_in_date is None

    def test_tenant_usage(self, parser, sample_response):
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.tenants[0].usage == "점포"
        assert dto.tenants[0].usage_code == "02"
        assert dto.tenants[1].usage == "주거"

    def test_tenant_occupied_part(self, parser, sample_response):
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.tenants[0].occupied_part == "1층 159호"
        assert dto.tenants[1].occupied_part == "2층 201호"

    def test_tenant_raw_json(self, parser, sample_response):
        """각 임차인의 원본 dict 보존"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert dto.tenants[0].raw_json is not None
        assert dto.tenants[0].raw_json["relPrtsNm"] == "김미미"


class TestParseProperty:
    """물건별 점유관계 파싱 테스트"""

    def test_property_basic(self, parser, sample_response):
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        p = dto.properties[0]
        assert p.property_index == 1
        assert p.tenant_count == 3
        assert p.possession_code == "05"

    def test_property_html_strip(self, parser, sample_response):
        """점유관계 설명 HTML 제거"""
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        p = dto.properties[0]
        assert p.possession_desc is not None
        assert "<br" not in p.possession_desc
        assert "<font" not in p.possession_desc
        assert "채무자(소유자)점유" in p.possession_desc

    def test_property_address(self, parser, sample_response):
        dto = parser.parse(sample_response, "2022타경112169", "B000210")
        assert "서울특별시 중구 마장로1길 22" in dto.properties[0].address


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_response(self, parser):
        """빈 응답"""
        dto = parser.parse({}, "2022타경999999", "B000210")
        assert len(dto.tenants) == 0
        assert len(dto.properties) == 0
        assert dto.investigation_date is None

    def test_empty_tenant_list(self, parser):
        """임차인 목록 빈 배열"""
        data = {"dlt_curstExmndcDtl": [], "dlt_gdsPossCtt": []}
        dto = parser.parse(data, "2022타경999999", "B000210")
        assert len(dto.tenants) == 0

    def test_partial_failure(self, parser):
        """임차인 1건이 이상해도 나머지 파싱 성공"""
        data = {
            "dlt_curstExmndcDtl": [
                {
                    "relPrtsNm": "정상인",
                    "relPrtsCd": "01",
                    "dpstAmt": "1천만원",
                    "mnthlyRntAmt": "",
                    "mvnDt": "2020.01.01",
                    "fxdDt": "",
                },
            ],
            "dlt_gdsPossCtt": [],
        }
        dto = parser.parse(data, "TEST", "B000210")
        assert len(dto.tenants) == 1
        assert dto.tenants[0].tenant_name == "정OO"

    def test_empty_v2_tenant_list(self, parser):
        """v2 포맷: 임차인 빈 배열"""
        data = {"dlt_ordTsLserLtn": [], "dlt_ordTsRlet": []}
        dto = parser.parse(data, "2023타경100000", "B000210")
        assert len(dto.tenants) == 0
        assert len(dto.properties) == 0


class TestParseV2:
    """v2 포맷 (실제 API 응답) 파싱 테스트"""

    @pytest.fixture
    def v2_response(self):
        with open(FIXTURE_DIR / "occupancy_response_v2.json", encoding="utf-8") as f:
            return json.load(f)

    def test_v2_basic(self, parser, v2_response):
        """v2 기본 파싱: 임차인 2명 + 물건 1개"""
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.case_number == "2023타경100000"
        assert len(dto.tenants) == 2
        assert len(dto.properties) == 1

    def test_v2_investigation_date(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.investigation_date == "2023년03월15일14시30분"

    def test_v2_etc_note(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.etc_note is not None
        assert "<br" not in dto.etc_note
        assert "현장 확인함." in dto.etc_note

    def test_v2_tenant_name(self, parser, v2_response):
        """v2 임차인 이름 마스킹 (intrpsNm 필드)"""
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.tenants[0].tenant_name == "박OO"

    def test_v2_tenant_party_type(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.tenants[0].party_type == "임차인"
        assert dto.tenants[0].party_type_code == "01"

    def test_v2_tenant_deposit(self, parser, v2_response):
        """v2 보증금 파싱 (lesDposDts 필드)"""
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.tenants[0].deposit == 300_000_000
        assert dto.tenants[0].deposit_raw == "3억원"
        assert dto.tenants[0].monthly_rent is None  # 빈 문자열

    def test_v2_tenant_dates(self, parser, v2_response):
        """v2 전입일/확정일 파싱 (mvinDtlCtt/fxdDtCtt 필드)"""
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        t0 = dto.tenants[0]
        assert t0.move_in_date == date(2021, 5, 10)
        assert t0.fixed_date == date(2021, 5, 15)

    def test_v2_tenant_unknown(self, parser, v2_response):
        """v2 미상 임차인"""
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        t1 = dto.tenants[1]
        assert t1.is_unknown is True
        assert t1.tenant_name == "미상"
        assert t1.deposit is None

    def test_v2_tenant_usage(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.tenants[0].usage == "주거"
        assert dto.tenants[0].usage_code == "01"

    def test_v2_tenant_occupied_part(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert dto.tenants[0].occupied_part == "101호 전체"

    def test_v2_property_basic(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        p = dto.properties[0]
        assert p.property_index == 1
        assert p.tenant_count == 2  # lesCnt 필드
        assert p.possession_code == "05"

    def test_v2_property_address(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        assert "역삼로 123" in dto.properties[0].address

    def test_v2_property_html_strip(self, parser, v2_response):
        dto = parser.parse(v2_response, "2023타경100000", "B000210")
        p = dto.properties[0]
        assert "<br" not in p.possession_desc
        assert "<font" not in p.possession_desc
