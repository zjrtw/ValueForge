from datetime import date

import pandas as pd

from src.collectors.krx_client import fetch_issue_base_info
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_MARKET_ENDPOINTS: dict[str, str] = {
    "KOSPI": "stk_isu_base_info",
    "KOSDAQ": "ksq_isu_base_info",
}
_VALID_MARKETS = {"KOSPI", "KOSDAQ"}


def fetch_ticker_list(base_date: str | None = None) -> pd.DataFrame:
    """KOSPI·KOSDAQ 전 종목 코드·종목명·시장·상장주식수를 반환.

    기준일 데이터가 없으면 자동으로 이전 거래일 재시도 (KRX API T+1~T+2 지연 대응).

    Returns:
        columns: stock_code, stock_name, market, shares_outstanding
    """
    from datetime import timedelta

    from src.utils.market_calendar import prev_trading_day

    bas_dd = _normalize_date(base_date)
    rows: list[dict] = []

    for market in _selected_markets():
        endpoint = _MARKET_ENDPOINTS[market]
        try:
            items = fetch_issue_base_info(endpoint, bas_dd)
        except Exception as exc:
            log.warning("krx ticker list fetch failed", market=market, error=str(exc))
            continue

        # KRX API에서 결과 없으면 이전 거래일로 재시도
        if not items:
            try:
                prev_date_obj = prev_trading_day(date.fromisoformat(bas_dd[:4] + "-" + bas_dd[4:6] + "-" + bas_dd[6:8]) - timedelta(days=1))
                prev_bas_dd = prev_date_obj.strftime("%Y%m%d")
                log.info("krx ticker list empty, retrying with previous trading day", endpoint=endpoint, original=bas_dd, retry=prev_bas_dd)
                items = fetch_issue_base_info(endpoint, prev_bas_dd)
            except Exception as exc:
                log.warning("krx ticker list fetch failed on retry", market=market, error=str(exc))
                items = []

        for item in items:
            code = _parse_code(item.get("ISU_SRT_CD"))
            if not code:
                continue
            rows.append({
                "stock_code": code,
                "stock_name": item.get("ISU_ABBRV") or item.get("ISU_NM") or code,
                "market": market,
                "shares_outstanding": _parse_int(item.get("LIST_SHRS")),
            })

    df = pd.DataFrame(rows, columns=["stock_code", "stock_name", "market", "shares_outstanding"])

    if settings.MAX_TICKERS > 0:
        df = df.head(settings.MAX_TICKERS)
        log.info("ticker count limited for testing", limit=settings.MAX_TICKERS)

    log.info("ticker collection complete", total=len(df), markets=",".join(_selected_markets()))
    return df


def fetch_stock_listing_info() -> pd.DataFrame:
    """전 종목 상장일·상장주식수를 반환.

    Returns:
        columns: stock_code, listing_date (YYYY-MM-DD), shares_outstanding
    """
    bas_dd = _normalize_date(None)
    rows: list[dict] = []

    for market in ("KOSPI", "KOSDAQ"):
        endpoint = _MARKET_ENDPOINTS[market]
        try:
            items = fetch_issue_base_info(endpoint, bas_dd)
        except Exception as exc:
            log.warning("krx listing info fetch failed", market=market, error=str(exc))
            continue

        for item in items:
            code = _parse_code(item.get("ISU_SRT_CD"))
            if not code:
                continue
            rows.append({
                "stock_code": code,
                "listing_date": _parse_listing_date(item.get("LIST_DD")),
                "shares_outstanding": _parse_int(item.get("LIST_SHRS")),
            })

    result = pd.DataFrame(rows, columns=["stock_code", "listing_date", "shares_outstanding"])
    log.info("listing info collection complete", total=len(result))
    return result


def _parse_code(raw: object) -> str:
    """ISU_SRT_CD 값을 6자리 문자열로 정규화. 유효하지 않으면 빈 문자열 반환."""
    if raw is None:
        return ""
    code = str(raw).strip().zfill(6)
    return "" if code == "000000" or not code.isdigit() else code


def _parse_int(raw: object) -> int | None:
    """쉼표 포함 숫자 문자열을 int로 변환."""
    if raw is None:
        return None
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _parse_listing_date(raw: object) -> str | None:
    """LIST_DD를 YYYY-MM-DD 형식으로 정규화.

    KRX API 포맷: 'YYYYMMDD' 또는 'YYYY/MM/DD'
    """
    if raw is None:
        return None
    digits = str(raw).strip().replace("/", "").replace("-", "")
    if len(digits) != 8 or not digits.isdigit():
        return None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def _selected_markets() -> list[str]:
    raw = settings.MARKETS.strip()
    if raw.upper() in {"ALL", "BOTH"}:
        return ["KOSPI", "KOSDAQ"]
    markets = [m.strip().upper() for m in raw.split(",") if m.strip()]
    invalid = [m for m in markets if m not in _VALID_MARKETS]
    if invalid or not markets:
        raise ValueError(
            f"Invalid MARKETS value: {settings.MARKETS!r}. Use one of: KOSPI, KOSDAQ, KOSPI,KOSDAQ, ALL"
        )
    return list(dict.fromkeys(markets))


def _normalize_date(base_date: str | None) -> str:
    if base_date is None:
        return date.today().strftime("%Y%m%d")
    return base_date.replace("-", "")
