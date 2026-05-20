import pandas as pd

from src.scoring.normalizer import percentile_rank_score

VALUE_SCORE_WEIGHTS = {
    "per": 0.30,
    "pbr": 0.25,
    "ev_ebitda": 0.25,
    "dividend_yield": 0.20,
}


def compute_value_score(df: pd.DataFrame) -> pd.Series:
    """PER, PBR, EV/EBITDA, 배당수익률 기반 가치 점수를 계산한다."""
    per_score = percentile_rank_score(_positive_numeric(df, "per"), higher_is_better=False)
    pbr_score = percentile_rank_score(_positive_numeric(df, "pbr"), higher_is_better=False)
    ev_score = percentile_rank_score(_ev_ebitda(df), higher_is_better=False)
    dividend_score = percentile_rank_score(_numeric_column(df, "dividend_yield"), higher_is_better=True)

    return (
        per_score * VALUE_SCORE_WEIGHTS["per"]
        + pbr_score * VALUE_SCORE_WEIGHTS["pbr"]
        + ev_score * VALUE_SCORE_WEIGHTS["ev_ebitda"]
        + dividend_score * VALUE_SCORE_WEIGHTS["dividend_yield"]
    ).clip(0, 100)


def _ev_ebitda(df: pd.DataFrame) -> pd.Series:
    market_cap = _numeric_column(df, "market_cap")
    total_debt = _numeric_column(df, "total_debt").fillna(0)
    cash_and_equiv = _numeric_column(df, "cash_and_equiv").fillna(0)
    ebitda = _positive_numeric(df, "ebitda")

    ev = market_cap + total_debt - cash_and_equiv
    result = ev / ebitda
    return result.where((ev > 0) & (result > 0))


def _positive_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    values = _numeric_column(df, column)
    return values.where(values > 0)


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df.columns else pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(values, errors="coerce")
