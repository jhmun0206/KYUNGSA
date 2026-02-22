"""텍스트 유틸리티 테스트"""

from app.utils.text_utils import strip_html


class TestStripHtml:
    def test_br_tag(self):
        assert strip_html("내용...<br />") == "내용..."

    def test_br_self_closing(self):
        assert strip_html("줄1<br/>줄2") == "줄1 줄2"

    def test_bold_tag(self):
        assert strip_html("<b>굵은</b> 텍스트") == "굵은 텍스트"

    def test_no_tags(self):
        assert strip_html("일반 텍스트") == "일반 텍스트"

    def test_none(self):
        assert strip_html(None) == ""

    def test_empty(self):
        assert strip_html("") == ""

    def test_multiple_spaces(self):
        assert strip_html("여러   공백   정리") == "여러 공백 정리"

    def test_complex_html(self):
        text = '채무자 배우자<br />직접 영업<br /><font color="red">주의</font>'
        result = strip_html(text)
        assert "<" not in result
        assert "채무자 배우자" in result
        assert "직접 영업" in result
        assert "주의" in result
