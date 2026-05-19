# Streamlit Cloud 프론트엔드 설계

> **ValueForge** | 대시보드 레이아웃, 캐싱 전략, UI 컴포넌트

## 목차

1. [설계 원칙](#1-설계-원칙)
2. [앱 구조 및 네비게이션](#2-앱-구조-및-네비게이션)
3. [데이터 로딩 및 캐싱](#3-데이터-로딩-및-캐싱)
4. [랭킹 페이지](#4-랭킹-페이지)
5. [종목 상세 페이지](#5-종목-상세-페이지)
6. [성능 최적화](#6-성능-최적화)
7. [Streamlit Secrets 설정](#7-streamlit-secrets-설정)

---

## 1. 설계 원칙

- **읽기 전용**: Streamlit Cloud는 사전 연산된 데이터만 표시. 어떤 계산도 실행 불가.
- **30분 캐시**: 매 30분마다 R2에서 최신 DB 갱신. 사용자 요청마다 다운로드 불필요.
- **메타데이터 우선**: 전체 DB 다운로드 전에 `latest_metadata.json`(1KB)으로 신선도 먼저 확인.
- **조인 최소화**: `rankings` 테이블은 비정규화되어 있어 대부분의 쿼리가 단일 테이블 조회.

---

## 2. 앱 구조 및 네비게이션

```
src/ui/
├── app.py                   ← 페이지 설정, 공통 레이아웃
├── data_loader.py           ← R2 다운로드 + SQLite 쿼리 + 캐싱
├── pages/
│   ├── 1_Rankings.py        ← 메인 랭킹 대시보드
│   ├── 2_Stock_Detail.py    ← 종목별 상세 분석
│   └── 3_About.md           ← 방법론 설명
└── components/
    ├── score_radar.py       ← 재사용 레이더 차트
    ├── flag_display.py      ← 리스크 플래그 렌더링
    └── metric_card.py       ← 스타일 지표 카드
```

```python
# src/ui/app.py

import streamlit as st

st.set_page_config(
    page_title="ValueForge — 한국 가치주 스크리너",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
```

---

## 3. 데이터 로딩 및 캐싱

```python
# src/ui/data_loader.py

import sqlite3
import pandas as pd
import streamlit as st
from src.storage.downloader import download_latest_db, get_metadata


@st.cache_resource(ttl=1800)
def get_db_connection() -> sqlite3.Connection:
    """
    R2에서 latest.db를 30분마다 1회 다운로드.
    읽기 전용 SQLite 연결 반환.
    """
    db_path = download_latest_db()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=1800)
def load_rankings(
    market: str | None = None,
    min_score: float = 0.0
) -> pd.DataFrame:
    conn = get_db_connection()
    query = """
        SELECT r.*, s.listing_date
        FROM rankings r
        JOIN stocks s ON r.stock_code = s.stock_code
        WHERE r.run_date = (
            SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS'
        )
          AND r.composite_score >= ?
    """
    params: list = [min_score]
    if market:
        query += " AND r.market = ?"
        params.append(market)
    query += " ORDER BY r.rank ASC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=1800)
def load_stock_detail(stock_code: str) -> dict:
    conn = get_db_connection()
    return {
        'scores': pd.read_sql_query(
            "SELECT * FROM scores WHERE stock_code = ? ORDER BY run_date DESC LIMIT 1",
            conn, params=[stock_code]
        ),
        'flags': pd.read_sql_query(
            "SELECT * FROM risk_flags WHERE stock_code = ? ORDER BY run_date DESC",
            conn, params=[stock_code]
        ),
        'fundamentals': pd.read_sql_query(
            "SELECT * FROM fundamentals WHERE stock_code = ? "
            "ORDER BY fiscal_year DESC LIMIT 6",
            conn, params=[stock_code]
        ),
        'prices': pd.read_sql_query(
            "SELECT date, close, volume, per, pbr FROM prices "
            "WHERE stock_code = ? ORDER BY date DESC LIMIT 252",
            conn, params=[stock_code]
        ),
    }


@st.cache_data(ttl=300)  # 메타데이터는 5분마다 갱신 (경량)
def load_metadata() -> dict:
    return get_metadata()
```

---

## 4. 랭킹 페이지

```python
# src/ui/pages/1_Rankings.py

import streamlit as st
import pandas as pd
from src.ui.data_loader import load_rankings, load_metadata


def render():
    st.title("한국 가치주 랭킹")

    # 데이터 신선도 배너
    meta = load_metadata()
    run_date = meta.get('run_date', '알 수 없음')
    st.caption(f"기준일: {run_date} | 최종 업데이트: {meta.get('completed_at', '')[:10]}")

    # ── 사이드바 필터 ──────────────────────────────────────────
    with st.sidebar:
        st.header("필터")
        market      = st.selectbox("시장", ["전체", "KOSPI", "KOSDAQ"])
        min_score   = st.slider("최소 복합 점수", 0, 100, 40)
        per_max     = st.slider("최대 PER", 5, 30, 20)
        max_flags   = st.selectbox("최대 리스크 플래그 수", [0, 1, 2, 3], index=2)
        sectors     = st.multiselect("섹터 (선택하지 않으면 전체)")

    # ── 데이터 로딩 ─────────────────────────────────────────────
    market_filter = None if market == "전체" else market
    df = load_rankings(market=market_filter, min_score=min_score)
    df = df[df['per'] <= per_max]
    df = df[df['risk_flag_count'] <= max_flags]
    if sectors:
        df = df[df['sector'].isin(sectors)]

    # ── 핵심 지표 행 ────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("후보 종목 수",    len(df))
    c2.metric("평균 복합 점수", f"{df['composite_score'].mean():.1f}")
    c3.metric("평균 PER",       f"{df['per'].mean():.1f}배")
    c4.metric("평균 PBR",       f"{df['pbr'].mean():.2f}배")

    # ── 메인 테이블 ─────────────────────────────────────────────
    display_cols = {
        'rank': '순위', 'stock_name': '종목명', 'market': '시장',
        'sector': '섹터', 'composite_score': '복합점수',
        'value_score': '가치', 'quality_score': '품질',
        'safety_score': '안전성', 'growth_score': '성장성',
        'per': 'PER', 'pbr': 'PBR', 'roe': 'ROE(%)',
        'market_cap_b': '시총(십억)', 'risk_flag_count': '플래그',
    }
    st.dataframe(
        df[list(display_cols.keys())].rename(columns=display_cols),
        use_container_width=True,
        hide_index=True,
        column_config={
            '복합점수': st.column_config.ProgressColumn(min_value=0, max_value=100),
        }
    )

    # ── CSV 내보내기 ─────────────────────────────────────────────
    csv = df.to_csv(index=False).encode('utf-8-sig')  # Excel용 BOM
    st.download_button("CSV 내보내기", csv, "valueforge_rankings.csv", "text/csv")


render()
```

---

## 5. 종목 상세 페이지

```python
# src/ui/pages/2_Stock_Detail.py

import streamlit as st
import plotly.graph_objects as go
from src.ui.data_loader import load_stock_detail, load_rankings


def render():
    st.title("종목 상세 분석")

    # 종목 선택
    rankings_df = load_rankings()
    options = {
        f"{r['rank']}위. {r['stock_name']} ({r['stock_code']})": r['stock_code']
        for _, r in rankings_df.head(100).iterrows()
    }
    selected = st.selectbox("종목 선택", list(options.keys()))
    code = options[selected]

    data   = load_stock_detail(code)
    scores = data['scores'].iloc[0] if not data['scores'].empty else {}
    flags  = data['flags']
    fundam = data['fundamentals']
    prices = data['prices']

    # ── 점수 요약 ────────────────────────────────────────────────
    st.subheader("5차원 점수")
    dims = [
        ("가치",    "value_score"),
        ("품질",    "quality_score"),
        ("안전성",  "safety_score"),
        ("성장성",  "growth_score"),
        ("모멘텀",  "momentum_score"),
    ]
    cols = st.columns(5)
    for col, (label, key) in zip(cols, dims):
        val = float(scores.get(key, 0) or 0)
        col.metric(label, f"{val:.0f} / 100")

    # 레이더 차트
    fig = go.Figure(go.Scatterpolar(
        r=[float(scores.get(k, 0) or 0) for _, k in dims],
        theta=[label for label, _ in dims],
        fill='toself',
        name='점수 프로파일'
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 100])),
        height=350, margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── 리스크 플래그 ────────────────────────────────────────────
    if not flags.empty:
        st.subheader("리스크 플래그")
        icons = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🔵'}
        for _, flag in flags.iterrows():
            icon = icons.get(flag['severity'], '⚪')
            st.warning(
                f"{icon} **{flag['flag_type']}** ({flag['severity']}): "
                f"{flag['flag_description']}"
            )

    # ── 재무 이력 ────────────────────────────────────────────────
    if not fundam.empty:
        st.subheader("재무 이력")
        display = ['fiscal_year', 'revenue', 'operating_profit', 'net_profit',
                   'roe', 'debt_to_equity', 'free_cash_flow']
        st.dataframe(
            fundam[display].rename(columns={
                'fiscal_year': '회계연도', 'revenue': '매출(십억)',
                'operating_profit': '영업이익', 'net_profit': '순이익',
                'roe': 'ROE(%)', 'debt_to_equity': '부채비율',
                'free_cash_flow': 'FCF'
            }),
            use_container_width=True, hide_index=True
        )

    # ── 주가 차트 ────────────────────────────────────────────────
    if not prices.empty:
        st.subheader("주가 (1년)")
        fig2 = go.Figure(go.Scatter(
            x=prices['date'], y=prices['close'],
            mode='lines', name='종가'
        ))
        fig2.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig2, use_container_width=True)


render()
```

---

## 6. 성능 최적화

| 기법 | 구현 방법 |
|---|---|
| DB 다운로드 캐시 | `@st.cache_resource(ttl=1800)` — 30분마다 1회 다운로드 |
| 쿼리 결과 캐시 | `@st.cache_data(ttl=1800)` — 쿼리별 캐싱 |
| 메타데이터 선행 확인 | `latest_metadata.json`(1KB) 조회 후 DB 다운로드 필요성 판단 |
| 지연 로딩 | 종목 상세는 사용자가 선택했을 때만 쿼리 |
| `rankings` 테이블 비정규화 | 조인 없이 단일 테이블 조회 — 가장 중요한 최적화 |
| Plotly 사용 | WebGL 기반 클라이언트 렌더링; Matplotlib 대비 훨씬 빠름 |
| 단일 SQLite 연결 공유 | `st.cache_resource`로 연결 재사용 |

---

## 7. Streamlit Secrets 설정

**로컬 개발** (`.streamlit/secrets.toml`, gitignore 등록 필수):

```toml
[r2]
account_id = "your_account_id"
access_key_id = "ro_access_key_id"     # 읽기 전용 토큰
secret_access_key = "ro_secret_key"
bucket_name = "valueforge-bucket"
```

**Streamlit Cloud**: 앱 설정 → Secrets 탭에서 동일 형식으로 입력.

**설정 클래스 연동**:

```python
# src/utils/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    R2_ACCOUNT_ID:       str
    R2_ACCESS_KEY_ID:    str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME:      str = "valueforge-bucket"

    class Config:
        env_file = ".env"

settings = Settings()
```

→ R2 자격증명 분리 전략: [STORAGE.md](STORAGE.md#7-자격증명-분리-전략)
