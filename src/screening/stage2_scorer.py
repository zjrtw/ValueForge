import pandas as pd

from src.scoring.growth_scorer import compute_growth_score
from src.scoring.momentum_scorer import compute_momentum_score
from src.scoring.quality_scorer import compute_quality_score
from src.scoring.safety_scorer import compute_safety_score
from src.scoring.value_scorer import compute_value_score
from src.utils.config import screening_params

_SCORE_COLUMNS = ("value_score", "quality_score", "safety_score", "growth_score", "momentum_score")


def stage2_score(
    df: pd.DataFrame,
    *,
    weights: dict | None = None,
    kospi_6m: float = 0.0,
    kospi_3m: float = 0.0,
) -> pd.DataFrame:
    """5개 스코어러의 복합 점수를 산출해 입력 DataFrame에 컬럼으로 추가한다.

    추가 컬럼: value_score, quality_score, safety_score, growth_score,
               momentum_score, composite_score (모두 0–100 범위)
    """
    w = weights or screening_params.stage2_weights

    result = df.copy()
    result["value_score"] = compute_value_score(result)
    result["quality_score"] = compute_quality_score(result)
    result["safety_score"] = compute_safety_score(result)
    result["growth_score"] = compute_growth_score(result)
    result["momentum_score"] = compute_momentum_score(result, kospi_6m=kospi_6m, kospi_3m=kospi_3m)

    result["composite_score"] = (
        result["value_score"] * w.get("value", 0.0)
        + result["quality_score"] * w.get("quality", 0.0)
        + result["safety_score"] * w.get("safety", 0.0)
        + result["growth_score"] * w.get("growth", 0.0)
        + result["momentum_score"] * w.get("momentum", 0.0)
    ).clip(0, 100)

    return result
