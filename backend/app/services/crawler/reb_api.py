"""한국부동산원 R-ONE Open API 클라이언트

상업용부동산 임대동향조사 — 지역별 소규모/중대형 상가 임대료 및 공실률.
분기 갱신 데이터이므로 별도 캐싱 없이 매 요청 시 호출.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

REB_API_BASE = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"

# 핵심 통계표 ID
STATBL_SMALL_SHOP_RENT = "T248223134698125"     # 소규모 상가 지역별 임대료
STATBL_MEDIUM_SHOP_RENT = "T244363134858603"    # 중대형 상가 지역별 임대료
STATBL_SMALL_SHOP_VACANCY = "T241833134686576"  # 소규모 상가 지역별 공실률


class RebApiClient:
    """한국부동산원 R-ONE Open API 클라이언트"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_rent_by_region(
        self,
        statbl_id: str,
        region: str,
    ) -> Optional[dict]:
        """지역별 상가 임대료/공실률 조회

        Args:
            statbl_id: 통계표 ID (STATBL_* 상수)
            region: 지역명 (예: "강남구", "서울")

        Returns:
            {
                "region": "강남구",
                "value": 45200,          # 원/㎡/월 (임대료) 또는 % (공실률)
                "unit": "원/㎡/월",
                "period": "2024년 3분기",
                "source": "한국부동산원 상업용부동산 임대동향조사"
            }
            또는 None (데이터 없거나 조회 실패)
        """
        params = {
            "KEY": self.api_key,
            "Type": "json",
            "pIndex": 1,
            "pSize": 500,
            "STATBL_ID": statbl_id,
            "DTACYCLE_CD": "QY",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(REB_API_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()

            # 응답 구조: [{"head": [...]}, {"row": [...]}]
            body = data.get("SttsApiTblData", [])
            rows = body[1].get("row", []) if len(body) > 1 else []

            # CLS_FULLNM = "서울>강남구", CLS_NM = "강남구"
            matched = [
                r for r in rows
                if region in (r.get("CLS_FULLNM") or "")
                or region == (r.get("CLS_NM") or "")
            ]
            if not matched:
                return None

            # 최신 시점 기준 정렬 (WRTTIME_IDTFR_ID: "2024Q3" 형태)
            matched.sort(
                key=lambda x: x.get("WRTTIME_IDTFR_ID") or "",
                reverse=True,
            )
            latest = matched[0]

            raw_val = latest.get("DTA_VAL")
            if raw_val is None:
                return None
            try:
                raw_val = float(raw_val)
            except (ValueError, TypeError):
                return None

            ui_nm = latest.get("UI_NM", "")

            # 단위 변환: 천원/㎡ → 원/㎡
            if "천원" in ui_nm:
                value = int(raw_val * 1000)
                unit = "원/㎡/월"
            else:
                value = raw_val
                unit = ui_nm

            return {
                "region": latest.get("CLS_NM") or region,
                "value": value,
                "unit": unit,
                "period": latest.get("WRTTIME_DESC") or "",
                "source": "한국부동산원 상업용부동산 임대동향조사",
            }
        except Exception as e:
            logger.warning("REB API 조회 실패 [%s/%s]: %s", statbl_id, region, e)
            return None
