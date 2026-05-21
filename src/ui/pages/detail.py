"""종목 상세 페이지 — 점수 레이더, 리스크 플래그, 재무 테이블, 주가 차트."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.components.radar_chart import render_radar
from src.ui.data_loader import load_rankings, load_stock_detail

_RADAR_DIMS = [
    ("value_score", "가치"),
    ("quality_score", "품질"),
    ("safety_score", "안전"),
    ("growth_score", "성장"),
    ("momentum_score", "모멘텀"),
]

_SEVERITY_BADGE = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}

_FLAG_TYPE_KR = {
    "HIGH_DEBT": "고부채",
    "LOW_INTEREST_COVERAGE": "이자보상부족",
    "LOW_OPERATING_MARGIN": "낮은영업이익률",
    "DECLINING_REVENUE": "매출감소",
    "HOLDING_COMPANY": "지주회사",
    "NEGATIVE_EQUITY": "자본잠식",
    "NEGATIVE_FCF": "음의FCF",
}

_FUNDAMENTAL_COLS = {
    "fiscal_year": "회계연도",
    "fiscal_quarter": "분기",
    "revenue": "매출액",
    "operating_profit": "영업이익",
    "net_profit": "순이익",
    "free_cash_flow": "FCF",
    "roe": "ROE(%)",
    "debt_to_equity": "부채비율",
    "operating_margin": "영업이익률",
    "current_ratio": "유동비율",
}


def build_radar_data(scores_row: pd.Series) -> dict[str, float]:
    """scores 행에서 레이더 차트용 {카테고리: 값} 딕셔너리를 반환한다."""
    return {
        label: float(scores_row.get(col, 0) or 0)
        for col, label in _RADAR_DIMS
    }



def format_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    """재무 DataFrame을 한국어 컬럼명으로 변환하고 숫자를 포맷한다."""
    if df.empty:
        return df

    cols = [c for c in _FUNDAMENTAL_COLS if c in df.columns]
    result = df[cols].copy()
    result = result.rename(columns=_FUNDAMENTAL_COLS)

    # 금액 컬럼 억 원 단위 표시
    money_labels = ["매출액", "영업이익", "순이익", "FCF"]
    for col in money_labels:
        if col in result.columns:
            result[col] = result[col].apply(
                lambda v: f"{v / 1e8:,.0f}" if pd.notna(v) else "—"
            )

    # 비율 컬럼 소수점 1자리
    ratio_labels = ["ROE(%)", "부채비율", "영업이익률", "유동비율"]
    for col in ratio_labels:
        if col in result.columns:
            result[col] = result[col].apply(
                lambda v: f"{v:.1f}" if pd.notna(v) else "—"
            )

    return result


def format_risk_flags(df: pd.DataFrame) -> pd.DataFrame:
    """리스크 플래그 DataFrame을 표시용으로 포맷한다."""
    if df.empty:
        return df

    result = df.copy()
    result["위험등급"] = result["severity"].apply(
        lambda s: f"{_SEVERITY_BADGE.get(s, '')} {s}"
    )
    result["유형"] = result["flag_type"].apply(
        lambda t: _FLAG_TYPE_KR.get(t, t)
    )
    result["설명"] = result["flag_description"].fillna("—")
    result["측정값"] = result["metric_value"].apply(
        lambda v: f"{v:.2f}" if pd.notna(v) else "—"
    )
    result["임계값"] = result["threshold_value"].apply(
        lambda v: f"{v:.2f}" if pd.notna(v) else "—"
    )

    return result[["위험등급", "유형", "설명", "측정값", "임계값"]]


def build_price_fig(prices_df: pd.DataFrame) -> go.Figure:
    """주가 데이터로 Plotly 라인 차트를 생성한다."""
    df = prices_df.sort_values("date")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["close"],
            mode="lines",
            name="종가",
            line=dict(color="royalblue", width=1.5),
        )
    )
    fig.update_layout(
        xaxis_title="날짜",
        yaxis_title="종가 (원)",
        margin=dict(l=40, r=20, t=20, b=40),
        height=280,
        hovermode="x unified",
    )
    return fig


def render(stock_code: str | None = None) -> None:
    """종목 상세 페이지를 렌더링한다."""
    # ── 종목 선택 ────────────────────────────────────────────────────────────
    if stock_code is None:
        stock_code = st.query_params.get("code")

    if not stock_code:
        st.info("종목코드를 URL 파라미터(?code=005930)로 전달하거나 아래에서 선택하세요.")
        df_rank = load_rankings()
        if not df_rank.empty:
            options = {
                f"{row['stock_name']} ({row['stock_code']})": row["stock_code"]
                for _, row in df_rank.iterrows()
            }
            selected = st.selectbox("종목 선택", list(options.keys()))
            stock_code = options[selected]
        else:
            st.warning("랭킹 데이터가 없습니다.")
            return

    detail = load_stock_detail(stock_code)
    scores_df = detail["scores"]
    flags_df = detail["flags"]
    fundamentals_df = detail["fundamentals"]
    prices_df = detail["prices"]

    # ── 헤더 ────────────────────────────────────────────────────────────────
    # rankings에서 기본 정보 조회
    df_rank = load_rankings()
    stock_row = df_rank[df_rank["stock_code"] == stock_code]
    stock_name = stock_row.iloc[0]["stock_name"] if not stock_row.empty else stock_code
    market = stock_row.iloc[0]["market"] if not stock_row.empty else ""
    sector = stock_row.iloc[0]["sector"] if not stock_row.empty else ""
    composite = (
        float(stock_row.iloc[0]["composite_score"]) if not stock_row.empty else None
    )

    col_title, col_back = st.columns([6, 1])
    with col_title:
        st.title(f"{stock_name} ({stock_code})")
        st.caption(f"{market} · {sector}")
    with col_back:
        st.write("")
        if st.button("← 목록으로"):
            st.query_params.clear()
            st.rerun()

    if composite is not None:
        st.metric("종합점수", f"{composite:.1f}")

    st.divider()

    # ── 점수 레이더 + 리스크 플래그 ─────────────────────────────────────────
    col_radar, col_flags = st.columns([1, 1])

    with col_radar:
        st.subheader("점수 레이더")
        if not scores_df.empty:
            radar_data = build_radar_data(scores_df.iloc[0])
            st.plotly_chart(render_radar(radar_data), use_container_width=True)
        else:
            st.info("점수 데이터 없음")

    with col_flags:
        st.subheader("리스크 플래그")
        if not flags_df.empty:
            fmt_flags = format_risk_flags(flags_df)
            st.dataframe(fmt_flags, use_container_width=True, hide_index=True)
        else:
            st.success("감지된 리스크 플래그 없음")

    st.divider()

    # ── 재무 테이블 ──────────────────────────────────────────────────────────
    st.subheader("재무 현황 (억 원)")
    if not fundamentals_df.empty:
        fmt_fund = format_fundamentals(fundamentals_df)
        st.dataframe(fmt_fund, use_container_width=True, hide_index=True)
    else:
        st.info("재무 데이터 없음")

    st.divider()

    # ── 주가 차트 ────────────────────────────────────────────────────────────
    st.subheader("주가 추이 (최근 1년)")
    if not prices_df.empty:
        st.plotly_chart(build_price_fig(prices_df), use_container_width=True)

        # PER / PBR 최신값
        latest = prices_df.sort_values("date").iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{latest['close']:,.0f}원")
        c2.metric("PER", f"{latest['per']:.1f}" if pd.notna(latest.get("per")) else "—")
        c3.metric("PBR", f"{latest['pbr']:.2f}" if pd.notna(latest.get("pbr")) else "—")
    else:
        st.info("주가 데이터 없음")
