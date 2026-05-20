import pandas as pd

from src.utils.config import screening_params


def stage1_filter(
    df: pd.DataFrame,
    params: dict | None = None,
) -> pd.DataFrame:
    """Stage 1 빠른 필터를 적용해 기본 가치 조건 통과 종목만 반환한다."""
    stage1 = params or screening_params.stage1

    market_cap = _numeric_column(df, "market_cap")
    avg_trading_value = _numeric_column(df, "avg_trading_value_20d")
    per = _numeric_column(df, "per")
    pbr = _numeric_column(df, "pbr")
    listing_days = _numeric_column(df, "listing_days")
    is_active = _numeric_column(df, "is_active")

    mask = (
        (market_cap >= _billion_to_krw(stage1.get("min_market_cap_billion", 0)))
        & (avg_trading_value >= _million_to_krw(stage1.get("min_avg_daily_volume_million", 0)))
        & (per > stage1.get("min_per", 0.0))
        & (per <= stage1.get("max_per", float("inf")))
        & (pbr <= stage1.get("max_pbr", float("inf")))
        & (listing_days >= stage1.get("min_listed_days", 0))
        & (is_active == 1)
        & per.notna()
        & pbr.notna()
    )
    return df[mask].copy()


def _billion_to_krw(value: int | float) -> float:
    return float(value) * 100_000_000


def _million_to_krw(value: int | float) -> float:
    return float(value) * 1_000_000


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df.columns else pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(values, errors="coerce")
