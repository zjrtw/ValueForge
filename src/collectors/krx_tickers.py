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
    """KOSPI·KOSDAQ 전 종목 코드·종목명·시장을 DataFrame으로 반환.

    pykrx를 이용하여 KRX 전체 종목을 수집한다.

    Args:
        base_date: 조회 기준일 (YYYY-MM-DD 또는 YYYYMMDD). None이면 오늘.

    Returns:
        columns: stock_code (str), stock_name (str), market (str)
    """
    query_date = _normalize_date(base_date)

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
                name = code  # 이름 조회 실패 시 코드로 대체

            rows.append({
                "stock_code": str(code).zfill(6),
                "stock_name": name,
                "market": market,
            })

    df = pd.DataFrame(rows, columns=["stock_code", "stock_name", "market"])

    if settings.MAX_TICKERS > 0:
        df = df.head(settings.MAX_TICKERS)
        log.info("ticker count limited for testing", limit=settings.MAX_TICKERS)

    log.info("ticker collection complete", total=len(df), markets=",".join(selected_markets))
    return df


def _selected_markets() -> list[str]:
    """Return markets selected by MARKETS env setting."""
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
    """pykrx용 날짜 문자열(YYYYMMDD)로 정규화."""
    if base_date is None:
        return date.today().strftime("%Y%m%d")
    return base_date.replace("-", "")
