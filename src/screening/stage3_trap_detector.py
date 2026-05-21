from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd

from src.utils.config import screening_params


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class FlagSpec:
    name: str
    description: str
    severity: Severity


FLAG_SPECS: tuple[FlagSpec, ...] = (
    # CRITICAL — 자동 실격
    FlagSpec("NEGATIVE_EQUITY", "자기자본이 마이너스 (기술적 부도 상태)", Severity.CRITICAL),
    FlagSpec("PERSISTENT_OPERATING_LOSS", "2년 연속 영업손실", Severity.CRITICAL),
    # HIGH — 강한 실격 신호
    FlagSpec("NEGATIVE_ROE", "ROE가 -5% 미만 (자본 훼손)", Severity.HIGH),
    FlagSpec("EXCESSIVE_DEBT", "부채비율 300% 초과 (지급불능 리스크)", Severity.HIGH),
    FlagSpec("PERSISTENT_NEGATIVE_FCF", "3년 연속 잉여현금흐름(FCF) 적자", Severity.HIGH),
    FlagSpec("REVENUE_COLLAPSE", "매출 YoY 30% 이상 감소", Severity.HIGH),
    # MEDIUM — 경고
    FlagSpec("DECLINING_MARGINS", "3년 연속 영업이익률 하락", Severity.MEDIUM),
    FlagSpec("DECLINING_REVENUE", "매출 YoY 5% 이상 감소", Severity.MEDIUM),
    FlagSpec("LOW_INTEREST_COVERAGE", "이자보상배율 1.5배 미만 (채무상환 리스크)", Severity.MEDIUM),
    # LOW — 정보성
    FlagSpec("HOLDING_COMPANY", "지주회사 (구조적 할인 가능성)", Severity.LOW),
    FlagSpec("HIGH_CAPEX", "CAPEX가 매출의 15% 초과 (자본집약적)", Severity.LOW),
)

_BY_NAME: dict[str, FlagSpec] = {s.name: s for s in FLAG_SPECS}


def is_value_trap(flags: list[dict[str, Any]]) -> bool:
    """CRITICAL 1개 이상 또는 HIGH 2개 이상이면 가치 함정(True)."""
    has_critical = any(f.get("severity") in (Severity.CRITICAL, "CRITICAL") for f in flags)
    high_count = sum(1 for f in flags if f.get("severity") in (Severity.HIGH, "HIGH"))
    return has_critical or high_count >= 2


def stage3_detect_traps(
    df: pd.DataFrame,
    *,
    params: dict | None = None,
) -> pd.DataFrame:
    """Stage 3 가치 함정 감지.

    입력 DataFrame에 다음 컬럼을 추가해 반환한다:
        risk_flags          — 콤마 구분 플래그 이름 문자열
        critical_flag_count — CRITICAL 플래그 수
        high_flag_count     — HIGH 플래그 수
        medium_flag_count   — MEDIUM 플래그 수
        low_flag_count      — LOW 플래그 수
        is_value_trap       — CRITICAL ≥1 또는 HIGH ≥2
    """
    p = params or screening_params.stage3
    result = df.copy()

    flag_mask: dict[str, pd.Series] = {
        spec.name: _check_flag(result, spec, p).fillna(False).astype(bool)
        for spec in FLAG_SPECS
    }

    for severity, col in (
        (Severity.CRITICAL, "critical_flag_count"),
        (Severity.HIGH, "high_flag_count"),
        (Severity.MEDIUM, "medium_flag_count"),
        (Severity.LOW, "low_flag_count"),
    ):
        names = [s.name for s in FLAG_SPECS if s.severity == severity]
        counts = pd.DataFrame({n: flag_mask[n].astype(int) for n in names}, index=result.index)
        result[col] = counts.sum(axis=1)

    flag_df = pd.DataFrame(flag_mask, index=result.index)
    result["risk_flags"] = flag_df.apply(
        lambda row: ",".join(name for name, active in row.items() if active),
        axis=1,
    )

    result["is_value_trap"] = (
        (result["critical_flag_count"] >= 1) | (result["high_flag_count"] >= 2)
    )

    return result


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype="float64")


def _check_flag(df: pd.DataFrame, spec: FlagSpec, params: dict) -> pd.Series:
    """플래그 조건을 평가해 boolean Series를 반환한다. 컬럼 부재 시 NaN → False."""
    max_debt = float(params.get("max_debt_ratio", 300.0)) / 100.0
    min_ic = float(params.get("min_interest_coverage", 1.5))
    max_rev_decline = float(params.get("max_revenue_decline_pct", -0.30))

    name = spec.name

    if name == "NEGATIVE_EQUITY":
        return _col(df, "total_equity") <= 0

    if name == "PERSISTENT_OPERATING_LOSS":
        return (_col(df, "op_profit_yr1") < 0) & (_col(df, "op_profit_yr2") < 0)

    if name == "NEGATIVE_ROE":
        return _col(df, "roe") < -5

    if name == "EXCESSIVE_DEBT":
        return _col(df, "debt_to_equity") > max_debt

    if name == "PERSISTENT_NEGATIVE_FCF":
        return (
            (_col(df, "fcf_yr1") < 0)
            & (_col(df, "fcf_yr2") < 0)
            & (_col(df, "fcf_yr3") < 0)
        )

    if name == "REVENUE_COLLAPSE":
        return _col(df, "revenue_growth_yoy") < max_rev_decline

    if name == "DECLINING_MARGINS":
        yr1 = _col(df, "op_margin_yr1")
        yr2 = _col(df, "op_margin_yr2")
        yr3 = _col(df, "op_margin_yr3")
        return (yr1 < yr2) & (yr2 < yr3)

    if name == "DECLINING_REVENUE":
        return _col(df, "revenue_growth_yoy") < -0.05

    if name == "LOW_INTEREST_COVERAGE":
        return _col(df, "interest_coverage") < min_ic

    if name == "HOLDING_COMPANY":
        if "industry" in df.columns:
            return df["industry"].astype(str) == "지주회사"
        return pd.Series(False, index=df.index)

    if name == "HIGH_CAPEX":
        revenue = _col(df, "revenue").abs()
        capex = _col(df, "capex").abs()
        ratio = capex / revenue.where(revenue > 0)
        return ratio > 0.15

    return pd.Series(False, index=df.index)
