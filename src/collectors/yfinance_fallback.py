from datetime import date
from typing import Any, cast

import pandas as pd
import yfinance as yf

from src.collectors.krx_prices import (
    _empty_history_frame,
    _format_output_date,
    _normalize_query_date,
)
from src.collectors.krx_tickers import fetch_ticker_list
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def fetch_yfinance_daily_price_data(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """pykrx 주가 데이터 누락 시 yfinance로 일별 가격을 보완한다.

    yfinance는 PER, PBR, 배당수익률을 안정적으로 제공하지 않을 수 있으므로
    해당 값은 ``None``으로 둔다.
    """
    query_date = _normalize_query_date(base_date)
    output_date = _format_output_date(query_date)
    ticker_df = _prepare_tickers(query_date, tickers)

    rows: list[dict] = []
    for item in ticker_df.itertuples(index=False):
        stock_code = str(item.stock_code)
        market = str(item.market)
        yf_symbol = _to_yfinance_symbol(stock_code, market)
        try:
            history = yf.download(yf_symbol, period="5d", interval="1d", progress=False)
        except Exception as exc:
            log.warning("yfinance daily price collection failed", stock_code=stock_code, error=str(exc))
            continue

        latest = _latest_history_row(history)
        if latest is None:
            continue

        close = _pick_value(latest, "Close")
        volume = _pick_value(latest, "Volume")
        rows.append(
            {
                "stock_code": stock_code,
                "date": output_date,
                "close": close,
                "trading_value": _multiply_or_none(close, volume),
                "market_cap": None,
                "per": None,
                "pbr": None,
                "dividend_yield": None,
                "market": market,
            }
        )

    if not rows:
        return _empty_yfinance_price_frame()

    result = pd.DataFrame(rows)
    result = result[["stock_code", "date", "close", "trading_value", "market_cap", "per", "pbr", "dividend_yield", "market"]]
    log.info("yfinance daily fallback collection complete", date=output_date, total=len(result))
    return result


def fetch_yfinance_price_history_1y(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    max_rows_per_ticker: int = 252,
) -> pd.DataFrame:
    """pykrx 이력 데이터 누락 시 yfinance로 1년 OHLCV를 보완한다."""
    query_date = _normalize_query_date(base_date)
    ticker_df = _prepare_tickers(query_date, tickers)

    frames: list[pd.DataFrame] = []
    for item in ticker_df.itertuples(index=False):
        stock_code = str(item.stock_code)
        market = str(item.market)
        yf_symbol = _to_yfinance_symbol(stock_code, market)
        try:
            history = yf.download(yf_symbol, period="1y", interval="1d", progress=False)
        except Exception as exc:
            log.warning("yfinance price history collection failed", stock_code=stock_code, error=str(exc))
            continue

        normalized = _normalize_yfinance_history(history, stock_code, max_rows_per_ticker)
        if not normalized.empty:
            frames.append(normalized)

    if not frames:
        return _empty_history_frame()

    result = pd.concat(frames, ignore_index=True)
    log.info("yfinance history fallback collection complete", total=len(result))
    return result


def _prepare_tickers(query_date: str, tickers: pd.DataFrame | None) -> pd.DataFrame:
    ticker_df = tickers if tickers is not None else fetch_ticker_list(query_date)
    ticker_df = ticker_df[["stock_code", "market"]].copy()
    ticker_df["stock_code"] = ticker_df["stock_code"].astype(str).str.zfill(6)
    ticker_df["market"] = ticker_df["market"].astype(str).str.upper()

    if tickers is None and settings.MAX_TICKERS > 0:
        ticker_df = ticker_df.head(settings.MAX_TICKERS)
        log.info("yfinance fallback count limited for testing", limit=settings.MAX_TICKERS)

    return ticker_df


def _to_yfinance_symbol(stock_code: str, market: str) -> str:
    suffix = ".KQ" if market == "KOSDAQ" else ".KS"
    return f"{stock_code}{suffix}"


def _latest_history_row(history: pd.DataFrame) -> pd.Series | None:
    if history.empty:
        return None
    latest = history.dropna(how="all")
    if latest.empty:
        return None
    return cast(pd.Series, latest.iloc[-1])


def _normalize_yfinance_history(
    history: pd.DataFrame,
    stock_code: str,
    max_rows: int,
) -> pd.DataFrame:
    if history.empty:
        return _empty_history_frame()

    result = history.dropna(how="all").tail(max_rows).copy()
    result.index = pd.to_datetime(result.index)
    result.insert(0, "stock_code", stock_code)
    result.insert(1, "date", result.index.date.astype(str))
    result["trading_value"] = [
        _multiply_or_none(close, volume)
        for close, volume in zip(result["Close"], result["Volume"], strict=False)
    ]
    result = result.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    columns = ["stock_code", "date", "open", "high", "low", "close", "volume", "trading_value"]
    result = result.reindex(columns=columns)
    for column in ["open", "high", "low", "close", "volume", "trading_value"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.reset_index(drop=True)


def _pick_value(row: pd.Series, key: str) -> float | None:
    value = row.get(key)
    if value is None or bool(pd.isna(value)):
        return None
    return float(cast(Any, value))


def _multiply_or_none(left: object, right: object) -> float | None:
    if left is None or right is None:
        return None
    try:
        left_float = float(cast(Any, left))
        right_float = float(cast(Any, right))
    except (TypeError, ValueError):
        return None
    if pd.isna(left_float) or pd.isna(right_float):
        return None
    return left_float * right_float


def _empty_yfinance_price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["stock_code", "date", "close", "trading_value", "market_cap", "per", "pbr", "dividend_yield", "market"]
    )
