"""RegistryParser 단위 테스트

등기부등본 텍스트 파싱 로직을 검증한다.
"""

import json
import os

import pytest

from app.models.registry import (
    Confidence,
    EventType,
    SectionType,
)
from app.services.parser.registry_parser import RegistryParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(filename: str) -> str:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _load_json_fixture(filename: str) -> dict:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def parser():
    return RegistryParser()


@pytest.fixture
def apt_text():
    return _load_fixture("registry_sample_apt.txt")


@pytest.fixture
def hardstop_text():
    return _load_fixture("registry_sample_hardstop.txt")


@pytest.fixture
def complex_text():
    return _load_fixture("registry_sample_complex.txt")


@pytest.fixture
def expected():
    return _load_json_fixture("registry_events_expected.json")


# === TestSectionSplit ===


class TestSectionSplit:
    """섹션 분리 테스트"""

    def test_split_three_sections(self, parser, apt_text):
        """표제부/갑구/을구 모두 분리"""
        sections = parser._split_sections(apt_text)
        assert sections["title"] != ""
        assert sections["gapgu"] != ""
        assert sections["eulgu"] != ""

    def test_gapgu_contains_keyword(self, parser, apt_text):
        """갑구에 소유권 관련 키워드 포함"""
        sections = parser._split_sections(apt_text)
        assert "소유권" in sections["gapgu"]

    def test_eulgu_contains_keyword(self, parser, apt_text):
        """을구에 근저당 관련 키워드 포함"""
        sections = parser._split_sections(apt_text)
        assert "근저당" in sections["eulgu"]

    def test_empty_text(self, parser):
        """빈 텍스트"""
        sections = parser._split_sections("")
        assert sections["title"] == ""
        assert sections["gapgu"] == ""
        assert sections["eulgu"] == ""

    def test_gapgu_only(self, parser):
        """갑구만 있는 경우"""
        text = "【갑구】 (소유권에 관한 사항)\n순위번호\n1 | 소유권이전 | 2020년1월1일 제1호 | | 소유자 홍길동"
        sections = parser._split_sections(text)
        assert sections["gapgu"] != ""
        assert sections["eulgu"] == ""


# === TestTitleParsing ===


class TestTitleParsing:
    """표제부 파싱 테스트"""

    def test_address_extraction(self, parser, apt_text):
        """주소 추출"""
        doc = parser.parse_text(apt_text)
        assert doc.title is not None
        assert "강남구" in doc.title.address
        assert "역삼동" in doc.title.address

    def test_area_extraction(self, parser, apt_text):
        """면적 추출"""
        doc = parser.parse_text(apt_text)
        assert doc.title.area == 85.12

    def test_structure_extraction(self, parser, apt_text):
        """구조 추출"""
        doc = parser.parse_text(apt_text)
        assert doc.title.structure is not None
        assert "철근콘크리트" in doc.title.structure

    def test_raw_text_preserved(self, parser, apt_text):
        """raw_text 보존"""
        doc = parser.parse_text(apt_text)
        assert doc.title.raw_text != ""


# === TestEventExtraction ===


class TestEventExtraction:
    """이벤트 추출 테스트"""

    def test_gapgu_event_count(self, parser, apt_text, expected):
        """갑구 이벤트 수"""
        doc = parser.parse_text(apt_text)
        assert len(doc.gapgu_events) == expected["gapgu_event_count"]

    def test_eulgu_event_count(self, parser, apt_text, expected):
        """을구 이벤트 수"""
        doc = parser.parse_text(apt_text)
        assert len(doc.eulgu_events) == expected["eulgu_event_count"]

    def test_all_events_count(self, parser, apt_text, expected):
        """전체 이벤트 수"""
        doc = parser.parse_text(apt_text)
        assert len(doc.all_events) == expected["all_event_count"]

    def test_event_sections_correct(self, parser, apt_text):
        """갑구/을구 섹션 구분"""
        doc = parser.parse_text(apt_text)
        for e in doc.gapgu_events:
            assert e.section == SectionType.GAPGU
        for e in doc.eulgu_events:
            assert e.section == SectionType.EULGU

    def test_all_events_sorted_by_date(self, parser, apt_text):
        """전체 이벤트 접수일 순 정렬"""
        doc = parser.parse_text(apt_text)
        dates = [e.accepted_at for e in doc.all_events if e.accepted_at]
        assert dates == sorted(dates)


# === TestFieldExtraction ===


class TestFieldExtraction:
    """필드 추출 테스트"""

    def test_accepted_at(self, parser, apt_text):
        """접수일자 추출"""
        doc = parser.parse_text(apt_text)
        first_gapgu = doc.gapgu_events[0]
        assert first_gapgu.accepted_at == "2018.03.15"

    def test_receipt_no(self, parser, apt_text):
        """접수번호 추출"""
        doc = parser.parse_text(apt_text)
        first_gapgu = doc.gapgu_events[0]
        assert first_gapgu.receipt_no == "12345"

    def test_amount_extraction(self, parser, apt_text):
        """금액 추출 (채권최고액)"""
        doc = parser.parse_text(apt_text)
        # 을구 1번: 근저당 600,000,000원
        first_eulgu = doc.eulgu_events[0]
        assert first_eulgu.amount == 600_000_000

    def test_amount_claim(self, parser, apt_text):
        """금액 추출 (청구금액)"""
        doc = parser.parse_text(apt_text)
        # 갑구 2번: 가압류 500,000,000원
        gapgu2 = doc.gapgu_events[1]
        assert gapgu2.amount == 500_000_000

    def test_holder_extraction(self, parser, apt_text):
        """권리자 추출"""
        doc = parser.parse_text(apt_text)
        first_gapgu = doc.gapgu_events[0]
        assert first_gapgu.holder is not None
        assert "홍길동" in first_gapgu.holder

    def test_raw_text_preserved(self, parser, apt_text):
        """raw_text 보존"""
        doc = parser.parse_text(apt_text)
        for event in doc.all_events:
            assert event.raw_text != ""

    def test_rank_no(self, parser, apt_text):
        """순위번호 추출"""
        doc = parser.parse_text(apt_text)
        ranks = [e.rank_no for e in doc.gapgu_events]
        assert ranks == [1, 2, 3]


# === TestCanceledDetection ===


class TestCanceledDetection:
    """말소 감지 테스트"""

    def test_canceled_event_detected(self, parser, complex_text):
        """말소 이벤트 감지 (complex 샘플의 갑구3 '2번가압류말소')"""
        doc = parser.parse_text(complex_text)
        canceled_events = [e for e in doc.gapgu_events if e.canceled]
        assert len(canceled_events) >= 1
        assert any("말소" in e.purpose for e in canceled_events)

    def test_normal_event_not_canceled(self, parser, apt_text):
        """일반 이벤트는 canceled=False"""
        doc = parser.parse_text(apt_text)
        for event in doc.all_events:
            assert event.canceled is False

    def test_eulgu_canceled(self, parser, complex_text):
        """을구 말소 감지 (complex 샘플의 을구3 '2번근저당권말소')"""
        doc = parser.parse_text(complex_text)
        canceled = [e for e in doc.eulgu_events if e.canceled]
        assert len(canceled) >= 1


# === TestEventTypeMapping ===


class TestEventTypeMapping:
    """EventType 매핑 테스트"""

    def test_mortgage(self, parser):
        assert parser._classify_event_type("근저당권설정") == EventType.MORTGAGE

    def test_mortgage_cancel(self, parser):
        assert parser._classify_event_type("근저당권말소") == EventType.MORTGAGE_CANCEL

    def test_provisional_seizure(self, parser):
        assert parser._classify_event_type("가압류") == EventType.PROVISIONAL_SEIZURE

    def test_auction_start_voluntary(self, parser):
        assert parser._classify_event_type("임의경매개시결정") == EventType.AUCTION_START

    def test_auction_start_forced(self, parser):
        assert parser._classify_event_type("강제경매개시결정") == EventType.AUCTION_START

    def test_lease_right(self, parser):
        assert parser._classify_event_type("전세권설정") == EventType.LEASE_RIGHT

    def test_ownership_transfer(self, parser):
        assert parser._classify_event_type("소유권이전") == EventType.OWNERSHIP_TRANSFER

    def test_preliminary_notice(self, parser):
        assert parser._classify_event_type("예고등기") == EventType.PRELIMINARY_NOTICE

    def test_trust(self, parser):
        assert parser._classify_event_type("신탁") == EventType.TRUST

    def test_other(self, parser):
        assert parser._classify_event_type("알수없는등기") == EventType.OTHER


# === TestFullParse ===


class TestFullParse:
    """전체 파싱 통합 테스트"""

    def test_apt_sample_full(self, parser, apt_text, expected):
        """아파트 샘플 전체 파싱 + expected 대조"""
        doc = parser.parse_text(apt_text)

        # 표제부
        assert doc.title is not None
        assert doc.title.area == expected["title"]["area"]
        assert expected["title"]["structure"] in (doc.title.structure or "")

        # 이벤트 수
        assert len(doc.gapgu_events) == expected["gapgu_event_count"]
        assert len(doc.eulgu_events) == expected["eulgu_event_count"]

        # 갑구 이벤트 상세
        for i, exp in enumerate(expected["gapgu_events"]):
            actual = doc.gapgu_events[i]
            assert actual.rank_no == exp["rank_no"]
            assert actual.event_type.value == exp["event_type"]
            assert actual.accepted_at == exp["accepted_at"]

        # 을구 이벤트 상세
        for i, exp in enumerate(expected["eulgu_events"]):
            actual = doc.eulgu_events[i]
            assert actual.rank_no == exp["rank_no"]
            assert actual.event_type.value == exp["event_type"]
            if "amount" in exp:
                assert actual.amount == exp["amount"]

        # 신뢰도
        assert doc.parse_confidence == Confidence.HIGH

    def test_hardstop_sample(self, parser, hardstop_text):
        """Hard Stop 샘플 파싱"""
        doc = parser.parse_text(hardstop_text)
        assert len(doc.gapgu_events) == 4
        assert len(doc.eulgu_events) == 2

        # 예고등기 이벤트 확인
        notice_events = [
            e for e in doc.gapgu_events
            if e.event_type == EventType.PRELIMINARY_NOTICE
        ]
        assert len(notice_events) == 1

        # 신탁 이벤트 확인
        trust_events = [
            e for e in doc.gapgu_events
            if e.event_type == EventType.TRUST
        ]
        assert len(trust_events) == 1

    def test_complex_sample(self, parser, complex_text):
        """복잡 케이스 파싱"""
        doc = parser.parse_text(complex_text)
        assert len(doc.gapgu_events) == 5
        assert len(doc.eulgu_events) == 5

        # 말소된 이벤트 존재
        canceled = [e for e in doc.all_events if e.canceled]
        assert len(canceled) >= 2  # 갑구3 + 을구3


# === TestEdgeCases ===


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_text(self, parser):
        """빈 텍스트"""
        doc = parser.parse_text("")
        assert len(doc.all_events) == 0
        assert doc.parse_confidence == Confidence.LOW

    def test_no_events(self, parser):
        """섹션은 있지만 이벤트 없음"""
        text = "【갑구】 (소유권에 관한 사항)\n순위번호 | 등기목적 | 접수"
        doc = parser.parse_text(text)
        assert len(doc.gapgu_events) == 0

    def test_gapgu_only(self, parser):
        """갑구만 있는 경우"""
        text = (
            "【갑구】 (소유권에 관한 사항)\n"
            "순위번호 | 등기목적 | 접수 | 등기원인 | 권리자\n"
            "1 | 소유권이전 | 2020년1월1일 제1호 | 매매 | 소유자 홍길동"
        )
        doc = parser.parse_text(text)
        assert len(doc.gapgu_events) == 1
        assert len(doc.eulgu_events) == 0
        assert doc.gapgu_events[0].event_type == EventType.OWNERSHIP_TRANSFER
