"""시장 배수(PER, PBR, 배당수익률) 계산."""
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

    # 배수 계산 (조건에 맞는 경우만)
    merged["per"] = None
    merged["pbr"] = None
    merged["dividend_yield"] = None

    # 유효성 검증 조건
    valid_per = (merged["eps"].notna()) & (merged["eps"] != 0) & (merged["close"] > 0)
    valid_pbr = (merged["bps"].notna()) & (merged["bps"] != 0) & (merged["close"] > 0)
    valid_div = (merged["dps"].notna()) & (merged["dps"] > 0) & (merged["close"] > 0)

    # 조건을 만족하는 행만 계산
    merged.loc[valid_per, "per"] = merged.loc[valid_per, "close"] / merged.loc[valid_per, "eps"]
    merged.loc[valid_pbr, "pbr"] = merged.loc[valid_pbr, "close"] / merged.loc[valid_pbr, "bps"]
    merged.loc[valid_div, "dividend_yield"] = merged.loc[valid_div, "dps"] / merged.loc[valid_div, "close"]

    # 계산 결과 음수 제거
    merged.loc[merged["per"] <= 0, "per"] = None
    merged.loc[merged["pbr"] <= 0, "pbr"] = None
    merged.loc[merged["dividend_yield"] <= 0, "dividend_yield"] = None

    result = merged[["stock_code", "date", "per", "pbr", "dividend_yield"]]
    log.info("market ratios calculation complete", total=len(result))
    return result


def _get_latest_fundamentals(fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """각 종목별로 가장 최신 재무 데이터를 선택."""
    if fundamentals_df.empty:
        return pd.DataFrame(columns=["stock_code", "eps", "bps", "dps"])

    latest = fundamentals_df.sort_values("fiscal_year").groupby("stock_code").tail(1)
    result = latest[["stock_code", "eps", "bps", "dps"]].reset_index(drop=True)

    # 디버그
    bps_valid = result["bps"].notna().sum()
    log.info("debug_latest_fundamentals", total=len(result), bps_valid=bps_valid)

    return result


def _empty_ratios_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["stock_code", "date", "per", "pbr", "dividend_yield"])
