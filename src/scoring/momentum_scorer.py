import pandas as pd

from src.scoring.normalizer import percentile_rank_score

MOMENTUM_SCORE_WEIGHTS = {
    "return_6m": 0.50,
    "return_3m": 0.30,
    "return_1m": 0.20,
}


def compute_momentum_score(
    df: pd.DataFrame,
    *,
    kospi_6m: float = 0.0,
    kospi_3m: float = 0.0,
) -> pd.Series:
    """6개월·3개월 시장 대비 수익률과 1개월 수익률 기반 모멘텀 점수를 계산한다."""
    enriched = _ensure_return_columns(df)
    relative_6m = _numeric_column(enriched, "return_6m") - kospi_6m
    relative_3m = _numeric_column(enriched, "return_3m") - kospi_3m

    score_6m = percentile_rank_score(relative_6m, higher_is_better=True)
    score_3m = percentile_rank_score(relative_3m, higher_is_better=True)
    score_1m = percentile_rank_score(_numeric_column(enriched, "return_1m"), higher_is_better=True)

    return (
        score_6m * MOMENTUM_SCORE_WEIGHTS["return_6m"]
        + score_3m * MOMENTUM_SCORE_WEIGHTS["return_3m"]
        + score_1m * MOMENTUM_SCORE_WEIGHTS["return_1m"]
    ).clip(0, 100)


def add_momentum_return_columns(df: pd.DataFrame) -> pd.DataFrame:
    """종목별 가격 이력에서 6개월·3개월·1개월 수익률을 붙인다."""
    required = {"stock_code", "date", "close"}
    if not required.issubset(df.columns):
        result = df.copy()
        for column in ("return_6m", "return_3m", "return_1m"):
            result[column] = pd.NA
        return result

    result = df.copy()
    result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.sort_values(["stock_code", "date"])

    groups = result.groupby("stock_code")["close"]
    result["return_6m"] = _period_return(result["close"], groups.shift(126))
    result["return_3m"] = _period_return(result["close"], groups.shift(63))
    result["return_1m"] = _period_return(result["close"], groups.shift(21))
    return result


def latest_momentum_returns(df: pd.DataFrame) -> pd.DataFrame:
    """종목별 최신 가격 행만 남겨 모멘텀 점수 입력 형태로 만든다."""
    enriched = add_momentum_return_columns(df)
    if not {"stock_code", "date"}.issubset(enriched.columns):
        return enriched

    return (
        enriched.sort_values(["stock_code", "date"])
        .groupby("stock_code", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def _ensure_return_columns(df: pd.DataFrame) -> pd.DataFrame:
    if {"return_6m", "return_3m", "return_1m"}.issubset(df.columns):
        return df
    return latest_momentum_returns(df)


def _period_return(current: pd.Series, previous: pd.Series) -> pd.Series:
    result = (current - previous) / previous
    return result.where(previous.notna() & (previous > 0))


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df.columns else pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(values, errors="coerce")
