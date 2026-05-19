import pandas as pd


def percentile_rank_score(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """스크리닝 유니버스 내 백분위 순위 기반 0-100 점수를 반환한다."""
    values = pd.to_numeric(series, errors="coerce")
    valid_values = values.dropna()
    ranked = valid_values.rank(pct=True)
    if not higher_is_better:
        ranked = 1 - ranked
    scores = pd.Series(0.0, index=series.index)
    scores.loc[valid_values.index] = (ranked * 100).clip(0, 100)
    return scores
