import pandas as pd

from src.utils.config import screening_params


def stage1_filter(
    df: pd.DataFrame,
    params: dict | None = None,
) -> pd.DataFrame:
    """Stage 1 빠른 필터를 적용해 기본 가치 조건 통과 종목만 반환한다."""
    stage1 = params or screening_params.stage1

    market_cap = pd.to_numeric(df.get("market_cap"), errors="coerce")
    avg_trading_value = pd.to_numeric(df.get("avg_trading_value_20d"), errors="coerce")
    per = pd.to_numeric(df.get("per"), errors="coerce")
    pbr = pd.to_numeric(df.get("pbr"), errors="coerce")
    listing_days = pd.to_numeric(df.get("listing_days"), errors="coerce")
    is_active = pd.to_numeric(df.get("is_active"), errors="coerce")

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
