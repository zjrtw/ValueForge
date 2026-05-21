from collections.abc import Iterable
from datetime import date, datetime, timedelta

import pandas as pd
from pykrx import stock

from src.collectors.krx_tickers import fetch_ticker_list
from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter

log = get_logger(__name__)

_MARKETS = ("KOSPI", "KOSDAQ")
_rate_limiter = RateLimiter(min_delay_seconds=0.5)


def fetch_daily_price_data(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    markets: Iterable[str] = _MARKETS,
) -> pd.DataFrame:
    """KRX 일별 주가·기본 지표를 시장 단위로 수집한다.

    반환 컬럼:
        stock_code, date, close, trading_value, market_cap,
        per, pbr, dividend_yield, market
    """
    query_date = _normalize_query_date(base_date)
    output_date = _format_output_date(query_date)

    ticker_df = tickers if tickers is not None else fetch_ticker_list(query_date)
    ticker_df = ticker_df[["stock_code", "market"]].copy()
    ticker_df["stock_code"] = ticker_df["stock_code"].astype(str).str.zfill(6)

    frames: list[pd.DataFrame] = []
    for market in markets:
        market = market.upper()
        market_tickers = ticker_df[ticker_df["market"] == market]
        if market_tickers.empty:
            continue

        try:
            market_df = _fetch_market_price_data(query_date, market)
        except Exception as exc:
            log.warning("krx daily price collection failed", market=market, error=str(exc))
            continue

        market_df = market_df[market_df["stock_code"].isin(market_tickers["stock_code"])]
        frames.append(market_df)

    if not frames:
        return _empty_price_frame()

    result = pd.concat(frames, ignore_index=True)
    result.insert(1, "date", output_date)

    if settings.MAX_TICKERS > 0:
        result = result.head(settings.MAX_TICKERS)
        log.info("daily price count limited for testing", limit=settings.MAX_TICKERS)

    log.info("daily price collection complete", date=output_date, total=len(result))
    return result[
        [
            "stock_code",
            "date",
            "close",
            "trading_value",
            "market_cap",
            "per",
            "pbr",
            "dividend_yield",
            "market",
        ]
    ].reset_index(drop=True)


def fetch_avg_trading_value_20d(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    lookback_days: int = 30,
    window: int = 20,
) -> pd.DataFrame:
    """종목별 최근 20거래일 평균 거래대금을 산출한다.

    pykrx의 종목별 OHLCV 기간 조회 결과에서 최신 ``window``개 행만 사용한다.

    반환 컬럼:
        stock_code, date, avg_trading_value_20d
    """
    query_date = _normalize_query_date(base_date)
    output_date = _format_output_date(query_date)
    start_date = _shift_query_date(query_date, days=-lookback_days)

    ticker_df = tickers if tickers is not None else fetch_ticker_list(query_date)
    codes = ticker_df["stock_code"].astype(str).str.zfill(6).tolist()

    if settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]
        log.info("avg trading value count limited for testing", limit=settings.MAX_TICKERS)

    rows: list[dict] = []
    for code in codes:
        try:
            ohlcv = _rate_limiter.throttle(stock.get_market_ohlcv)(start_date, query_date, code)
        except Exception as exc:
            log.warning("krx ohlcv history collection failed", stock_code=code, error=str(exc))
            continue

        avg_value = _compute_avg_trading_value(ohlcv, window=window)
        rows.append(
            {
                "stock_code": code,
                "date": output_date,
                "avg_trading_value_20d": avg_value,
            }
        )

    result = pd.DataFrame(rows, columns=["stock_code", "date", "avg_trading_value_20d"])
    log.info("avg trading value collection complete", date=output_date, total=len(result))
    return result


def fetch_price_history_1y(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    lookback_days: int = 370,
    max_rows_per_ticker: int = 252,
) -> pd.DataFrame:
    """모멘텀 계산용 최근 1년 OHLCV 이력을 수집한다.

    pykrx 기간 조회 결과에서 최신 ``max_rows_per_ticker``개 거래일만 사용한다.

    반환 컬럼:
        stock_code, date, open, high, low, close, volume, trading_value
    """
    query_date = _normalize_query_date(base_date)
    start_date = _shift_query_date(query_date, days=-lookback_days)

    ticker_df = tickers if tickers is not None else fetch_ticker_list(query_date)
    codes = ticker_df["stock_code"].astype(str).str.zfill(6).tolist()

    if settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]
        log.info("price history count limited for testing", limit=settings.MAX_TICKERS)

    frames: list[pd.DataFrame] = []
    for code in codes:
        try:
            history = _rate_limiter.throttle(stock.get_market_ohlcv)(start_date, query_date, code)
        except Exception as exc:
            log.warning("krx price history collection failed", stock_code=code, error=str(exc))
            continue

        normalized = _normalize_history_frame(history, stock_code=code, max_rows=max_rows_per_ticker)
        if not normalized.empty:
            frames.append(normalized)

    if not frames:
        return _empty_history_frame()

    result = pd.concat(frames, ignore_index=True)
    log.info("price history collection complete", to_date=_format_output_date(query_date), total=len(result))
    return result


def _fetch_market_price_data(query_date: str, market: str) -> pd.DataFrame:
    ohlcv = _rate_limiter.throttle(stock.get_market_ohlcv_by_ticker)(query_date, market=market)
    caps = _rate_limiter.throttle(stock.get_market_cap_by_ticker)(query_date, market=market)
    fundamentals = _rate_limiter.throttle(stock.get_market_fundamental_by_ticker)(query_date, market=market)

    ohlcv = _with_stock_code_index(ohlcv)
    caps = _with_stock_code_index(caps)
    fundamentals = _with_stock_code_index(fundamentals)

    merged = (
        ohlcv[["stock_code", "종가", "거래대금"]]
        .merge(caps[["stock_code", "시가총액"]], on="stock_code", how="left")
        .merge(fundamentals[["stock_code", "PER", "PBR", "DIV"]], on="stock_code", how="left")
    )
    merged["market"] = market
    merged = merged.rename(
        columns={
            "종가": "close",
            "거래대금": "trading_value",
            "시가총액": "market_cap",
            "PER": "per",
            "PBR": "pbr",
            "DIV": "dividend_yield",
        }
    )

    for column in ["close", "trading_value", "market_cap", "per", "pbr", "dividend_yield"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")

    return merged


def _with_stock_code_index(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.index = result.index.astype(str).str.zfill(6)
    result.index.name = "stock_code"
    return result.reset_index()


def _normalize_query_date(base_date: str | date | None) -> str:
    if base_date is None:
        return date.today().strftime("%Y%m%d")
    if isinstance(base_date, date):
        return base_date.strftime("%Y%m%d")

    compact = base_date.replace("-", "")
    datetime.strptime(compact, "%Y%m%d")
    return compact


def _format_output_date(query_date: str) -> str:
    return datetime.strptime(query_date, "%Y%m%d").date().isoformat()


def _shift_query_date(query_date: str, days: int) -> str:
    shifted = datetime.strptime(query_date, "%Y%m%d").date() + timedelta(days=days)
    return shifted.strftime("%Y%m%d")


def _compute_avg_trading_value(ohlcv: pd.DataFrame, window: int) -> float | None:
    if "거래대금" not in ohlcv.columns or ohlcv.empty:
        return None

    values = pd.to_numeric(ohlcv["거래대금"], errors="coerce").dropna().tail(window)
    if values.empty:
        return None
    return float(values.mean())


def _normalize_history_frame(
    history: pd.DataFrame,
    stock_code: str,
    max_rows: int,
) -> pd.DataFrame:
    if history.empty:
        return _empty_history_frame()

    result = history.tail(max_rows).copy()
    result.index = pd.to_datetime(result.index)
    result.insert(0, "stock_code", stock_code)
    result.insert(1, "date", result.index.date.astype(str))
    result = result.rename(
        columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
            "거래대금": "trading_value",
        }
    )

    columns = ["stock_code", "date", "open", "high", "low", "close", "volume", "trading_value"]
    result = result.reindex(columns=columns)
    for column in ["open", "high", "low", "close", "volume", "trading_value"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.reset_index(drop=True)


def _empty_history_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["stock_code", "date", "open", "high", "low", "close", "volume", "trading_value"]
    )


def _empty_price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "stock_code",
            "date",
            "close",
            "trading_value",
            "market_cap",
            "per",
            "pbr",
            "dividend_yield",
            "market",
        ]
    )
