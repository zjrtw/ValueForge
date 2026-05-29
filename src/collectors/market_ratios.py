"""시장 배수(PER, PBR, 배당수익률) 계산."""
from typing import Any

import pandas as pd

from src.utils.logger import get_logger

log = get_logger(__name__)


def calculate_market_ratios(
    prices_df: pd.DataFrame,
    fundamentals_df: pd.DataFrame,
) -> pd.DataFrame:
    """주가 데이터와 재무 데이터로부터 시장 배수를 계산한다.

    최신 재무 데이터(최대 fiscal_year)를 각 종목별로 선택하여 배수를 계산한다.

    Args:
        prices_df: stock_code, date, close 포함 (일별 가격)
        fundamentals_df: stock_code, fiscal_year, eps, bps, dps 포함

    Returns:
        stock_code, date, per, pbr, dividend_yield 컬럼 포함
    """
    if prices_df.empty or fundamentals_df.empty:
        return _empty_ratios_frame()

    latest_fundamentals = _get_latest_fundamentals(fundamentals_df)

    merged = prices_df.merge(
        latest_fundamentals,
        on="stock_code",
        how="left",
    )

    result_rows = []
    for _, row in merged.iterrows():
        close = _parse_numeric(row.get("close"))
        eps = _parse_numeric(row.get("eps"))
        bps = _parse_numeric(row.get("bps"))
        dps = _parse_numeric(row.get("dps"))

        result_rows.append({
            "stock_code": row["stock_code"],
            "date": row["date"],
            "per": _calculate_ratio(close, eps),
            "pbr": _calculate_ratio(close, bps),
            "dividend_yield": _calculate_ratio(dps, close),
        })

    result = pd.DataFrame(result_rows)
    log.info("market ratios calculation complete", total=len(result))
    return result


def _get_latest_fundamentals(fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """각 종목별로 가장 최신 재무 데이터를 선택."""
    if fundamentals_df.empty:
        return pd.DataFrame(columns=["stock_code", "eps", "bps", "dps"])

    latest = fundamentals_df.sort_values("fiscal_year").groupby("stock_code").tail(1)
    return latest[["stock_code", "eps", "bps", "dps"]].reset_index(drop=True)


def _calculate_ratio(numerator: float | None, denominator: float | None) -> float | None:
    """배수 계산. 분자나 분모가 None이거나 0이면 None 반환."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    try:
        ratio = float(numerator) / float(denominator)
        return ratio if ratio > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_numeric(value: Any) -> float | None:
    """값을 float로 파싱."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _empty_ratios_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["stock_code", "date", "per", "pbr", "dividend_yield"])
