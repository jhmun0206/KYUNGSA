"""이름 마스킹 테스트"""

from app.utils.privacy import mask_name


class TestMaskName:
    def test_three_char(self):
        assert mask_name("김미미") == "김OO"

    def test_three_char_2(self):
        assert mask_name("이상익") == "이OO"

    def test_two_char(self):
        assert mask_name("김란") == "김O"

    def test_four_char(self):
        assert mask_name("김미미미") == "김OOO"

    def test_misang(self):
        assert mask_name("미상") == "미상"

    def test_empty(self):
        assert mask_name("") == ""

    def test_none(self):
        assert mask_name(None) == ""

    def test_single_char(self):
        assert mask_name("김") == "김"

    def test_whitespace(self):
        assert mask_name("  김미미  ") == "김OO"
