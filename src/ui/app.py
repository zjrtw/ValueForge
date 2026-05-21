"""ValueForge Streamlit 앱 진입점."""
import streamlit as st

from src.ui.components import freshness_banner
from src.ui.pages import about, detail, ranking

st.set_page_config(
    page_title="ValueForge — 한국 주식 가치 스크리너",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 종목 상세 페이지는 query param으로 직접 진입
code = st.query_params.get("code")
if code:
    freshness_banner.render()
    detail.render(stock_code=code)
else:
    with st.sidebar:
        page = st.radio(
            "메뉴",
            options=["📊 랭킹", "ℹ️ About"],
            label_visibility="collapsed",
        )

    freshness_banner.render()

    if page == "📊 랭킹":
        ranking.render()
    else:
        about.render()
