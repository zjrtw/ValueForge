import pandas as pd

from src.scoring.normalizer import percentile_rank_score

SAFETY_SCORE_WEIGHTS = {
    "debt_to_equity": 0.35,
    "current_ratio": 0.35,
    "interest_coverage": 0.30,
}


def compute_safety_score(df: pd.DataFrame) -> pd.Series:
    """부채비율, 유동비율, 이자보상배율 기반 안전성 점수를 계산한다."""
    debt_score = percentile_rank_score(
        _numeric_column(df, "debt_to_equity"),
        higher_is_better=False,
    )
    current_score = percentile_rank_score(
        _numeric_column(df, "current_ratio"),
        higher_is_better=True,
    )
    interest_score = percentile_rank_score(
        _numeric_column(df, "interest_coverage"),
        higher_is_better=True,
    )

    return (
        debt_score * SAFETY_SCORE_WEIGHTS["debt_to_equity"]
        + current_score * SAFETY_SCORE_WEIGHTS["current_ratio"]
        + interest_score * SAFETY_SCORE_WEIGHTS["interest_coverage"]
    ).clip(0, 100)


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df.columns else pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(values, errors="coerce")
