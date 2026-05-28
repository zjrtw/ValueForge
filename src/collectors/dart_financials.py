from collections.abc import Iterable
from datetime import date
from typing import Any

import pandas as pd

from src.collectors.krx_tickers import fetch_ticker_list
from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.rate_limiter import DailyQuotaTracker

log = get_logger(__name__)

_REPORT_CODE = "11011"
_DEFAULT_YEARS = 3
_STATEMENT_DIVISIONS = {"IS", "BS", "CIS", "CF"}
_quota_tracker = DailyQuotaTracker(daily_limit=10000)

_ACCOUNT_MAP = {
    "revenue": ("매출액", "수익(매출액)", "영업수익"),
    "gross_profit": ("매출총이익",),
    "operating_profit": ("영업이익",),
    "net_profit": ("당기순이익", "당기순이익(손실)"),
    "total_assets": ("자산총계",),
    "current_assets": ("유동자산",),
    "cash_and_equiv": ("현금및현금성자산", "현금 및 현금성자산"),
    "total_liabilities": ("부채총계",),
    "current_liabilities": ("유동부채",),
    "total_equity": ("자본총계",),
    "operating_cf": ("영업활동현금흐름", "영업활동으로 인한 현금흐름"),
    "capex": ("유형자산의 취득", "유형자산 취득"),
    "eps": ("기본주당이익", "기본주당순이익"),
}


def fetch_financial_statements(
    tickers: pd.DataFrame | None = None,
    *,
    years: int = _DEFAULT_YEARS,
    base_year: int | None = None,
    client: Any | None = None,
) -> pd.DataFrame:
    """DART annual financial statements for KOSPI/KOSDAQ stocks.

    Returns rows shaped for Repository.upsert_fundamentals.
    """
    dart = client if client is not None else _create_dart_client()
    ticker_df = tickers if tickers is not None else fetch_ticker_list()
    codes = ticker_df["stock_code"].astype(str).str.zfill(6).tolist()

    if settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]
        log.info("dart financial count limited for testing", limit=settings.MAX_TICKERS)

    target_year = base_year if base_year is not None else date.today().year - 1
    fiscal_years = list(range(target_year - years + 1, target_year + 1))

    rows: list[dict[str, Any]] = []
    for code in codes:
        for fiscal_year in fiscal_years:
            if not _quota_tracker.can_call(1):
                log.info("dart daily quota exhausted, skipping remaining requests", stock_code=code)
                break

            try:
                raw = _fetch_raw_statement(dart, code, fiscal_year)
                _quota_tracker.add_calls(1)
            except Exception as exc:
                log.warning(
                    "dart financial collection failed",
                    stock_code=code,
                    fiscal_year=fiscal_year,
                    error=str(exc),
                )
                continue

            normalized = normalize_financial_statement(raw, code, fiscal_year)
            if normalized is not None:
                rows.append(normalized)

    result = pd.DataFrame(rows, columns=_fundamental_columns())
    log.info("dart financial collection complete", total=len(result))
    return result


def _fetch_raw_statement(dart: Any, stock_code: str, fiscal_year: int) -> pd.DataFrame | None:
    if hasattr(dart, "finstate_all"):
        return dart.finstate_all(stock_code, fiscal_year, reprt_code=_REPORT_CODE)
    return dart.finstate(stock_code, fiscal_year, reprt_code=_REPORT_CODE)


def normalize_financial_statement(
    raw: pd.DataFrame | None,
    stock_code: str,
    fiscal_year: int,
) -> dict[str, Any] | None:
    if raw is None or raw.empty:
        return None

    frame = raw.copy()
    if "sj_div" in frame.columns:
        frame = frame[frame["sj_div"].isin(_STATEMENT_DIVISIONS)]

    values = _extract_accounts(frame)
    if not values:
        return None

    row: dict[str, Any] = {
        "stock_code": str(stock_code).zfill(6),
        "fiscal_year": int(fiscal_year),
        "fiscal_quarter": 0,
        "data_source": "dart",
    }
    row.update(values)
    _add_derived_values(row)
    return row


def fetch_company_metadata(
    tickers: pd.DataFrame | None = None,
    *,
    client: Any | None = None,
) -> pd.DataFrame:
    """DART company API에서 종목별 메타데이터를 수집한다.

    반환 컬럼: stock_code, stock_name_en, industry

    - industry: DART induty_code (표준산업분류코드, 예: '264').
      KRX 섹터명과 다르며 추후 마이그레이션 시 별도 매핑 테이블로 변환 예정.
    - listing_date: DART company API에 포함되지 않아 수집 불가.
    """
    dart = client if client is not None else _create_dart_client()
    ticker_df = tickers if tickers is not None else fetch_ticker_list()
    codes = ticker_df["stock_code"].astype(str).str.zfill(6).tolist()

    if settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]

    rows: list[dict[str, Any]] = []
    for code in codes:
        if not _quota_tracker.can_call(1):
            log.info("dart daily quota exhausted, stopping company metadata fetch")
            break
        try:
            info = dart.company(code)
            _quota_tracker.add_calls(1)

            if not isinstance(info, dict):
                continue

            induty_code = info.get("induty_code")
            corp_name_eng = info.get("corp_name_eng")

            if induty_code or corp_name_eng:
                rows.append({
                    "stock_code": code,
                    "stock_name_en": corp_name_eng or None,
                    "industry": induty_code or None,
                })
        except Exception as exc:
            log.warning("dart company info fetch failed", stock_code=code, error=str(exc))

    log.info("dart company metadata collection complete", total=len(rows))
    return pd.DataFrame(rows, columns=["stock_code", "stock_name_en", "industry"])


def _create_dart_client() -> Any:
    if not settings.DART_API_KEY:
        raise RuntimeError("DART_API_KEY is not configured")

    try:
        from opendartreader import OpenDartReader
    except ModuleNotFoundError:
        import OpenDartReader

    return OpenDartReader(settings.DART_API_KEY)


def _extract_accounts(frame: pd.DataFrame) -> dict[str, float]:
    result: dict[str, float] = {}
    for target_column, account_names in _ACCOUNT_MAP.items():
        value = _find_first_amount(frame, account_names)
        if value is not None:
            if target_column == "capex" and value > 0:
                value = -value
            result[target_column] = value
    return result


def _find_first_amount(frame: pd.DataFrame, account_names: Iterable[str]) -> float | None:
    if "account_nm" not in frame.columns:
        return None

    amount_column = _amount_column(frame)
    if amount_column is None:
        return None

    for account_name in account_names:
        matched = frame[frame["account_nm"].astype(str).str.strip() == account_name]
        if matched.empty:
            continue

        for value in matched[amount_column]:
            amount = _parse_amount(value)
            if amount is not None:
                return amount
    return None


def _amount_column(frame: pd.DataFrame) -> str | None:
    for column in ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount"):
        if column in frame.columns:
            return column
    return None


def _parse_amount(value: Any) -> float | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text or text == "-":
        return None

    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "")
    try:
        amount = float(text)
    except ValueError:
        return None
    return -amount if negative else amount


def _add_derived_values(row: dict[str, Any]) -> None:
    operating_cf = row.get("operating_cf")
    capex = row.get("capex")
    if operating_cf is not None and capex is not None:
        row["free_cash_flow"] = operating_cf + capex

    revenue = row.get("revenue")
    if revenue:
        row["gross_margin"] = _ratio(row.get("gross_profit"), revenue)
        row["operating_margin"] = _ratio(row.get("operating_profit"), revenue)
        row["net_margin"] = _ratio(row.get("net_profit"), revenue)

    row["roe"] = _ratio(row.get("net_profit"), row.get("total_equity"))
    row["roa"] = _ratio(row.get("net_profit"), row.get("total_assets"))
    row["debt_to_equity"] = _ratio(row.get("total_liabilities"), row.get("total_equity"))
    row["current_ratio"] = _ratio(row.get("current_assets"), row.get("current_liabilities"))

def _ratio(numerator: Any, denominator: Any) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _fundamental_columns() -> list[str]:
    return [
        "stock_code",
        "fiscal_year",
        "fiscal_quarter",
        "revenue",
        "gross_profit",
        "operating_profit",
        "ebitda",
        "net_profit",
        "total_assets",
        "current_assets",
        "cash_and_equiv",
        "total_liabilities",
        "current_liabilities",
        "total_equity",
        "total_debt",
        "operating_cf",
        "capex",
        "free_cash_flow",
        "eps",
        "bps",
        "dps",
        "roe",
        "roa",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "debt_to_equity",
        "current_ratio",
        "interest_coverage",
        "data_source",
    ]
