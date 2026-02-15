"""경매 물건 주소 → CODEF 검색 파라미터 변환

AuctionCaseDetail.address(단일 문자열)에서 CODEF 등기부 검색에 필요한
시도/시군구/동/지번/도로명 등을 추출한다.

두 가지 형식을 처리:
1. 도로명: "서울특별시 종로구 새문안로5가길 28 지1층비109호 (적선동,광화문플래티넘)"
2. 지번:   "서울 강남구 역삼동 123-4 [건물 5층]"

사용:
    from app.services.address_parser import parse_auction_address
    params = parse_auction_address(case.address)
    # → CodefAddressParams(sido="서울특별시", sigungu="종로구", dong="적선동", ...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class AddressParseError(Exception):
    """주소 파싱 실패"""


@dataclass
class CodefAddressParams:
    """CODEF 등기부 검색에 필요한 주소 파라미터"""

    sido: str = ""                  # "서울특별시"
    sigungu: str = ""               # "강남구"
    dong: str = ""                  # "역삼동"
    lot_number: str = ""            # "123-45" 또는 "산123-4"
    road_name: str = ""             # "새문안로5가길"
    building_number: str = ""       # "28"
    building_name: str = ""         # "광화문플래티넘"
    detail: str = ""                # "지1층비109호"
    address_text: str = ""          # CODEF address 파라미터용 검색어
    warnings: list[str] = field(default_factory=list)


# ── 시도 약칭 → 정식명칭 ────────────────────────────────────

SIDO_SHORT_TO_FULL = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
}

# 정식명칭도 포함 (이미 정식이면 그대로)
SIDO_FULL_NAMES = set(SIDO_SHORT_TO_FULL.values())

# ── 정규식 패턴 ───────────────────────────────────────────

# 도로명 주소의 괄호 부분: (동,건물명) 또는 (동)
_RE_PAREN = re.compile(r"\(([^)]+)\)\s*$")

# 지번 패턴: 산123-4 또는 123-45
_RE_LOT = re.compile(r"(산?\d+(?:-\d+)?)")

# 도로명 패턴: 한글+숫자+길/로/대로 + 건물번호
# 예: "새문안로5가길 28", "남현7길 51", "테헤란로 123"
_RE_ROAD = re.compile(
    r"([\w가-힣]+(?:대로|로|길)(?:\d+가)?(?:길)?)\s+(\d+(?:-\d+)?)"
)

# 동/리/읍/면/가 이름: 역삼동, 적선동, 한솔동, 신림1동 등
_RE_DONG = re.compile(r"([\w가-힣]+\d*(?:동|리|읍|면|가))\b")

# 층/호 상세: 지1층비109호, 6층602호, 1층101호
_RE_FLOOR_UNIT = re.compile(r"((?:지?\d+층)?[\w가-힣]*\d+호)")

# 대괄호 상세: [건물 5층]
_RE_BRACKET = re.compile(r"\[([^\]]+)\]")


def _normalize_sido(token: str) -> str:
    """시도명 정규화: 약칭 → 정식명칭"""
    if token in SIDO_FULL_NAMES:
        return token
    return SIDO_SHORT_TO_FULL.get(token, token)


def _is_sigungu(token: str) -> bool:
    """시군구 토큰 여부 판별"""
    return bool(
        token.endswith(("구", "군", "시"))
        and len(token) >= 2
    )


def _is_dong(token: str) -> bool:
    """동/리/읍/면/가 토큰 여부 판별"""
    return bool(
        token.endswith(("동", "리", "읍", "면", "가"))
        and len(token) >= 2
    )


def parse_auction_address(address: str) -> CodefAddressParams:
    """경매 물건 주소 → CODEF 검색 파라미터

    Args:
        address: AuctionCaseDetail.address 문자열

    Returns:
        CodefAddressParams

    Raises:
        AddressParseError: 시도를 추출할 수 없을 때
    """
    if not address or not address.strip():
        raise AddressParseError("빈 주소")

    address = address.strip()
    result = CodefAddressParams()
    warnings: list[str] = []

    # 1. 괄호 부분 추출 (도로명 주소의 참고주소)
    paren_match = _RE_PAREN.search(address)
    paren_dong = ""
    paren_building = ""
    if paren_match:
        paren_content = paren_match.group(1)
        parts = [p.strip() for p in paren_content.split(",")]
        if parts:
            paren_dong = parts[0]
        if len(parts) >= 2:
            paren_building = parts[1]
        # 괄호 부분 제거한 본체
        body = address[: paren_match.start()].strip()
    else:
        body = address

    # 2. 대괄호 상세 추출 (지번 주소의 건물 상세)
    bracket_match = _RE_BRACKET.search(body)
    if bracket_match:
        body = body[: bracket_match.start()].strip()

    # 3. 토큰 분리
    tokens = body.split()
    if not tokens:
        raise AddressParseError(f"토큰 분리 실패: {address}")

    # 4. 시도 추출 (첫 번째 토큰)
    sido_raw = tokens[0]
    sido = _normalize_sido(sido_raw)
    if sido == sido_raw and sido not in SIDO_FULL_NAMES:
        raise AddressParseError(f"시도 인식 불가: {sido_raw}")
    result.sido = sido

    # 5. 시군구 추출 (두 번째 토큰)
    if len(tokens) >= 2 and _is_sigungu(tokens[1]):
        result.sigungu = tokens[1]
        remaining_tokens = tokens[2:]
    elif sido == "세종특별자치시":
        # 세종시는 시군구 없음
        remaining_tokens = tokens[1:]
    else:
        warnings.append(f"시군구 추출 실패: {address}")
        remaining_tokens = tokens[1:]

    # 6. 도로명 vs 지번 판별 + 동/지번/도로명 추출
    remaining_text = " ".join(remaining_tokens)

    # 도로명 패턴 시도
    road_match = _RE_ROAD.search(remaining_text)
    if road_match:
        # 도로명 주소
        result.road_name = road_match.group(1)
        result.building_number = road_match.group(2)

        # 동은 괄호에서 추출
        if paren_dong and _is_dong(paren_dong):
            result.dong = paren_dong
        elif remaining_tokens and _is_dong(remaining_tokens[0]):
            # 드물지만 "동 도로명 번호" 형태일 수 있음
            result.dong = remaining_tokens[0]

        # 건물명은 괄호에서
        if paren_building:
            result.building_name = paren_building

        # 층/호 상세
        floor_match = _RE_FLOOR_UNIT.search(remaining_text)
        if floor_match:
            result.detail = floor_match.group(1)

    else:
        # 지번 주소
        # 동 추출: remaining_tokens에서 동/리 이름 찾기
        for token in remaining_tokens:
            if _is_dong(token):
                result.dong = token
                break

        # 지번 추출
        lot_match = _RE_LOT.search(remaining_text)
        if lot_match and result.dong:
            # 동 이후의 지번만 취함
            dong_pos = remaining_text.find(result.dong)
            after_dong = remaining_text[dong_pos + len(result.dong):]
            lot_after = _RE_LOT.search(after_dong)
            if lot_after:
                result.lot_number = lot_after.group(1)
            else:
                result.lot_number = lot_match.group(1)
        elif lot_match:
            result.lot_number = lot_match.group(1)

        # 건물명: 지번 이후 남은 텍스트 (대괄호/숫자 제외)
        if result.lot_number and result.dong:
            after_lot_idx = remaining_text.find(result.lot_number)
            if after_lot_idx >= 0:
                after_lot = remaining_text[
                    after_lot_idx + len(result.lot_number) :
                ].strip()
                # 숫자/대괄호만 남으면 건물명 아님
                cleaned = re.sub(r"\[.*?\]", "", after_lot).strip()
                if cleaned and not cleaned.isdigit():
                    result.building_name = cleaned

    # 7. address_text 생성 (CODEF 검색용)
    parts = []
    if result.dong:
        parts.append(result.dong)
    if result.building_name:
        parts.append(result.building_name)
    elif result.lot_number:
        parts.append(result.lot_number)
    result.address_text = " ".join(parts) if parts else remaining_text

    result.warnings = warnings
    return result


def extract_codef_params(
    address: str,
    lot_number: str = "",
    building_name: str = "",
) -> CodefAddressParams:
    """AuctionCaseDetail에서 CODEF 파라미터 추출 (보충 정보 포함)

    address_parser의 결과에 property_objects의 구조화 데이터를 보충한다.

    Args:
        address: AuctionCaseDetail.address
        lot_number: property_objects[0].lot_number (있으면)
        building_name: property_objects[0].building_name (있으면)

    Returns:
        CodefAddressParams
    """
    params = parse_auction_address(address)

    # property_objects에서 보충
    if lot_number and not params.lot_number:
        params.lot_number = lot_number
    if building_name and not params.building_name:
        params.building_name = building_name

    # address_text 갱신 (보충 후)
    if params.building_name and params.building_name not in params.address_text:
        parts = []
        if params.dong:
            parts.append(params.dong)
        parts.append(params.building_name)
        params.address_text = " ".join(parts)

    return params
