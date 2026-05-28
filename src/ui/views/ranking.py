"""랭킹 페이지 — 메인 테이블, 사이드바 필터, 점수 지표."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.data_loader import (
    load_pipeline_stats,
    load_rankings,
    load_scores_with_filters,
)

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

_DISPLAY_COLS_SKIP_STAGE1 = [
    "rank",
    "stock_code",
    "stock_name",
    "market",
    "sector",
    "composite_score",
    "stage1_pass",
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

_DISPLAY_COLS_TEST_MODE = [
    "rank",
    "stock_code",
    "stock_name",
    "market",
    "sector",
    "composite_score",
    "stage1_pass",
    "is_value_trap",
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
    "stage1_pass": "S1통과",
    "is_value_trap": "가치함정",
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


def _render_pipeline_stats() -> None:
    """최신 파이프라인 실행 통계를 표시한다."""
    stats_list = load_pipeline_stats()

    if not stats_list:
        st.info("파이프라인 실행 기록이 없습니다.")
        return

    latest = stats_list[0]

    st.subheader(f"실행 날짜: {latest.get('run_date', '—')}")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("상태", latest.get("status", "—"))
        st.metric("소요 시간", f"{latest.get('duration_seconds', 0) // 60}분")
    with col2:
        st.metric("시작", latest.get("started_at", "—").split("T")[1][:5] if latest.get("started_at") else "—")
        st.metric("완료", latest.get("completed_at", "—").split("T")[1][:5] if latest.get("completed_at") else "—")

    st.divider()
    st.markdown("### 📊 수집 통계")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("수집 종목", f"{latest.get('stocks_collected', 0)}")
    with col2:
        st.metric("유효 데이터", f"{latest.get('stocks_with_data', 0)}")
    with col3:
        st.metric("수집 오류", f"{latest.get('collection_errors', 0)}")

    st.divider()
    st.markdown("### 🎯 스크리닝 결과")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stage1 통과", f"{latest.get('stage1_pass_count', 0)}")
    with col2:
        st.metric("Stage2 점수", f"{latest.get('stage2_score_count', 0)}")
    with col3:
        st.metric("가치함정 감지", f"{latest.get('stage3_trap_count', 0)}")
    with col4:
        st.metric("최종 후보", f"{latest.get('final_candidates', 0)}", delta="추천 종목")

    if latest.get("error_message"):
        st.error(f"오류: {latest['error_message']}")


def render() -> None:
    """랭킹 페이지를 렌더링한다."""
    col_title, col_stats = st.columns([5, 1])
    with col_title:
        st.title("📊 종목 랭킹")
    with col_stats, st.popover("📋 집계내용"):
        _render_pipeline_stats()

    # ── 사이드바 필터 ────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("필터")

        test_mode = st.checkbox(
            "🧪 필터 테스트 모드",
            value=False,
            help="Stage별 필터를 개별 조정할 수 있습니다.",
        )

        if test_mode:
            st.divider()
            st.subheader("Stage 필터")
            stage1_enabled = st.checkbox("Stage1 통과 필수", value=True, key="s1")
            stage3_exclude = st.checkbox("가치함정 제외", value=True, key="s3")
            min_score_test = st.slider(
                "최소 종합점수 (테스트)",
                min_value=0,
                max_value=100,
                value=0,
                step=1,
            )
        else:
            stage1_enabled = True
            stage3_exclude = True
            min_score_test = 0

        st.divider()
        st.subheader("기본 필터")

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
    if test_mode:
        df_raw = load_scores_with_filters(
            market=market,
            min_score=float(min_score_test),
            require_stage1=stage1_enabled,
            exclude_value_trap=stage3_exclude,
        )
    else:
        df_raw = load_rankings(market=market, min_score=float(min_score))

    # 섹터 필터 (데이터 로드 후 옵션 구성)
    with st.sidebar:
        sectors = ["전체"] + sorted(df_raw["sector"].dropna().unique().tolist())
        sector_opt = st.selectbox("섹터", options=sectors, index=0)
        sector = None if sector_opt == "전체" else sector_opt

    df = apply_filters(df_raw, market=None, sector=sector, min_score=0.0, max_risk_flags=max_risk_flags)

    # ── 테스트 모드 경고 ─────────────────────────────────────────────────────
    if test_mode:
        cols = []
        if not stage1_enabled:
            cols.append("Stage1 비활성")
        if not stage3_exclude:
            cols.append("가치함정 포함")
        msg = ", ".join(cols) if cols else "기본 설정"
        st.warning(f"🧪 **필터 테스트 모드** | {msg}")

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

    cols_to_use = _DISPLAY_COLS_TEST_MODE if test_mode else _DISPLAY_COLS

    display_cols = [c for c in cols_to_use if c in df.columns]
    df_display = df[display_cols].copy()

    # stage1_pass를 O/X로 표시
    if "stage1_pass" in df_display.columns:
        df_display["stage1_pass"] = df_display["stage1_pass"].apply(
            lambda v: "✅" if v else "❌"
        )

    # is_value_trap를 O/X로 표시
    if "is_value_trap" in df_display.columns:
        df_display["is_value_trap"] = df_display["is_value_trap"].apply(
            lambda v: "⚠️" if v else "—"
        )

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
