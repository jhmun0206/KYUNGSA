"""금액 파서 테스트"""

import pytest
from app.utils.money_parser import parse_korean_money


class TestKoreanMoneyUnits:
    """한글 단위 금액 파싱"""

    def test_cheon_man(self):
        assert parse_korean_money("2천만원") == 20_000_000

    def test_man(self):
        assert parse_korean_money("165만원") == 1_650_000

    def test_50man(self):
        assert parse_korean_money("50만원") == 500_000

    def test_eok(self):
        assert parse_korean_money("3억원") == 300_000_000

    def test_eok_cheonman(self):
        assert parse_korean_money("1억 5천만원") == 150_000_000

    def test_eok_with_comma_man(self):
        assert parse_korean_money("4억 3,800만원") == 438_000_000

    def test_eok_man(self):
        assert parse_korean_money("4억 3800만원") == 438_000_000

    def test_5cheon_man(self):
        assert parse_korean_money("5천만원") == 50_000_000


class TestPureNumbers:
    """순수 숫자(쉼표 포함) 파싱"""

    def test_comma_separated(self):
        assert parse_korean_money("300,000,000") == 300_000_000

    def test_comma_with_won(self):
        assert parse_korean_money("438,000,000원") == 438_000_000

    def test_plain_number(self):
        assert parse_korean_money("20000000") == 20_000_000


class TestSpecialValues:
    """특수 값 처리"""

    def test_misang(self):
        assert parse_korean_money("미상") is None

    def test_empty(self):
        assert parse_korean_money("") is None

    def test_none(self):
        assert parse_korean_money(None) is None

    def test_eopseum(self):
        assert parse_korean_money("없음") == 0

    def test_dash(self):
        assert parse_korean_money("-") is None

    def test_whitespace(self):
        assert parse_korean_money("  ") is None
