"""날짜 파서 테스트"""

from datetime import date

import pytest
from app.utils.date_parser import parse_korean_date


class TestDotFormat:
    """점(.) 구분 날짜"""

    def test_standard(self):
        assert parse_korean_date("2011.08.23") == date(2011, 8, 23)

    def test_trailing_dot(self):
        assert parse_korean_date("2021.04.13.") == date(2021, 4, 13)

    def test_single_digit_month(self):
        assert parse_korean_date("2017.1.5") == date(2017, 1, 5)


class TestKoreanFormat:
    """한글 날짜"""

    def test_standard(self):
        assert parse_korean_date("2022년12월09일") == date(2022, 12, 9)

    def test_with_time(self):
        assert parse_korean_date("2022년12월09일16시10분") == date(2022, 12, 9)

    def test_with_space(self):
        assert parse_korean_date("2022년 12월 09일") == date(2022, 12, 9)


class TestISOFormat:
    """ISO 형식"""

    def test_iso(self):
        assert parse_korean_date("2021-04-13") == date(2021, 4, 13)


class TestSpecialValues:
    """특수 값"""

    def test_misang(self):
        assert parse_korean_date("미상") is None

    def test_empty(self):
        assert parse_korean_date("") is None

    def test_none(self):
        assert parse_korean_date(None) is None

    def test_dash(self):
        assert parse_korean_date("-") is None

    def test_invalid_date(self):
        assert parse_korean_date("2021.13.32") is None
