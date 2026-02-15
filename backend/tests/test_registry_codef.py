"""CODEF 등기부등본 매퍼 + 프로바이더 테스트

CodefRegistryMapper: CODEF JSON → RegistryDocument 변환
CodefRegistryProvider: CODEF API 호출 + 매핑 (mock 기반)

실제 CODEF 응답 구조 (2026-02-10 확인):
  resRegistrationHisList → 전체 등기 이력 (표제부 + 갑구 + 을구)
  resRegistrationSumList → 요약 (소유지분현황, 공시지가, 토지이용계획)
  각 행: resType2="1"(헤더), "2"(데이터), resDetailList[].resNumber → 컬럼 위치
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.models.registry import (
    Confidence,
    EventType,
    RegistryDocument,
    SectionType,
)
from app.services.registry.codef_mapper import CodefRegistryMapper
from app.services.registry.codef_provider import CodefRegistryProvider
from app.services.registry.provider import RegistryTwoWayAuthRequired

# === Fixture 로드 ===

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def codef_response() -> dict:
    """CODEF 등기부등본 응답 mock fixture"""
    with open(FIXTURES_DIR / "codef_registry_response.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def mapper() -> CodefRegistryMapper:
    return CodefRegistryMapper()


@pytest.fixture()
def mapped_doc(mapper: CodefRegistryMapper, codef_response: dict) -> RegistryDocument:
    """fixture 전체를 매핑한 결과"""
    return mapper.map_response(codef_response)


# ============================================================
# TestCodefMapper — 매핑 로직 단위 테스트
# ============================================================


class TestCodefMapperSectionType:
    """섹션 타입 판별"""

    def test_detect_gapgu(self, mapper: CodefRegistryMapper) -> None:
        assert mapper._detect_section_type("갑구") == SectionType.GAPGU

    def test_detect_gapgu_with_description(self, mapper: CodefRegistryMapper) -> None:
        assert mapper._detect_section_type("갑구(소유권에 관한 사항)") == SectionType.GAPGU

    def test_detect_eulgu(self, mapper: CodefRegistryMapper) -> None:
        assert mapper._detect_section_type("을구") == SectionType.EULGU

    def test_detect_unknown(self, mapper: CodefRegistryMapper) -> None:
        assert mapper._detect_section_type("표제부") is None

    def test_detect_summary_not_section(self, mapper: CodefRegistryMapper) -> None:
        """요약 타입(소유지분현황 등)은 갑구/을구가 아님"""
        assert mapper._detect_section_type("소유지분현황 (갑구)") == SectionType.GAPGU


class TestCodefMapperEventTypes:
    """이벤트 타입 매핑"""

    def test_ownership_transfer(self, mapped_doc: RegistryDocument) -> None:
        gapgu = mapped_doc.gapgu_events
        ownership = [e for e in gapgu if e.event_type == EventType.OWNERSHIP_TRANSFER]
        assert len(ownership) == 1
        assert ownership[0].rank_no == 1

    def test_provisional_seizure(self, mapped_doc: RegistryDocument) -> None:
        gapgu = mapped_doc.gapgu_events
        seizure = [e for e in gapgu if e.event_type == EventType.PROVISIONAL_SEIZURE]
        assert len(seizure) == 1
        assert seizure[0].rank_no == 2

    def test_auction_start(self, mapped_doc: RegistryDocument) -> None:
        gapgu = mapped_doc.gapgu_events
        auction = [e for e in gapgu if e.event_type == EventType.AUCTION_START]
        assert len(auction) == 1
        assert auction[0].rank_no == 3

    def test_mortgage(self, mapped_doc: RegistryDocument) -> None:
        eulgu = mapped_doc.eulgu_events
        mortgages = [e for e in eulgu if e.event_type == EventType.MORTGAGE]
        # 을구 1번 + 을구 3번 = 2개
        assert len(mortgages) == 2

    def test_lease_right(self, mapped_doc: RegistryDocument) -> None:
        eulgu = mapped_doc.eulgu_events
        leases = [e for e in eulgu if e.event_type == EventType.LEASE_RIGHT]
        assert len(leases) == 1
        assert leases[0].rank_no == 2

    def test_mortgage_cancel(self, mapped_doc: RegistryDocument) -> None:
        """말소 이벤트: 등기목적에 "말소" 포함"""
        eulgu = mapped_doc.eulgu_events
        cancels = [e for e in eulgu if e.event_type == EventType.MORTGAGE_CANCEL]
        assert len(cancels) == 1
        assert cancels[0].rank_no == 3
        assert cancels[0].canceled is True


class TestCodefMapperFieldExtraction:
    """필드 추출 (테이블 형식 컬럼 기반)"""

    def test_date_extraction(self, mapped_doc: RegistryDocument) -> None:
        """접수 컬럼에서 날짜 추출: YYYY.MM.DD"""
        ownership = mapped_doc.gapgu_events[0]
        assert ownership.accepted_at == "2018.03.15"

    def test_date_extraction_single_digit_month(self, mapped_doc: RegistryDocument) -> None:
        """7월 → 07"""
        seizure = [e for e in mapped_doc.gapgu_events if e.event_type == EventType.PROVISIONAL_SEIZURE][0]
        assert seizure.accepted_at == "2022.07.01"

    def test_receipt_no(self, mapped_doc: RegistryDocument) -> None:
        """접수 컬럼에서 접수번호 추출"""
        ownership = mapped_doc.gapgu_events[0]
        assert ownership.receipt_no == "12345"

    def test_amount_mortgage(self, mapped_doc: RegistryDocument) -> None:
        """근저당 채권최고액 추출 (권리자 컬럼에서)"""
        mortgages = [e for e in mapped_doc.eulgu_events if e.event_type == EventType.MORTGAGE]
        first = [m for m in mortgages if m.rank_no == 1][0]
        assert first.amount == 600_000_000

    def test_amount_seizure(self, mapped_doc: RegistryDocument) -> None:
        """가압류 청구금액 추출"""
        seizure = [e for e in mapped_doc.gapgu_events if e.event_type == EventType.PROVISIONAL_SEIZURE][0]
        assert seizure.amount == 500_000_000

    def test_amount_lease(self, mapped_doc: RegistryDocument) -> None:
        """전세금 추출"""
        lease = [e for e in mapped_doc.eulgu_events if e.event_type == EventType.LEASE_RIGHT][0]
        assert lease.amount == 300_000_000

    def test_holder_owner(self, mapped_doc: RegistryDocument) -> None:
        """소유자 추출"""
        ownership = mapped_doc.gapgu_events[0]
        # fixture에서 "소유자 홍OO" → 홍OO
        assert ownership.holder is not None
        assert "홍" in ownership.holder

    def test_holder_creditor(self, mapped_doc: RegistryDocument) -> None:
        """채권자 추출"""
        seizure = [e for e in mapped_doc.gapgu_events if e.event_type == EventType.PROVISIONAL_SEIZURE][0]
        assert seizure.holder == "○○은행"

    def test_holder_mortgagee(self, mapped_doc: RegistryDocument) -> None:
        """근저당권자 추출"""
        mortgages = [e for e in mapped_doc.eulgu_events if e.event_type == EventType.MORTGAGE]
        first = [m for m in mortgages if m.rank_no == 1][0]
        assert first.holder == "○○은행"

    def test_holder_lessee(self, mapped_doc: RegistryDocument) -> None:
        """전세권자 추출"""
        lease = [e for e in mapped_doc.eulgu_events if e.event_type == EventType.LEASE_RIGHT][0]
        assert lease.holder is not None
        assert "박" in lease.holder

    def test_cause_field(self, mapped_doc: RegistryDocument) -> None:
        """등기원인 컬럼 추출"""
        ownership = mapped_doc.gapgu_events[0]
        assert ownership.cause is not None
        assert "매매" in ownership.cause


class TestCodefMapperCanceled:
    """말소 이벤트 처리"""

    def test_active_events_not_canceled(self, mapped_doc: RegistryDocument) -> None:
        """일반 이벤트는 canceled=False"""
        gapgu_active = [e for e in mapped_doc.gapgu_events if not e.canceled]
        assert len(gapgu_active) == 3  # 소유권이전, 가압류, 경매개시

    def test_canceled_event_detected(self, mapped_doc: RegistryDocument) -> None:
        """등기목적에 '말소' 포함 → canceled=True"""
        canceled = [e for e in mapped_doc.all_events if e.canceled]
        assert len(canceled) == 1
        assert canceled[0].event_type == EventType.MORTGAGE_CANCEL


class TestCodefMapperTitle:
    """표제부 파싱 (resRegistrationHisList 표제부 섹션)"""

    def test_title_address(self, mapped_doc: RegistryDocument) -> None:
        assert mapped_doc.title is not None
        assert "강남구" in mapped_doc.title.address
        assert "역삼동" in mapped_doc.title.address

    def test_title_area(self, mapped_doc: RegistryDocument) -> None:
        assert mapped_doc.title is not None
        assert mapped_doc.title.area == 85.12

    def test_title_structure(self, mapped_doc: RegistryDocument) -> None:
        assert mapped_doc.title is not None
        assert "콘크리트" in mapped_doc.title.structure

    def test_title_fallback_to_realty(self, mapper: CodefRegistryMapper) -> None:
        """표제부가 없으면 resRealty에서 파싱"""
        data = {
            "resRegisterEntriesList": [{
                "resRealty": "[집합건물] 서울특별시 강남구 역삼동 123",
                "resRegistrationHisList": [
                    {"resType": "갑구", "resType1": "", "resContentsList": [
                        {"resType2": "1", "resDetailList": [
                            {"resNumber": "0", "resContents": "순위번호"},
                            {"resNumber": "1", "resContents": "등기목적"},
                            {"resNumber": "2", "resContents": "접수"},
                            {"resNumber": "3", "resContents": "등기원인"},
                            {"resNumber": "4", "resContents": "권리자"},
                        ], "resNumber": "0"},
                        {"resType2": "2", "resDetailList": [
                            {"resNumber": "0", "resContents": "1"},
                            {"resNumber": "1", "resContents": "소유권보존"},
                            {"resNumber": "2", "resContents": "2020년1월1일\n제1호"},
                            {"resNumber": "3", "resContents": ""},
                            {"resNumber": "4", "resContents": "소유자 테스트"},
                        ], "resNumber": "1"},
                    ]},
                ],
                "resRegistrationSumList": [],
            }],
        }
        doc = mapper.map_response(data)
        assert doc.title is not None
        assert "역삼동" in doc.title.address


class TestCodefMapperEdgeCases:
    """엣지 케이스"""

    def test_empty_response(self, mapper: CodefRegistryMapper) -> None:
        doc = mapper.map_response({})
        assert doc.source == "codef"
        assert doc.parse_confidence == Confidence.LOW
        assert len(doc.all_events) == 0

    def test_empty_entries_list(self, mapper: CodefRegistryMapper) -> None:
        doc = mapper.map_response({"resRegisterEntriesList": []})
        assert doc.parse_confidence == Confidence.LOW

    def test_header_rows_skipped(self, mapper: CodefRegistryMapper) -> None:
        """resType2='1' 헤더 행은 이벤트로 파싱되지 않음"""
        data = {
            "resRegisterEntriesList": [{
                "resRealty": "",
                "resRegistrationHisList": [{
                    "resType": "갑구",
                    "resType1": "",
                    "resContentsList": [
                        {"resType2": "1", "resDetailList": [
                            {"resNumber": "0", "resContents": "순위번호"},
                        ], "resNumber": "0"},
                    ],
                }],
                "resRegistrationSumList": [],
            }]
        }
        doc = mapper.map_response(data)
        assert len(doc.all_events) == 0

    def test_empty_purpose_skipped(self, mapper: CodefRegistryMapper) -> None:
        """등기목적 컬럼이 비어있으면 이벤트 건너뜀"""
        data = {
            "resRegisterEntriesList": [{
                "resRealty": "",
                "resRegistrationHisList": [{
                    "resType": "갑구",
                    "resType1": "",
                    "resContentsList": [
                        {"resType2": "2", "resDetailList": [
                            {"resNumber": "0", "resContents": "1"},
                            {"resNumber": "1", "resContents": ""},
                            {"resNumber": "2", "resContents": ""},
                            {"resNumber": "3", "resContents": ""},
                            {"resNumber": "4", "resContents": ""},
                        ], "resNumber": "1"},
                    ],
                }],
                "resRegistrationSumList": [],
            }]
        }
        doc = mapper.map_response(data)
        assert len(doc.all_events) == 0

    def test_source_field(self, mapped_doc: RegistryDocument) -> None:
        assert mapped_doc.source == "codef"


class TestCodefMapperIntegration:
    """통합: 전체 fixture → RegistryDocument"""

    def test_total_event_count(self, mapped_doc: RegistryDocument) -> None:
        """갑구 3 + 을구 4 (3 active + 1 canceled) = 7"""
        assert len(mapped_doc.all_events) == 7

    def test_gapgu_count(self, mapped_doc: RegistryDocument) -> None:
        assert len(mapped_doc.gapgu_events) == 3

    def test_eulgu_count(self, mapped_doc: RegistryDocument) -> None:
        """을구: 근저당1 + 전세 + 근저당2 + 근저당말소 = 4"""
        assert len(mapped_doc.eulgu_events) == 4

    def test_events_sorted_by_date(self, mapped_doc: RegistryDocument) -> None:
        dates = [e.accepted_at for e in mapped_doc.all_events if e.accepted_at]
        assert dates == sorted(dates)

    def test_confidence_high(self, mapped_doc: RegistryDocument) -> None:
        assert mapped_doc.parse_confidence == Confidence.HIGH

    def test_analyzer_compatible(self, mapped_doc: RegistryDocument) -> None:
        """매핑 결과가 RegistryAnalyzer에 정상 입력 가능"""
        from app.services.parser.registry_analyzer import RegistryAnalyzer

        analyzer = RegistryAnalyzer()
        result = analyzer.analyze(mapped_doc)
        # 분석이 정상 수행되면 cancellation_base가 존재해야 함
        assert result.cancellation_base_event is not None
        assert result.summary  # 요약 텍스트 존재


# ============================================================
# TestCodefProvider — API 호출 테스트 (mock)
# ============================================================


class TestCodefProviderFetch:
    """fetch_registry mock 테스트"""

    def test_fetch_success(self, codef_response: dict) -> None:
        """정상 응답 → RegistryDocument 반환"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        doc = provider.fetch_registry("12345678901234")

        assert isinstance(doc, RegistryDocument)
        assert doc.source == "codef"
        assert len(doc.all_events) == 7
        mock_client._request.assert_called_once()

    def test_fetch_passes_unique_no(self, codef_response: dict) -> None:
        """unique_no가 payload에 포함되는지 확인"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        provider.fetch_registry("99998877665544", realty_type="1")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["uniqueNo"] == "99998877665544"
        assert payload["realtyType"] == "1"

    def test_inquiry_type_0(self, codef_response: dict) -> None:
        """inquiryType=0 (고유번호로 찾기) 확인"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["inquiryType"] == "0"

    def test_no_addr_params_in_payload(self, codef_response: dict) -> None:
        """inquiryType=0이므로 addr_* 파라미터가 payload에 없어야 함"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        # 기존 호환: addr_* 전달해도 무시됨
        provider.fetch_registry(
            "12345678901234",
            addr_sido="서울특별시",
            addr_sigungu="강남구",
        )

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        # addr_* 키가 payload에 없어야 함
        assert "addr_sido" not in payload
        assert "addr_sigungu" not in payload
        assert "addr_dong" not in payload

    def test_unique_no_hyphen_removed(self, codef_response: dict) -> None:
        """uniqueNo에서 하이픈이 제거되는지"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        provider.fetch_registry("1101-2022-002636")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["uniqueNo"] == "11012022002636"

    def test_password_is_rsa_encrypted(self, codef_response: dict) -> None:
        """password 필드가 RSA 암호화되었는지 확인 (4자리 숫자)"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        with (
            patch.object(settings, "IROS_PASSWORD", "1234"),
            patch.object(settings, "CODEF_PUBLIC_KEY", "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAovKx1tTD+2/SrdvlcZXJXERanqFO9H+A8qqldYdSWO5oVug/xk98pRMBMEHCgGGZrdAJLy1DhdLJ1RX7G4/VwltG31Cff5ozBGftrhowSjri7D+to0IW/G8XEQI7A3WLV/gueKpQbVkySvIwtYIfafRHkKFy9pC83Hc5EWOBF1jBKbh0YsOOHagF86jhEFRpmZYND+XYDRgZ4kmBP9025CWgXbreeKNA4NwusF3rfizbFUorydlHNamFMAN06nCGpUqmhxh8kV5BrZA/QDCintYnT9GYmQENaEw9Nkust/O1ORJy5POgnmSst35naHu2OJoI+wLEYlxWA8F70YqqcwIDAQAB"),
        ):
            provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        # RSA 암호화된 password는 평문 "1234"가 아니어야 함
        assert payload["password"] != "1234"
        assert payload["password"] != ""
        assert len(payload["password"]) > 100  # RSA-2048 Base64 = ~344자

    def test_eprepay_pass_is_plaintext(self, codef_response: dict) -> None:
        """ePrepayPass가 평문인지 확인 (RSA 암호화 아님!)"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        with patch.object(settings, "IROS_EPREPAY_PASS", "mypassword"):
            provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        # ePrepayPass는 평문 그대로여야 함
        assert payload["ePrepayPass"] == "mypassword"

    def test_eprepay_no_in_payload(self, codef_response: dict) -> None:
        """ePrepayNo가 평문으로 payload에 포함"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        with patch.object(settings, "IROS_EPREPAY_NO", "N22578636045"):
            provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["ePrepayNo"] == "N22578636045"

    def test_phone_no_from_settings(self, codef_response: dict) -> None:
        """phoneNo가 IROS_PHONE_NO 설정에서 가져오는지 확인"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        with patch.object(settings, "IROS_PHONE_NO", "01012345678"):
            provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["phoneNo"] == "01012345678"

    def test_warning_skip_yn(self, codef_response: dict) -> None:
        """warningSkipYN=1 확인 (자동화용)"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["warningSkipYN"] == "1"

    def test_password_empty_when_not_set(self, codef_response: dict) -> None:
        """IROS_PASSWORD 미설정 시 password 빈 문자열"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        with patch.object(settings, "IROS_PASSWORD", ""):
            provider.fetch_registry("12345678901234")

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["password"] == ""

    def test_fetch_api_error_propagates(self) -> None:
        """CodefApiError가 전파되는지 확인"""
        from app.services.crawler.codef_client import CodefApiError

        mock_client = MagicMock()
        mock_client._request.side_effect = CodefApiError("CF-99999", "서버 오류")

        provider = CodefRegistryProvider(codef_client=mock_client)
        with pytest.raises(CodefApiError, match="CF-99999"):
            provider.fetch_registry("12345678901234")

    def test_source_is_codef(self, codef_response: dict) -> None:
        """source 필드가 "codef"인지 확인"""
        mock_client = MagicMock()
        mock_client._request.return_value = codef_response

        provider = CodefRegistryProvider(codef_client=mock_client)
        doc = provider.fetch_registry("12345678901234")

        assert doc.source == "codef"

    def test_two_way_auth(self) -> None:
        """추가인증 요구 시 예외 발생"""
        mock_client = MagicMock()
        mock_client._request.return_value = {
            "continue2Way": True,
            "jti": "test-jti-123",
            "twoWayTimestamp": "20260210120000",
            "resRegisterEntriesList": [],
        }

        provider = CodefRegistryProvider(codef_client=mock_client)
        with pytest.raises(RegistryTwoWayAuthRequired) as exc_info:
            provider.fetch_registry("12345678901234")
        assert exc_info.value.jti == "test-jti-123"


class TestCodefProviderSearch:
    """search_by_address mock 테스트"""

    def test_search_returns_list(self) -> None:
        """실제 CODEF 응답: data가 리스트로 반환"""
        mock_client = MagicMock()
        mock_client._request.return_value = [
            {"commUniqueNo": "11012022002636", "commAddrLotNumber": "서울특별시 강남구 삼성동", "resType": "건물"},
            {"commUniqueNo": "11012022002637", "commAddrLotNumber": "서울특별시 강남구 삼성동", "resType": "건물"},
        ]

        provider = CodefRegistryProvider(codef_client=mock_client)
        results = provider.search_by_address(
            sido="서울특별시",
            sigungu="강남구",
            address="삼성동 아이파크",
        )

        assert len(results) == 2
        assert results[0]["commUniqueNo"] == "11012022002636"

    def test_search_dict_fallback(self) -> None:
        """호환성: data가 dict인 경우 resSearchList 키 사용"""
        mock_client = MagicMock()
        mock_client._request.return_value = {
            "resSearchList": [
                {"commUniqueNo": "1234567890ABCD"},
            ]
        }

        provider = CodefRegistryProvider(codef_client=mock_client)
        results = provider.search_by_address(sido="서울특별시", sigungu="강남구", address="역삼동")

        assert len(results) == 1
        assert results[0]["commUniqueNo"] == "1234567890ABCD"

    def test_search_empty(self) -> None:
        """검색 결과 없음"""
        mock_client = MagicMock()
        mock_client._request.return_value = {}

        provider = CodefRegistryProvider(codef_client=mock_client)
        results = provider.search_by_address(sido="서울특별시", sigungu="강남구", address="없는동")

        assert results == []

    def test_search_payload_params(self) -> None:
        """주소 검색 payload 파라미터 확인"""
        mock_client = MagicMock()
        mock_client._request.return_value = []

        provider = CodefRegistryProvider(codef_client=mock_client)
        provider.search_by_address(
            sido="서울특별시",
            sigungu="강남구",
            addr_dong="역삼동",
            address="역삼동 아이파크",
            dong="101",
            ho="101",
        )

        call_args = mock_client._request.call_args
        payload = call_args[0][1]
        assert payload["addrSido"] == "서울특별시"
        assert payload["addrSigungu"] == "강남구"
        assert payload["addrDong"] == "역삼동"
        assert payload["address"] == "역삼동 아이파크"
        assert payload["dong"] == "101"
        assert payload["ho"] == "101"

    def test_search_cf13007_retry_with_realty_type_3(self) -> None:
        """CF-13007 결과 과다 → realtyType=3으로 재시도"""
        from app.services.crawler.codef_client import CodefApiError

        mock_client = MagicMock()
        # 첫 호출: CF-13007 에러, 두 번째 호출: 성공
        mock_client._request.side_effect = [
            CodefApiError("CF-13007", "검색 결과가 너무 많습니다"),
            [{"commUniqueNo": "11012022002636", "commAddrLotNumber": "강남구 삼성동"}],
        ]

        provider = CodefRegistryProvider(codef_client=mock_client)
        results = provider.search_by_address(
            sido="서울특별시",
            sigungu="강남구",
            address="삼성동 아이파크",
        )

        assert len(results) == 1
        # 두 번째 호출의 payload에서 realtyType=3 확인
        second_call = mock_client._request.call_args_list[1]
        payload = second_call[0][1]
        assert payload["realtyType"] == "3"

    def test_search_cf13007_already_realty_type_3_raises(self) -> None:
        """이미 realtyType=3인데 CF-13007이면 에러 전파"""
        from app.services.crawler.codef_client import CodefApiError

        mock_client = MagicMock()
        mock_client._request.side_effect = CodefApiError("CF-13007", "검색 결과가 너무 많습니다")

        provider = CodefRegistryProvider(codef_client=mock_client)
        with pytest.raises(CodefApiError, match="CF-13007"):
            provider.search_by_address(
                sido="서울특별시",
                sigungu="강남구",
                address="삼성동",
                realty_type="3",
            )


# ============================================================
# TestRSAEncryption — RSA 암호화 단위 테스트
# ============================================================


class TestRSAEncryption:
    """RSA 공개키 암호화 테스트"""

    @pytest.fixture()
    def rsa_keypair(self) -> tuple[str, str]:
        """테스트용 RSA 키 쌍 생성 (2048bit)"""
        import base64

        from Crypto.PublicKey import RSA

        key = RSA.generate(2048)
        public_key_b64 = base64.b64encode(key.publickey().export_key("DER")).decode()
        private_key_der = key.export_key("DER")
        private_key_b64 = base64.b64encode(private_key_der).decode()
        return public_key_b64, private_key_b64

    def test_encrypt_decrypt_roundtrip(self, rsa_keypair: tuple[str, str]) -> None:
        """암호화 → 복호화 라운드트립"""
        import base64

        from Crypto.Cipher import PKCS1_v1_5 as Cipher_PKCS1_v1_5
        from Crypto.PublicKey import RSA

        public_key_b64, private_key_b64 = rsa_keypair

        with patch.object(settings, "CODEF_PUBLIC_KEY", public_key_b64):
            encrypted = CodefRegistryProvider._encrypt_rsa("test_password_123")

        # Base64 디코드 → RSA 복호화
        cipher_text = base64.b64decode(encrypted)
        private_key = RSA.import_key(base64.b64decode(private_key_b64))
        cipher = Cipher_PKCS1_v1_5.new(private_key)
        decrypted = cipher.decrypt(cipher_text, sentinel=b"ERROR")
        assert decrypted.decode("utf-8") == "test_password_123"

    def test_encrypt_returns_base64(self, rsa_keypair: tuple[str, str]) -> None:
        """암호화 결과가 유효한 Base64 문자열"""
        import base64

        public_key_b64, _ = rsa_keypair
        with patch.object(settings, "CODEF_PUBLIC_KEY", public_key_b64):
            encrypted = CodefRegistryProvider._encrypt_rsa("hello")

        # Base64 디코딩이 성공해야 함
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 0

    def test_encrypt_no_public_key_raises(self) -> None:
        """공개키 미설정 시 RuntimeError"""
        with patch.object(settings, "CODEF_PUBLIC_KEY", ""):
            with pytest.raises(RuntimeError, match="CODEF_PUBLIC_KEY"):
                CodefRegistryProvider._encrypt_rsa("test")


# ============================================================
# TestValidation — 전화번호/전자민원캐시 검증
# ============================================================


class TestValidation:
    """전화번호, 전자민원캐시 번호 검증"""

    def test_phone_no_valid_010(self) -> None:
        assert CodefRegistryProvider.validate_phone_no("01012345678") is True

    def test_phone_no_valid_02(self) -> None:
        assert CodefRegistryProvider.validate_phone_no("0212345678") is True

    def test_phone_no_valid_070(self) -> None:
        assert CodefRegistryProvider.validate_phone_no("07012345678") is True

    def test_phone_no_invalid(self) -> None:
        assert CodefRegistryProvider.validate_phone_no("09012345678") is False

    def test_phone_no_empty(self) -> None:
        assert CodefRegistryProvider.validate_phone_no("") is False

    def test_phone_no_from_settings(self) -> None:
        with patch.object(settings, "IROS_PHONE_NO", "01099999999"):
            assert CodefRegistryProvider.validate_phone_no() is True

    def test_eprepay_no_12digits(self) -> None:
        with patch.object(settings, "IROS_EPREPAY_NO", "123456789012"):
            assert CodefRegistryProvider.validate_eprepay_no() is True

    def test_eprepay_no_wrong_length(self) -> None:
        with patch.object(settings, "IROS_EPREPAY_NO", "N22578636045"):
            result = CodefRegistryProvider.validate_eprepay_no()
            expected = len("N22578636045") == 12
            assert result is expected

    def test_eprepay_no_empty(self) -> None:
        with patch.object(settings, "IROS_EPREPAY_NO", ""):
            assert CodefRegistryProvider.validate_eprepay_no() is False
