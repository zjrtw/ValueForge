from datetime import date

import pandas as pd
from pykrx import stock

from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter

log = get_logger(__name__)

_MARKETS = ("KOSPI", "KOSDAQ")
_rate_limiter = RateLimiter(min_delay_seconds=0.5)

_VALID_MARKETS = {"KOSPI", "KOSDAQ"}


def fetch_ticker_list(base_date: str | None = None) -> pd.DataFrame:
    """KOSPI·KOSDAQ 전 종목 코드·종목명·시장·상장주식수를 반환.

    Returns:
        columns: stock_code, stock_name, market, shares_outstanding
    """
    query_date = _normalize_date(base_date)

    # 종목기본정보(MDCSTAT01901)에서 상장주식수 일괄 수집
    stock_info = fetch_stock_listing_info()
    shares_by_code = (
        stock_info.set_index("stock_code")["shares_outstanding"].to_dict()
        if not stock_info.empty
        else {}
    )

    rows: list[dict] = []
    selected_markets = _selected_markets()

    for market in selected_markets:
        _rate_limiter.wait()
        try:
            codes: list[str] = stock.get_market_ticker_list(date=query_date, market=market)
        except Exception as exc:
            log.warning("krx ticker list fetch failed", market=market, error=str(exc))
            continue

        for code in codes:
            try:
                name: str = stock.get_market_ticker_name(code)
            except Exception as exc:
                log.warning("krx ticker name fetch failed", code=code, error=str(exc))
                name = code

            padded = str(code).zfill(6)
            rows.append({
                "stock_code": padded,
                "stock_name": name,
                "market": market,
                "shares_outstanding": shares_by_code.get(padded),
            })

    df = pd.DataFrame(rows, columns=["stock_code", "stock_name", "market", "shares_outstanding"])

    if settings.MAX_TICKERS > 0:
        df = df.head(settings.MAX_TICKERS)
        log.info("ticker count limited for testing", limit=settings.MAX_TICKERS)

    log.info("ticker collection complete", total=len(df), markets=",".join(selected_markets))
    return df


def fetch_stock_listing_info() -> pd.DataFrame:
    """KRX 종목기본정보(MDCSTAT01901)에서 전 종목 상장일·상장주식수를 일괄 수집.

    pykrx 내부 클래스를 직접 사용한다. get_market_sector_classifications 대신
    사용하는 이유: pykrx 1.2.8 기준 sector_classifications에 인코딩 버그 존재.

    Returns:
        columns: stock_code, listing_date (YYYY-MM-DD), shares_outstanding (int)
    """
    try:
        import pykrx.website.krx.market.core as _core

        # bld == MDCSTAT01901 인 클래스를 동적 탐색
        fetcher = None
        for name in dir(_core):
            obj = getattr(_core, name)
            if isinstance(obj, type) and issubclass(obj, _core.KrxWebIo if hasattr(_core, "KrxWebIo") else object):
                try:
                    instance = obj()
                    if hasattr(instance, "bld") and "01901" in str(instance.bld):
                        fetcher = instance
                        break
                except Exception:
                    continue

        if fetcher is None:
            log.warning("krx_listing_info_class_not_found")
            return _empty_listing_frame()

        _rate_limiter.wait()
        df = fetcher.fetch(mktId="ALL")
        if df.empty:
            log.warning("krx_listing_info_empty_response")
            return _empty_listing_frame()

        # 필요 컬럼 추출: ISU_SRT_CD(종목코드), LIST_DD(상장일), LIST_SHRS(상장주식수)
        needed = {"ISU_SRT_CD", "LIST_DD", "LIST_SHRS"}
        if not needed.issubset(df.columns):
            log.warning("krx_listing_info_missing_columns", columns=df.columns.tolist())
            return _empty_listing_frame()

        result = df[["ISU_SRT_CD", "LIST_DD", "LIST_SHRS"]].copy()
        result.columns = ["stock_code", "listing_date_raw", "shares_outstanding"]
        result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)

        # LIST_DD: "2008/09/23" → "2008-09-23"
        result["listing_date"] = pd.to_datetime(
            result["listing_date_raw"], format="%Y/%m/%d", errors="coerce"
        ).dt.strftime("%Y-%m-%d")

        result["shares_outstanding"] = pd.to_numeric(
            result["shares_outstanding"].astype(str).str.replace(",", ""),
            errors="coerce",
        ).astype("Int64")

        result = result[["stock_code", "listing_date", "shares_outstanding"]].dropna(subset=["stock_code"])
        log.info("krx_listing_info_collected", count=len(result))
        return result.reset_index(drop=True)

    except Exception as exc:
        log.warning("krx_listing_info_failed", error=str(exc))
        return _empty_listing_frame()


def _empty_listing_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["stock_code", "listing_date", "shares_outstanding"])


def _selected_markets() -> list[str]:
    raw_markets = settings.MARKETS.strip()
    if raw_markets.upper() in {"ALL", "BOTH"}:
        return ["KOSPI", "KOSDAQ"]

    markets = [market.strip().upper() for market in raw_markets.split(",") if market.strip()]
    invalid = [market for market in markets if market not in _VALID_MARKETS]
    if invalid or not markets:
        valid_values = "KOSPI, KOSDAQ, KOSPI,KOSDAQ, ALL"
        raise ValueError(f"Invalid MARKETS value: {settings.MARKETS}. Use one of: {valid_values}")

    return list(dict.fromkeys(markets))


def _normalize_date(base_date: str | None) -> str:
    if base_date is None:
        return date.today().strftime("%Y%m%d")
    return base_date.replace("-", "")
