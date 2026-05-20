import pandas as pd

from src.scoring.normalizer import percentile_rank_score

QUALITY_SCORE_WEIGHTS = {
    "roe": 0.30,
    "roa": 0.25,
    "operating_margin": 0.25,
    "roe_stability": 0.20,
}


def compute_quality_score(df: pd.DataFrame) -> pd.Series:
    """ROE, ROA, 영업이익률, ROE 안정성 기반 퀄리티 점수를 계산한다."""
    roe_score = percentile_rank_score(_numeric_column(df, "roe"), higher_is_better=True)
    roa_score = percentile_rank_score(_numeric_column(df, "roa"), higher_is_better=True)
    margin_score = percentile_rank_score(
        _numeric_column(df, "operating_margin"),
        higher_is_better=True,
    )
    stability_score = percentile_rank_score(_roe_stability(df), higher_is_better=False)

    return (
        roe_score * QUALITY_SCORE_WEIGHTS["roe"]
        + roa_score * QUALITY_SCORE_WEIGHTS["roa"]
        + margin_score * QUALITY_SCORE_WEIGHTS["operating_margin"]
        + stability_score * QUALITY_SCORE_WEIGHTS["roe_stability"]
    ).clip(0, 100)


def add_roe_stability(
    df: pd.DataFrame,
    *,
    years: int = 3,
    output_column: str = "roe_3yr_std",
) -> pd.DataFrame:
    """종목별 최근 N년 ROE 표준편차를 붙인다."""
    required = {"stock_code", "fiscal_year", "roe"}
    missing = required - set(df.columns)
    if missing:
        result = df.copy()
        result[output_column] = pd.NA
        return result

    result = df.copy()
    result["stock_code"] = result["stock_code"].astype(str).str.zfill(6)
    result["fiscal_year"] = pd.to_numeric(result["fiscal_year"], errors="coerce")
    result["roe"] = pd.to_numeric(result["roe"], errors="coerce")
    result = result.sort_values(["stock_code", "fiscal_year"])

    result[output_column] = (
        result.groupby("stock_code")["roe"]
        .transform(lambda values: values.rolling(window=years, min_periods=years).std())
        .astype("float64")
    )
    return result


def _roe_stability(df: pd.DataFrame) -> pd.Series:
    if "roe_3yr_std" in df.columns:
        return _numeric_column(df, "roe_3yr_std")

    if {"stock_code", "fiscal_year", "roe"}.issubset(df.columns):
        return add_roe_stability(df)["roe_3yr_std"]

    return pd.Series(index=df.index, dtype="float64")


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df.columns else pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(values, errors="coerce")
