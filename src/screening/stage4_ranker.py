import pandas as pd

from src.utils.config import screening_params


def stage4_rank(
    df: pd.DataFrame,
    *,
    params: dict | None = None,
) -> pd.DataFrame:
    """Stage 4 최종 랭킹.

    1. is_value_trap 종목 제거
    2. 리스크 플래그 패널티 적용: adjusted_score = composite_score
       - medium_flag_count × penalty_per_medium_flag
       - high_flag_count   × penalty_per_high_flag  (0 하한 클리핑)
    3. adjusted_score 내림차순 정렬 후 final_rank(1-based) 부여
    4. 상위 top_n 반환
    """
    p = params or screening_params.stage4
    penalty_medium = float(p.get("penalty_per_medium_flag", 2.0))
    penalty_high = float(p.get("penalty_per_high_flag", 5.0))
    top_n = int(p.get("top_n", 100))

    # 가치 함정 제거
    if "is_value_trap" in df.columns:
        result = df[~df["is_value_trap"].fillna(False).astype(bool)].copy()
    else:
        result = df.copy()

    composite = _col(result, "composite_score")
    medium_cnt = _col(result, "medium_flag_count").fillna(0)
    high_cnt = _col(result, "high_flag_count").fillna(0)

    result["adjusted_score"] = (
        composite - medium_cnt * penalty_medium - high_cnt * penalty_high
    ).clip(lower=0)

    result = result.sort_values("adjusted_score", ascending=False, ignore_index=True)
    result["final_rank"] = range(1, len(result) + 1)

    return result.head(top_n)


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(0.0, index=df.index, dtype="float64")
