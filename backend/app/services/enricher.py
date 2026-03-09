"""1단 데이터 보강 (무료 공공 API 연동)

AuctionCaseDetail에 건축물대장, 용도지역, 시세 정보를 추가하여
EnrichedCase를 생성한다. 모든 API 호출은 fail-open (실패해도 진행).
"""

import logging
import time
from datetime import date, timedelta

from app.models.auction import AuctionCaseDetail
from app.models.enriched_case import (
    BuildingInfo,
    EnrichedCase,
    LandUseInfo,
    LocationData,
    MarketPriceInfo,
    RentAreaRange,
    RentPriceInfo,
)
from app.services.crawler.geo_client import GeoClient
from app.services.crawler.public_api import PublicDataClient

logger = logging.getLogger(__name__)

# 면적 구간 기준 (label, min_m2 이상, max_m2 미만)
_AREA_RANGES: list[tuple[str, float, float]] = [
    ("10㎡ 미만", 0.0, 10.0),
    ("10~20㎡", 10.0, 20.0),
    ("20~40㎡", 20.0, 40.0),
    ("40~60㎡", 40.0, 60.0),
    ("60~85㎡", 60.0, 85.0),
    ("85㎡ 초과", 85.0, 9999.0),
]

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

        # 2. 좌표 → 용도지역 + 입지 데이터 (좌표 없으면 스킵)
        if enriched.coordinates:
            x, y = enriched.coordinates["x"], enriched.coordinates["y"]
            enriched.land_use = self._fetch_land_use(x, y)
            enriched.location_data = self._fetch_location_data(x, y)

        # 3. 건축물대장 조회 (geocode 결과의 지번 정보 활용)
        enriched.building = self._fetch_building(case, enriched.coordinates)

        # 4. 시세 조회
        enriched.market_price = self._fetch_market_price(case)

        # 5. 월세 실거래가 조회 (좌표 있을 때만)
        if enriched.coordinates:
            enriched.rent_price = self._fetch_rent_price_info(
                case,
                enriched.coordinates,
                enriched.building,
            )

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

    def _fetch_building(
        self, case: AuctionCaseDetail, coords: dict | None = None
    ) -> BuildingInfo | None:
        """건축물대장 조회"""
        params = self._extract_building_params(case, coords)
        if not params:
            logger.debug("건축물대장 params 추출 실패 [%s]", case.case_number)
            return None
        try:
            items = self._public.fetch_building_register(**params)
            if not items:
                logger.info("건축물대장 응답 비어있음 [%s] params=%s", case.case_number, params)
                return None
            logger.info("건축물대장 %d건 수신 [%s]", len(items), case.case_number)
            first = items[0]
            # 위반건축물 여부: 관련 필드에서 "위반" 키워드 탐색
            violation = any("위반" in str(v) for v in first.values())
            # 건축년도 (사용승인일 앞 4자리)
            use_apr = first.get("useAprDay", "")
            build_year = _safe_int(use_apr[:4]) if len(use_apr) >= 4 else None
            info = BuildingInfo(
                main_purpose=first.get("mainPurpsCdNm", ""),
                structure=first.get("strctCdNm", ""),
                total_area=_safe_float(first.get("totArea", "")),
                exclusive_area_m2=_safe_float(first.get("platArea", "")),
                ground_floors=_safe_int(first.get("grndFlrCnt", "")),
                underground_floors=_safe_int(first.get("ugrndFlrCnt", "")),
                units_count=_safe_int(first.get("hhldCnt", "")) or _safe_int(first.get("hoCnt", "")),
                build_year=build_year,
                use_approve_date=use_apr,
                violation=violation,
                raw_items=items,
            )
            logger.info(
                "BuildingInfo 생성 [%s]: purpose=%s area=%.1f floors=%s year=%s",
                case.case_number,
                info.main_purpose,
                info.total_area or 0,
                info.ground_floors,
                info.build_year,
            )

            # 전유부 호실별 면적 조회 (fail-open)
            try:
                units = self._public.fetch_building_units(**params)
                if units:
                    info.units = units
                    logger.info("전유부 %d호실 수신 [%s]", len(units), case.case_number)
            except Exception as e:
                logger.warning("전유부 조회 실패 [%s]: %s", case.case_number, e)

            return info
        except Exception as e:
            logger.warning("건축물대장 조회 실패 [%s]: %s", case.case_number, e)
            return None

    def _fetch_location_data(self, x: str, y: str) -> LocationData | None:
        """카카오 카테고리 검색으로 입지 데이터 수집 (fail-open)

        카테고리별로 독립 호출하며, 실패한 카테고리는 건너뛴다.
        categories_fetched에는 성공한 카테고리 코드만 기록된다.
        """
        fetched: list[str] = []
        nearest_station_m: int | None = None
        station_count_1km = 0
        nearest_school_m: int | None = None
        school_count_1km = 0
        amenity_count_500m = 0

        # 지하철역 (SW8, 반경 2000m)
        try:
            stations = self._geo.search_nearby_category(x, y, "SW8", radius=2000)
            fetched.append("SW8")
            if stations:
                dists = [int(p.get("distance", 0)) for p in stations if p.get("distance")]
                if dists:
                    nearest_station_m = min(dists)
                    station_count_1km = sum(1 for d in dists if d <= 1000)
        except Exception as e:
            logger.warning("지하철역 검색 실패 [SW8]: %s", e)

        # 학교 (SC4, 반경 1500m)
        try:
            schools = self._geo.search_nearby_category(x, y, "SC4", radius=1500)
            fetched.append("SC4")
            if schools:
                dists = [int(p.get("distance", 0)) for p in schools if p.get("distance")]
                if dists:
                    nearest_school_m = min(dists)
                    school_count_1km = sum(1 for d in dists if d <= 1000)
        except Exception as e:
            logger.warning("학교 검색 실패 [SC4]: %s", e)

        # 편의시설 (MT1=마트, CS2=편의점, HP8=병원, 반경 500m)
        amenity_total = 0
        for code in ("MT1", "CS2", "HP8"):
            try:
                places = self._geo.search_nearby_category(x, y, code, radius=500)
                fetched.append(code)
                amenity_total += len(places)
            except Exception as e:
                logger.warning("편의시설 검색 실패 [%s]: %s", code, e)
        amenity_count_500m = amenity_total

        return LocationData(
            nearest_station_m=nearest_station_m,
            station_count_1km=station_count_1km,
            nearest_school_m=nearest_school_m,
            school_count_1km=school_count_1km,
            amenity_count_500m=amenity_count_500m,
            categories_fetched=fetched,
        )

    def _fetch_rent_price_info(
        self,
        case: AuctionCaseDetail,
        coords: dict,
        building: BuildingInfo | None,
    ) -> RentPriceInfo | None:
        """월세 실거래가 조회 (면적 구간별 분류)

        좌표의 b_code 앞 5자리를 lawd_cd로 사용하여 최근 3개월 조회.
        property_type에 따라 API 선택:
          아파트 → apt_rent, 오피스텔 → office_rent, 다세대/연립/빌라 → rh_rent
          기타 → rh_rent + office_rent 모두
        면적 구간별로 그룹화 (count < 2인 구간은 제외).
        전체 sample_count < 3이면 None 반환.
        """
        # lawd_cd 추출 (b_code 앞 5자리)
        b_code = coords.get("b_code", "")
        if not b_code or len(b_code) < 5:
            return None
        lawd_cd = b_code[:5]

        # 조회 월 목록 (현재월 + 직전 2개월)
        today = date.today()
        months: list[str] = []
        for i in range(3):
            d = (today.replace(day=1) - timedelta(days=1) * (i * 31)).replace(day=1)
            months.append(d.strftime("%Y%m"))
        months = sorted(set(months), reverse=True)[:3]

        # property_type 기반 API 선택
        pt = case.property_type or ""
        raw_rows: list[dict[str, str]] = []
        try:
            if "아파트" in pt:
                for ym in months:
                    raw_rows.extend(self._public.fetch_apt_rent(lawd_cd, ym))
                source = "아파트"
            elif "오피스텔" in pt:
                for ym in months:
                    raw_rows.extend(self._public.fetch_office_rent(lawd_cd, ym))
                source = "오피스텔"
            elif any(k in pt for k in ("다세대", "연립", "빌라", "단독", "다가구")):
                for ym in months:
                    raw_rows.extend(self._public.fetch_rh_rent(lawd_cd, ym))
                source = "연립다세대"
            else:
                for ym in months:
                    raw_rows.extend(self._public.fetch_rh_rent(lawd_cd, ym))
                    raw_rows.extend(self._public.fetch_office_rent(lawd_cd, ym))
                source = "연립다세대+오피스텔"
        except Exception as e:
            logger.warning("월세 실거래가 조회 실패 [%s]: %s", case.case_number, e)
            return None

        if not raw_rows:
            logger.debug("월세 실거래가 없음 [%s] lawd_cd=%s", case.case_number, lawd_cd)
            return None

        # 월세 거래만 필터링 (월세=0은 전세)
        rent_rows = [r for r in raw_rows if (_safe_int_str(r.get("monthlyRent", "0")) or 0) > 0]

        if len(rent_rows) < 3:
            logger.debug(
                "월세 샘플 부족 [%s]: %d건 (최소 3건 필요)", case.case_number, len(rent_rows)
            )
            return None

        # 면적 구간별 그룹화
        by_area_range: list[RentAreaRange] = []
        for label, lo, hi in _AREA_RANGES:
            bucket: list[dict] = []
            for r in rent_rows:
                area = _safe_float_str(r.get("excluUseAr", "") or r.get("exclusiveArea", ""))
                if area is not None and lo <= area < hi:
                    bucket.append(r)
            if len(bucket) < 2:
                continue
            rents = [v for v in (_safe_float_str(r.get("monthlyRent", "")) for r in bucket) if v is not None]
            deps = [v for v in (_safe_float_str(r.get("deposit", "") or r.get("leaseAmount", "")) for r in bucket) if v is not None]
            if not rents:
                continue
            by_area_range.append(RentAreaRange(
                range=label,
                min_m2=lo,
                max_m2=hi,
                avg_rent=round(sum(rents) / len(rents), 1),
                avg_deposit=round(sum(deps) / len(deps), 0) if deps else 0.0,
                count=len(bucket),
            ))

        # 전체 평균 (fallback)
        all_rents = [v for v in (_safe_float_str(r.get("monthlyRent", "")) for r in rent_rows) if v is not None]
        all_deps = [v for v in (_safe_float_str(r.get("deposit", "") or r.get("leaseAmount", "")) for r in rent_rows) if v is not None]
        overall_avg_rent = round(sum(all_rents) / len(all_rents), 1) if all_rents else None
        overall_avg_deposit = round(sum(all_deps) / len(all_deps), 0) if all_deps else None

        logger.info(
            "월세 정보 [%s]: 구간=%d개 전체=%d건 avg=%.0f만원",
            case.case_number, len(by_area_range), len(rent_rows), overall_avg_rent or 0,
        )
        return RentPriceInfo(
            by_area_range=by_area_range,
            overall_avg_rent=overall_avg_rent,
            overall_avg_deposit=overall_avg_deposit,
            sample_count=len(rent_rows),
            source=source,
            lawd_cd=lawd_cd,
            queried_months=months,
        )

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
            if addr and addr.strip():
                return addr.strip()
        return case.address.strip() if case.address else ""

    @staticmethod
    def _extract_building_params(
        case: AuctionCaseDetail, coords: dict | None = None
    ) -> dict | None:
        """건축물대장 API 파라미터 추출

        우선순위:
        1. geocode 결과의 b_code + main/sub_address_no (가장 정확)
        2. case.lot_number / property_objects[0].lot_number (크롤러 rprsLtnoAddr)
        3. 주소 문자열 regex fallback (지번 주소만 매칭)
        """
        import re

        address = case.address

        # --- 방법 1: geocode 결과의 지번 정보 (도로명 주소에서도 동작) ---
        if coords:
            b_code = coords.get("b_code", "")
            main_no = coords.get("main_address_no", "")
            if b_code and len(b_code) >= 10 and main_no:
                sigungu_cd = b_code[:5]
                bjdong_cd = b_code[5:10]
                bun = main_no.zfill(4)
                sub_no = coords.get("sub_address_no", "")
                ji = sub_no.zfill(4) if sub_no else "0000"
                logger.debug(
                    "건축물대장 params (geocode): %s-%s %s-%s [%s]",
                    sigungu_cd, bjdong_cd, bun, ji, case.case_number,
                )
                return {
                    "sigungu_cd": sigungu_cd,
                    "bjdong_cd": bjdong_cd,
                    "bun": bun,
                    "ji": ji,
                }

        # --- SIGUNGU 코드 (방법 2, 3에서 사용) ---
        sigungu_cd = None
        for gu_name, code in SIGUNGU_CODE_MAP.items():
            if gu_name in address:
                sigungu_cd = code
                break
        if not sigungu_cd:
            return None

        # --- 방법 2: 크롤러 lot_number (rprsLtnoAddr) ---
        lot = case.lot_number
        if not lot and case.property_objects:
            lot = case.property_objects[0].lot_number

        # --- 방법 3: 주소 regex fallback (지번 주소) ---
        if not lot:
            # "동 421-21", "리 산15" 패턴 매칭
            # 오탐 방지: "동" 뒤에 숫자가 바로 오는 경우만 (층/호 제외)
            m = re.search(r"[동리]\s+(산?\d+(?:-\d+)?)\b", address)
            if m:
                # 매칭된 지번 뒤에 "층", "호"가 오면 오탐 (예: "다동 3층")
                after = address[m.end():]
                if not re.match(r"\s*[층호]", after):
                    lot = m.group(1)

        if not lot:
            return None

        bun, ji = _parse_lot_number(lot)
        if not bun:
            return None

        return {
            "sigungu_cd": sigungu_cd,
            "bjdong_cd": "00000",  # 방법 2,3은 bjdong 불명 → 전체 조회
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


def _safe_float_str(text: str | None) -> float | None:
    """문자열 → float (실패 또는 None 입력 시 None, 0이면 None)"""
    if not text:
        return None
    try:
        v = float(str(text).replace(",", "").strip())
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _safe_int_str(text: str | None) -> int | None:
    """문자열 → int (실패 또는 None 입력 시 None, 0이면 None)"""
    if not text:
        return None
    try:
        v = int(str(text).replace(",", "").strip())
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _safe_float(text: str) -> float | None:
    """문자열 → float (실패 시 None)"""
    if not text:
        return None
    try:
        return float(str(text).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_int(text: str) -> int | None:
    """문자열 → int (실패 시 None, 0이면 None)"""
    if not text:
        return None
    try:
        v = int(str(text).replace(",", "").strip())
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None
