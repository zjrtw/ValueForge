"""랭킹 페이지 — 메인 테이블, 사이드바 필터, 점수 지표."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.data_loader import load_rankings

_SCORE_COLS = [
    "value_score",
    "quality_score",
    "safety_score",
    "growth_score",
    "momentum_score",
]

_DISPLAY_COLS = [
    "rank",
    "stock_code",
    "stock_name",
    "market",
    "sector",
    "composite_score",
    "value_score",
    "quality_score",
    "safety_score",
    "growth_score",
    "momentum_score",
    "market_cap_b",
    "per",
    "pbr",
    "roe",
    "dividend_yield",
    "risk_flag_count",
    "highest_severity",
]

_COL_LABELS = {
    "rank": "순위",
    "stock_code": "종목코드",
    "stock_name": "종목명",
    "market": "시장",
    "sector": "섹터",
    "composite_score": "종합점수",
    "value_score": "가치",
    "quality_score": "품질",
    "safety_score": "안전",
    "growth_score": "성장",
    "momentum_score": "모멘텀",
    "market_cap_b": "시총(억)",
    "per": "PER",
    "pbr": "PBR",
    "roe": "ROE(%)",
    "dividend_yield": "배당(%)",
    "risk_flag_count": "위험수",
    "highest_severity": "최고위험",
}

_SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, None: 0}

# CSV 내보내기에 포함할 컬럼 (표시용과 동일, severity 배지 없이 원본 값 유지)
_CSV_COLS = [
    "rank",
    "stock_code",
    "stock_name",
    "market",
    "sector",
    "composite_score",
    "value_score",
    "quality_score",
    "safety_score",
    "growth_score",
    "momentum_score",
    "market_cap_b",
    "per",
    "pbr",
    "roe",
    "dividend_yield",
    "debt_to_equity",
    "risk_flag_count",
    "highest_severity",
]


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame을 UTF-8 BOM CSV 바이트로 변환한다.

    Excel에서 한글이 깨지지 않도록 UTF-8 BOM(\\xef\\xbb\\xbf)을 앞에 붙인다.
    컬럼명은 한국어로 변환하며, 원본 severity 값(배지 없이)을 그대로 유지한다.
    """
    cols = [c for c in _CSV_COLS if c in df.columns]
    out = df[cols].rename(columns=_COL_LABELS)
    csv_str = out.to_csv(index=False, encoding="utf-8")
    return b"\xef\xbb\xbf" + csv_str.encode("utf-8")


def apply_filters(
    df: pd.DataFrame,
    market: str | None,
    sector: str | None,
    min_score: float,
    max_risk_flags: int,
) -> pd.DataFrame:
    """DataFrame에 사이드바 필터를 적용한다."""
    if market:
        df = df[df["market"] == market]
    if sector:
        df = df[df["sector"] == sector]
    df = df[df["composite_score"] >= min_score]
    df = df[df["risk_flag_count"] <= max_risk_flags]
    return df


def build_score_metrics(df: pd.DataFrame) -> dict[str, float]:
    """랭킹 DataFrame의 점수 요약 지표를 반환한다."""
    if df.empty:
        return {col: 0.0 for col in ["count", "avg_composite"] + _SCORE_COLS}
    metrics: dict[str, float] = {
        "count": float(len(df)),
        "avg_composite": float(df["composite_score"].mean()),
    }
    for col in _SCORE_COLS:
        if col in df.columns:
            metrics[f"avg_{col}"] = float(df[col].mean())
    return metrics


def _severity_badge(severity: str | None) -> str:
    colors = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}
    return colors.get(severity or "", "⚪")


def render() -> None:
    """랭킹 페이지를 렌더링한다."""
    st.title("📊 종목 랭킹")

    # ── 사이드바 필터 ────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("필터")

        market_opt = st.selectbox(
            "시장",
            options=["전체", "KOSPI", "KOSDAQ"],
            index=0,
        )
        market = None if market_opt == "전체" else market_opt

        min_score = st.slider(
            "최소 종합점수",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
        )

        max_risk_flags = st.slider(
            "최대 위험 플래그 수",
            min_value=0,
            max_value=10,
            value=10,
            step=1,
        )

    # ── 데이터 로드 ──────────────────────────────────────────────────────────
    df_raw = load_rankings(market=market, min_score=float(min_score))

    # 섹터 필터 (데이터 로드 후 옵션 구성)
    with st.sidebar:
        sectors = ["전체"] + sorted(df_raw["sector"].dropna().unique().tolist())
        sector_opt = st.selectbox("섹터", options=sectors, index=0)
        sector = None if sector_opt == "전체" else sector_opt

    df = apply_filters(df_raw, market=None, sector=sector, min_score=0.0, max_risk_flags=max_risk_flags)

    # ── 점수 지표 요약 ───────────────────────────────────────────────────────
    metrics = build_score_metrics(df)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("종목 수", f"{int(metrics['count'])}")
    m2.metric("평균 종합", f"{metrics.get('avg_composite', 0):.1f}")
    m3.metric("평균 가치", f"{metrics.get('avg_value_score', 0):.1f}")
    m4.metric("평균 품질", f"{metrics.get('avg_quality_score', 0):.1f}")
    m5.metric("평균 안전", f"{metrics.get('avg_safety_score', 0):.1f}")
    m6.metric("평균 성장", f"{metrics.get('avg_growth_score', 0):.1f}")

    st.divider()

    # ── 메인 테이블 ──────────────────────────────────────────────────────────
    if df.empty:
        st.info("조건에 맞는 종목이 없습니다.")
        return

    display_cols = [c for c in _DISPLAY_COLS if c in df.columns]
    df_display = df[display_cols].copy()

    # severity 배지 추가
    if "highest_severity" in df_display.columns:
        df_display["highest_severity"] = df_display["highest_severity"].apply(
            lambda v: f"{_severity_badge(v)} {v}" if pd.notna(v) and v else "—"
        )

    df_display = df_display.rename(columns=_COL_LABELS)

    score_cols_kr = ["종합점수", "가치", "품질", "안전", "성장", "모멘텀"]
    present_score_cols = [c for c in score_cols_kr if c in df_display.columns]

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            col: st.column_config.ProgressColumn(
                col,
                min_value=0,
                max_value=100,
                format="%.1f",
            )
            for col in present_score_cols
        },
    )

    col_caption, col_download = st.columns([5, 1])
    with col_caption:
        st.caption(f"총 {len(df)}개 종목 표시 중")
    with col_download:
        run_date = df["run_date"].iloc[0] if "run_date" in df.columns else "latest"
        st.download_button(
            label="⬇ CSV",
            data=to_csv_bytes(df),
            file_name=f"valueforge_rankings_{run_date}.csv",
            mime="text/csv",
        )
