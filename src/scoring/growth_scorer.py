import pandas as pd

from src.scoring.normalizer import percentile_rank_score

GROWTH_SCORE_WEIGHTS = {
    "revenue_growth_yoy": 0.25,
    "op_profit_growth_yoy": 0.35,
    "eps_growth_yoy": 0.25,
    "fcf_growth_yoy": 0.15,
}

_GROWTH_SOURCE_COLUMNS = {
    "revenue_growth_yoy": "revenue",
    "op_profit_growth_yoy": "operating_profit",
    "eps_growth_yoy": "eps",
    "fcf_growth_yoy": "free_cash_flow",
}


def compute_growth_score(df: pd.DataFrame) -> pd.Series:
    """매출, 영업이익, EPS, FCF YoY 성장률 기반 성장성 점수를 계산한다."""
    enriched = _ensure_growth_columns(df)
    revenue_score = percentile_rank_score(
        _numeric_column(enriched, "revenue_growth_yoy"),
        higher_is_better=True,
    )
    operating_profit_score = percentile_rank_score(
        _numeric_column(enriched, "op_profit_growth_yoy"),
        higher_is_better=True,
    )
    eps_score = percentile_rank_score(
        _numeric_column(enriched, "eps_growth_yoy"),
        higher_is_better=True,
    )
    fcf_score = percentile_rank_score(
        _numeric_column(enriched, "fcf_growth_yoy"),
        higher_is_better=True,
    )

    return (
        revenue_score * GROWTH_SCORE_WEIGHTS["revenue_growth_yoy"]
        + operating_profit_score * GROWTH_SCORE_WEIGHTS["op_profit_growth_yoy"]
        + eps_score * GROWTH_SCORE_WEIGHTS["eps_growth_yoy"]
        + fcf_score * GROWTH_SCORE_WEIGHTS["fcf_growth_yoy"]
    ).clip(0, 100)


def add_yoy_growth_columns(df: pd.DataFrame) -> pd.DataFrame:
    """종목별 전년 대비 성장률 컬럼을 붙인다."""
    required = {"stock_code", "fiscal_year"}
    if not required.issubset(df.columns):
        result = df.copy()
        for output_column in _GROWTH_SOURCE_COLUMNS:
            result[output_column] = pd.NA
        return result

    result = df.copy()
    result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)
    result["fiscal_year"] = pd.to_numeric(result["fiscal_year"], errors="coerce")
    result = result.sort_values(["stock_code", "fiscal_year"])

    for output_column, source_column in _GROWTH_SOURCE_COLUMNS.items():
        current = _numeric_column(result, source_column)
        previous = current.groupby(result["stock_code"]).shift(1)
        result[output_column] = _yoy_growth(current, previous)

    return result


def _ensure_growth_columns(df: pd.DataFrame) -> pd.DataFrame:
    if set(_GROWTH_SOURCE_COLUMNS).issubset(df.columns):
        return df
    return add_yoy_growth_columns(df)


def _yoy_growth(current: pd.Series, previous: pd.Series) -> pd.Series:
    result = (current - previous) / previous.abs()
    return result.where(previous.notna() & (previous != 0))


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df.columns else pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(values, errors="coerce")
