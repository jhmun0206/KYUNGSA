"""1단 데이터 보강 (무료 공공 API 연동)

AuctionCaseDetail에 건축물대장, 용도지역, 시세 정보를 추가하여
EnrichedCase를 생성한다. 모든 API 호출은 fail-open (실패해도 진행).
"""

import logging
import time
from datetime import date

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import (
    BuildingInfo,
    EnrichedCase,
    LandUseInfo,
    MarketPriceInfo,
)
from app.services.crawler.geo_client import GeoClient
from app.services.crawler.public_api import PublicDataClient

logger = logging.getLogger(__name__)

# 서울 25개 구 시군구코드 (MVP: 서울만)
SIGUNGU_CODE_MAP: dict[str, str] = {
    "종로구": "11110",
    "중구": "11140",
    "용산구": "11170",
    "성동구": "11200",
    "광진구": "11215",
    "동대문구": "11230",
    "중랑구": "11260",
    "성북구": "11290",
    "강북구": "11305",
    "도봉구": "11320",
    "노원구": "11350",
    "은평구": "11380",
    "서대문구": "11410",
    "마포구": "11440",
    "양천구": "11470",
    "강서구": "11500",
    "구로구": "11530",
    "금천구": "11545",
    "영등포구": "11560",
    "동작구": "11590",
    "관악구": "11620",
    "서초구": "11650",
    "강남구": "11680",
    "송파구": "11710",
    "강동구": "11740",
}


class CaseEnricher:
    """경매 물건 데이터 보강기

    AuctionCaseDetail에 공공 API 데이터를 결합하여 EnrichedCase를 생성한다.
    모든 외부 API 호출은 try/except로 감싸며, 실패 시 해당 필드를 None으로 둔다.
    """

    def __init__(
        self,
        geo_client: GeoClient | None = None,
        public_client: PublicDataClient | None = None,
    ) -> None:
        self._geo = geo_client or GeoClient()
        self._public = public_client or PublicDataClient()

    def enrich(self, case: AuctionCaseDetail) -> EnrichedCase:
        """단일 물건 보강"""
        enriched = EnrichedCase(case=case)

        # 1. 주소 → 좌표
        enriched.coordinates = self._geocode(case)

        # 2. 좌표 → 용도지역 (좌표 없으면 스킵)
        if enriched.coordinates:
            enriched.land_use = self._fetch_land_use(
                enriched.coordinates["x"], enriched.coordinates["y"]
            )

        # 3. 건축물대장 조회
        enriched.building = self._fetch_building(case)

        # 4. 시세 조회
        enriched.market_price = self._fetch_market_price(case)

        return enriched

    def enrich_batch(
        self, cases: list[AuctionCaseDetail], delay: float = 2.0
    ) -> list[EnrichedCase]:
        """배치 보강 (API rate limit 준수)"""
        results: list[EnrichedCase] = []
        for i, case in enumerate(cases):
            if i > 0:
                time.sleep(delay)
            try:
                enriched = self.enrich(case)
                results.append(enriched)
            except Exception as e:
                logger.error("보강 실패 [%s]: %s", case.case_number, e)
                results.append(EnrichedCase(case=case))
        return results

    # --- private helpers ---

    def _geocode(self, case: AuctionCaseDetail) -> dict | None:
        """주소를 좌표로 변환"""
        address = self._extract_address(case)
        if not address:
            return None
        try:
            return self._geo.geocode(address)
        except Exception as e:
            logger.warning("Geocode 실패 [%s]: %s", case.case_number, e)
            return None

    def _fetch_land_use(self, x: str, y: str) -> LandUseInfo | None:
        """좌표 기준 용도지역 조회"""
        try:
            items = self._geo.fetch_land_use(x, y)
            zones: list[str] = []
            for item in items:
                # Vworld LT_C_UQ111 응답: uname(원본) → name(매핑)
                for key in ("name", "uname"):
                    val = item.get(key, "")
                    if val and val != "미분류" and val not in zones:
                        zones.append(val)
            is_greenbelt = any(
                "개발제한" in z or "그린벨트" in z for z in zones
            )
            return LandUseInfo(
                zones=zones,
                is_greenbelt=is_greenbelt,
                raw_items=items,
            )
        except Exception as e:
            logger.warning("용도지역 조회 실패: %s", e)
            return None

    def _fetch_building(self, case: AuctionCaseDetail) -> BuildingInfo | None:
        """건축물대장 조회"""
        params = self._extract_building_params(case)
        if not params:
            return None
        try:
            items = self._public.fetch_building_register(**params)
            if not items:
                return None
            first = items[0]
            # 위반건축물 여부: 관련 필드에서 "위반" 키워드 탐색
            violation = any("위반" in str(v) for v in first.values())
            return BuildingInfo(
                main_purpose=first.get("mainPurpsCdNm", ""),
                structure=first.get("strctCdNm", ""),
                total_area=_safe_float(first.get("totArea", "")),
                use_approve_date=first.get("useAprDay", ""),
                violation=violation,
                raw_items=items,
            )
        except Exception as e:
            logger.warning("건축물대장 조회 실패 [%s]: %s", case.case_number, e)
            return None

    def _fetch_market_price(self, case: AuctionCaseDetail) -> MarketPriceInfo | None:
        """시세 정보 조회 (아파트 매매 실거래가)"""
        lawd_cd = self._extract_lawd_cd(case)
        if not lawd_cd:
            return None
        deal_ymd = _recent_deal_ymd()
        try:
            trades = self._public.fetch_apt_trade(lawd_cd, deal_ymd)
            if not trades:
                return MarketPriceInfo(
                    trade_count=0,
                    reference_period=deal_ymd,
                    lawd_cd=lawd_cd,
                )
            avg = _calc_avg_price_per_m2(trades)
            return MarketPriceInfo(
                avg_price_per_m2=avg,
                recent_trades=trades[:10],
                trade_count=len(trades),
                reference_period=deal_ymd,
                lawd_cd=lawd_cd,
            )
        except Exception as e:
            logger.warning("시세 조회 실패 [%s]: %s", case.case_number, e)
            return None

    # --- 주소/파라미터 추출 ---

    @staticmethod
    def _extract_address(case: AuctionCaseDetail) -> str:
        """geocode용 주소 추출"""
        if case.property_objects:
            addr = case.property_objects[0].address
            if addr:
                return addr
        return case.address

    @staticmethod
    def _extract_building_params(case: AuctionCaseDetail) -> dict | None:
        """건축물대장 API 파라미터 추출"""
        address = case.address
        sigungu_cd = None
        for gu_name, code in SIGUNGU_CODE_MAP.items():
            if gu_name in address:
                sigungu_cd = code
                break
        if not sigungu_cd:
            return None

        # 지번에서 본번/부번 추출
        lot = case.lot_number
        if not lot and case.property_objects:
            lot = case.property_objects[0].lot_number
        # fallback: 주소 문자열에서 지번 추출 (동 뒤의 숫자-숫자)
        if not lot:
            import re
            m = re.search(r"[동리가]\s+(산?\d+(?:-\d+)?)", address)
            if m:
                lot = m.group(1)
        if not lot:
            return None

        bun, ji = _parse_lot_number(lot)
        if not bun:
            return None

        return {
            "sigungu_cd": sigungu_cd,
            "bjdong_cd": "00000",  # MVP: 전체 조회
            "bun": bun,
            "ji": ji,
        }

    @staticmethod
    def _extract_lawd_cd(case: AuctionCaseDetail) -> str:
        """시세 API용 법정동코드(5자리) 추출"""
        for gu_name, code in SIGUNGU_CODE_MAP.items():
            if gu_name in case.address:
                return code
        return ""


# --- 모듈 수준 유틸리티 ---


def _parse_lot_number(lot: str) -> tuple[str, str]:
    """지번 문자열에서 본번/부번 추출

    "156"      → ("0156", "0000")
    "1086-12"  → ("1086", "0012")
    """
    if not lot:
        return ("", "")
    lot = lot.strip()
    if "-" in lot:
        parts = lot.split("-", 1)
        bun = parts[0].zfill(4)
        ji = parts[1].zfill(4)
    else:
        bun = lot.zfill(4)
        ji = "0000"
    return (bun, ji)


def _recent_deal_ymd() -> str:
    """최근 거래 조회용 년월"""
    return date.today().strftime("%Y%m")


def _calc_avg_price_per_m2(trades: list[dict]) -> float | None:
    """거래 목록에서 평균 단가 (원/㎡) 산출"""
    prices: list[float] = []
    for t in trades:
        amount_str = t.get("dealAmount", "").replace(",", "").strip()
        area_str = t.get("excluUseAr", "").strip()
        if not amount_str or not area_str:
            continue
        try:
            amount = int(amount_str) * 10_000  # 만원 → 원
            area = float(area_str)
            if area > 0:
                prices.append(amount / area)
        except (ValueError, TypeError):
            continue
    if not prices:
        return None
    return sum(prices) / len(prices)


def _safe_float(text: str) -> float | None:
    """문자열 → float (실패 시 None)"""
    if not text:
        return None
    try:
        return float(str(text).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
