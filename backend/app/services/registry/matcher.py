"""CODEF 검색 결과에서 경매 대상 물건 특정

CODEF search_by_address()는 해당 동의 모든 부동산을 반환한다.
이 모듈은 검색 결과에서 경매 대상 물건에 가장 일치하는 항목을 특정한다.

매칭 전략 (우선순위):
1. 지번 완전 일치 — 동 + 지번 모두 일치
2. 건물명 포함 매칭 — commAddrLotNumber에 건물명 포함
3. 동 일치 + 첫 번째 결과 — 동만 일치하는 경우 (weakest)
4. 매칭 실패 → NoMatchError

사용:
    matcher = RegistryMatcher()
    match = matcher.match(search_results, target_params)
    # → MatchResult(unique_no="114600...", confidence=1.0, ...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.address_parser import CodefAddressParams


class NoMatchError(Exception):
    """검색 결과에서 매칭되는 물건이 없음"""


@dataclass
class MatchResult:
    """매칭 결과"""

    unique_no: str          # 매칭된 고유번호
    matched_address: str    # CODEF 결과의 주소
    confidence: float       # 매칭 신뢰도 (0.0~1.0)
    match_method: str       # "lot_exact", "building_name", "dong_only", "first_result"


# 지번 패턴 (주소 문자열에서 추출)
_RE_LOT_IN_ADDR = re.compile(r"(산?\d+(?:-\d+)?)")


class RegistryMatcher:
    """CODEF 검색 결과에서 경매 대상 물건을 특정"""

    def match(
        self,
        search_results: list[dict],
        target: CodefAddressParams,
    ) -> MatchResult:
        """검색 결과에서 가장 일치하는 물건 특정

        Args:
            search_results: CODEF search_by_address() 결과 목록
                각 항목: {commUniqueNo, commAddrLotNumber, resType, ...}
            target: 파싱된 대상 주소 파라미터

        Returns:
            MatchResult

        Raises:
            NoMatchError: 매칭 결과 없음
        """
        if not search_results:
            raise NoMatchError("검색 결과가 비어있습니다")

        # 각 후보에 점수 부여
        scored: list[tuple[float, str, dict]] = []
        for item in search_results:
            addr = item.get("commAddrLotNumber", "")
            score, method = self._score(addr, target)
            scored.append((score, method, item))

        # 최고 점수 항목 선택
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_method, best_item = scored[0]

        if best_score <= 0:
            raise NoMatchError(
                f"매칭 실패: {target.dong} {target.lot_number or target.building_name}"
            )

        return MatchResult(
            unique_no=best_item.get("commUniqueNo", ""),
            matched_address=best_item.get("commAddrLotNumber", ""),
            confidence=min(best_score, 1.0),
            match_method=best_method,
        )

    def _score(
        self,
        addr: str,
        target: CodefAddressParams,
    ) -> tuple[float, str]:
        """후보 주소에 대한 매칭 점수 산출

        Returns:
            (score, method) — score가 높을수록 일치
        """
        score = 0.0
        method = "none"

        # 기본: 동 일치 확인
        dong_matches = bool(target.dong and target.dong in addr)

        # 전략 1: 지번 완전 일치
        if target.lot_number and dong_matches:
            if self._lot_matches(addr, target.dong, target.lot_number):
                return 1.0, "lot_exact"

        # 전략 2: 건물명 포함
        if target.building_name and target.building_name in addr:
            score = 0.8
            method = "building_name"
            if dong_matches:
                score = 0.9
            return score, method

        # 전략 3: 지번 부분 일치 (본번만)
        if target.lot_number and dong_matches:
            main_lot = target.lot_number.split("-")[0].replace("산", "")
            if main_lot and main_lot in addr:
                return 0.6, "lot_prefix"

        # 전략 4: 동 일치만
        if dong_matches:
            return 0.3, "dong_only"

        return score, method

    @staticmethod
    def _lot_matches(addr: str, dong: str, lot_number: str) -> bool:
        """주소에서 동 뒤의 지번이 정확히 일치하는지 확인"""
        dong_idx = addr.find(dong)
        if dong_idx < 0:
            return False

        after_dong = addr[dong_idx + len(dong):]
        lots = _RE_LOT_IN_ADDR.findall(after_dong)
        return lot_number in lots
