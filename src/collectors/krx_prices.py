import sqlite3
from collections.abc import Iterable
from datetime import date, datetime, timedelta

import pandas as pd

from src.collectors.krx_client import fetch_market_daily
from src.collectors.krx_tickers import fetch_ticker_list
from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.market_calendar import is_trading_day, prev_trading_day
from src.utils.rate_limiter import RateLimiter

log = get_logger(__name__)

_MARKETS = ("KOSPI", "KOSDAQ")
_MARKET_ENDPOINTS: dict[str, str] = {
    "KOSPI": "stk_bydd_trd",
    "KOSDAQ": "ksq_bydd_trd",
}
_rate_limiter = RateLimiter(min_delay_seconds=0.5)


def fetch_daily_price_data(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    markets: Iterable[str] = _MARKETS,
) -> pd.DataFrame:
    """KRX 일별 주가·기본 지표를 시장 단위로 수집한다.

    반환 컬럼:
        stock_code, date, close, trading_value, market_cap,
        per, pbr, dividend_yield, market, sector
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

    if tickers is None and settings.MAX_TICKERS > 0:
        result = result.head(settings.MAX_TICKERS)
        log.info("daily price count limited for testing", limit=settings.MAX_TICKERS)

    log.info("daily price collection complete", date=output_date, total=len(result))
    return result[
        [
            "stock_code",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trading_value",
            "market_cap",
            "per",
            "pbr",
            "dividend_yield",
            "market",
            "sector",
        ]
    ].reset_index(drop=True)


def fetch_avg_trading_value_20d(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    lookback_days: int = 30,
    window: int = 20,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
    """종목별 최근 20거래일 평균 거래대금을 산출한다.

    Args:
        base_date: 기준일
        tickers: 대상 종목 DataFrame
        lookback_days: API 조회 시 과거 며칠을 볼지 (DB 미사용 시)
        window: 평균 낼 거래일 수
        conn: SQLite 연결 (제공 시 DB에서 계산하여 성능 최적화)

    Returns:
        stock_code, date, avg_trading_value_20d DataFrame
    """
    query_date_obj = _parse_date(base_date)
    output_date = query_date_obj.isoformat()
    query_date_str = query_date_obj.strftime("%Y%m%d")

    # ── [최적화] DB 연결이 있는 경우 DB에서 직접 계산 ──
    if conn is not None:
        log.info("calculating avg trading value using local DB")
        # trading_value 컬럼이 있으면 사용하고, 없으면 close * volume으로 대체
        query = f"""
            SELECT stock_code, AVG(val) as avg_trading_value_20d
            FROM (
                SELECT stock_code, 
                       COALESCE(trading_value, close * volume) as val,
                       ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY date DESC) as rn
                FROM prices
                WHERE date <= ?
            )
            WHERE rn <= ?
            GROUP BY stock_code
        """
        df = pd.read_sql_query(query, conn, params=(output_date, window))
        df["date"] = output_date
        
        # tickers가 제공된 경우 필터링 및 누락 종목 보충
        if tickers is not None:
            ticker_list = tickers["stock_code"].astype(str).str.zfill(6).tolist()
            df = df[df["stock_code"].isin(ticker_list)]
            existing_codes = set(df["stock_code"])
            missing_rows = []
            for code in ticker_list:
                if code not in existing_codes:
                    missing_rows.append({"stock_code": code, "date": output_date, "avg_trading_value_20d": None})
            if missing_rows:
                df = pd.concat([df, pd.DataFrame(missing_rows)], ignore_index=True)
        
        log.info("avg trading value calculation from DB complete", total=len(df))
        return df

    # ── [기존] DB가 없는 경우 KRX API 호출 (느림) ──
    ticker_df = tickers if tickers is not None else fetch_ticker_list(query_date_str)
    codes = ticker_df["stock_code"].astype(str).str.zfill(6).tolist()

    if tickers is None and settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]
        log.info("avg trading value count limited for testing", limit=settings.MAX_TICKERS)

    daily_records: dict[str, list[float]] = {code: [] for code in codes}

    trading_dates = _get_trading_dates(query_date_obj, lookback_days)
    for tdate in trading_dates:
        date_str = tdate.strftime("%Y%m%d")
        for market in _MARKETS:
            try:
                items = _rate_limiter.throttle(fetch_market_daily)(_MARKET_ENDPOINTS[market], date_str)
                for item in items:
                    code = _parse_code(item.get("ISU_SRT_CD"))
                    if code in daily_records:
                        trading_value = _parse_numeric(item.get("ACC_TRDVAL"))
                        if trading_value is not None:
                            daily_records[code].append(trading_value)
            except Exception as exc:
                log.debug("market daily fetch failed for avg computation", market=market, date=date_str, error=str(exc))
                continue

    rows = []
    for code in codes:
        values = daily_records[code]
        if len(values) >= window:
            avg_value = float(pd.Series(values).tail(window).mean())
        elif values:
            avg_value = float(pd.Series(values).mean())
        else:
            avg_value = None

        rows.append({
            "stock_code": code,
            "date": output_date,
            "avg_trading_value_20d": avg_value,
        })

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

    날짜별 전체 시장 조회 후 각 종목별로 최신 ``max_rows_per_ticker``개 거래일 데이터를 추출한다.

    반환 컬럼:
        stock_code, date, open, high, low, close, volume, trading_value
    """
    query_date_obj = _parse_date(base_date)
    query_date_str = query_date_obj.strftime("%Y%m%d")

    ticker_df = tickers if tickers is not None else fetch_ticker_list(query_date_str)
    codes = ticker_df["stock_code"].astype(str).str.zfill(6).tolist()

    if tickers is None and settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]
        log.info("price history count limited for testing", limit=settings.MAX_TICKERS)

    daily_history: dict[str, list[dict]] = {code: [] for code in codes}

    trading_dates = _get_trading_dates(query_date_obj, lookback_days)
    for tdate in trading_dates:
        date_str = tdate.strftime("%Y%m%d")
        for market in _MARKETS:
            try:
                items = _rate_limiter.throttle(fetch_market_daily)(_MARKET_ENDPOINTS[market], date_str)
                for item in items:
                    code = _parse_code(item.get("ISU_SRT_CD"))
                    if code in daily_history:
                        daily_history[code].append({
                            "date": date_str,
                            "open": _parse_numeric(item.get("TDD_OPNPRC")),
                            "high": _parse_numeric(item.get("TDD_HGPRC")),
                            "low": _parse_numeric(item.get("TDD_LWPRC")),
                            "close": _parse_numeric(item.get("TDD_CLSPRC")),
                            "volume": _parse_numeric(item.get("ACC_TRDVOL")),
                            "trading_value": _parse_numeric(item.get("ACC_TRDVAL")),
                        })
            except Exception as exc:
                log.debug("market daily fetch failed for history", market=market, date=date_str, error=str(exc))
                continue

    frames = []
    for code in codes:
        records = daily_history[code]
        if not records:
            continue

        df = pd.DataFrame(records[-max_rows_per_ticker:])
        df.insert(0, "stock_code", code)
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        frames.append(df)

    if not frames:
        return _empty_history_frame()

    result = pd.concat(frames, ignore_index=True)
    result = result[["stock_code", "date", "open", "high", "low", "close", "volume", "trading_value"]]
    log.info("price history collection complete", to_date=query_date_obj.isoformat(), total=len(result))
    return result


def _fetch_market_price_data(query_date: str, market: str) -> pd.DataFrame:
    from datetime import timedelta

    endpoint = _MARKET_ENDPOINTS.get(market.upper())
    if not endpoint:
        return _empty_price_frame()

    try:
        items = _rate_limiter.throttle(fetch_market_daily)(endpoint, query_date)
    except Exception as exc:
        log.warning("krx market daily fetch failed", market=market, endpoint=endpoint, error=str(exc))
        return _empty_price_frame()

    # 결과 없으면 이전 거래일로 자동 재시도 (KRX API T+1~T+2 지연 대응)
    if not items:
        try:
            query_date_obj = datetime.strptime(query_date, "%Y%m%d").date()
            prev_date_obj = prev_trading_day(query_date_obj - timedelta(days=1))
            prev_query_date = prev_date_obj.strftime("%Y%m%d")
            log.info("krx daily price empty, retrying with previous trading day", market=market, original=query_date, retry=prev_query_date)
            items = _rate_limiter.throttle(fetch_market_daily)(endpoint, prev_query_date)
        except Exception as exc:
            log.debug("krx market daily fetch retry failed", market=market, error=str(exc))
            items = []

    if not items:
        return _empty_price_frame()

    rows = []
    for item in items:
        # ISU_SRT_CD 우선, 없으면 ISU_CD 사용
        code = _parse_code(item.get("ISU_SRT_CD"))
        if not code:
            code = _parse_code(item.get("ISU_CD"))
        if not code:
            continue

        rows.append({
            "stock_code": code,
            "open": _parse_numeric(item.get("TDD_OPNPRC")),
            "high": _parse_numeric(item.get("TDD_HGPRC")),
            "low": _parse_numeric(item.get("TDD_LWPRC")),
            "close": _parse_numeric(item.get("TDD_CLSPRC")),
            "volume": _parse_numeric(item.get("ACC_TRDVOL")),
            "trading_value": _parse_numeric(item.get("ACC_TRDVAL")),
            "market_cap": _parse_numeric(item.get("MKTCAP")),
            "per": _parse_numeric(item.get("PER")),
            "pbr": _parse_numeric(item.get("PBR")),
            "dividend_yield": _parse_numeric(item.get("DIV_YD")),
            "market": market.upper(),
            "sector": item.get("SECT_TP_NM") or "Unknown",
        })

    if not rows:
        return _empty_price_frame()

    return pd.DataFrame(rows)


def _parse_code(raw: object) -> str:
    """ISU_SRT_CD 값을 6자리 문자열로 정규화. 유효하지 않으면 빈 문자열 반환."""
    if raw is None:
        return ""
    code = str(raw).strip().zfill(6)
    return "" if code == "000000" or not code.isdigit() else code


def _extract_code_from_isin(isin: object) -> str:
    """ISU_CD (ISIN 형식 KR7XXXXXX00)에서 6자리 종목코드를 추출."""
    if isin is None:
        return ""
    s = str(isin).strip()
    # KR7로 시작하는 12자리 ISIN: KR7 + 6자리 코드 + 00
    if len(s) >= 11 and s.startswith("KR7"):
        code = s[3:9]  # 위치 3-9: 6자리
        if code.isdigit():
            return code
    return ""


def _parse_numeric(raw: object) -> float | None:
    """쉼표 포함 숫자 문자열을 float로 변환."""
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


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


def _parse_date(base_date: str | date | None) -> date:
    """문자열 또는 date를 date 객체로 변환."""
    if base_date is None:
        return date.today()
    if isinstance(base_date, date):
        return base_date
    compact = str(base_date).replace("-", "").strip()
    return datetime.strptime(compact, "%Y%m%d").date()


def _get_trading_dates(end_date: date, lookback_days: int) -> list[date]:
    """종료일부터 역순으로 최대 N개의 거래일을 반환."""
    trading_dates: list[date] = []
    current = end_date
    attempted = 0
    max_attempts = lookback_days * 2

    while len(trading_dates) < lookback_days and attempted < max_attempts:
        try:
            if is_trading_day(current):
                trading_dates.append(current)
        except Exception:
            pass
        current = current - timedelta(days=1)
        attempted += 1

    return sorted(trading_dates)


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
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trading_value",
            "market_cap",
            "per",
            "pbr",
            "dividend_yield",
            "market",
            "sector",
        ]
    )
