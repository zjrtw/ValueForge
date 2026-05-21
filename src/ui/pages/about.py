"""About 페이지 — 방법론 설명, 데이터 소스 안내."""
from __future__ import annotations

import streamlit as st

# ── 방법론 상수 ───────────────────────────────────────────────────────────────

PIPELINE_STAGES = [
    {
        "id": "Stage 1",
        "name": "빠른 필터",
        "icon": "🔍",
        "desc": "주가 데이터만으로 명백히 비가치인 종목을 즉시 제거합니다.",
        "criteria": [
            ("시가총액", "≥ 500억 원", "소형주·저유동성 종목 제거"),
            ("20일 평균 거래대금", "≥ 50억 원", "최소 유동성 확보"),
            ("PER", "0 < PER ≤ 50", "적자 및 극단적 고평가 제외"),
            ("PBR", "0 < PBR ≤ 10", "심각한 부실·고평가 종목 제외"),
            ("상장 기간", "≥ 1년", "신규 상장 투기 종목 제외"),
        ],
        "output": "전체 ~2,600개 → 약 400~700개",
    },
    {
        "id": "Stage 2",
        "name": "심화 스코어링",
        "icon": "📊",
        "desc": "DART 재무 데이터를 활용해 5개 차원의 복합 점수(0–100)를 산출합니다. "
                "모든 점수는 스크리닝 유니버스 내 백분위 순위(상대 비교)로 정규화됩니다.",
        "scores": [
            ("가치 (Value)", "30%", "PER·PBR·EV/EBITDA·배당수익률"),
            ("품질 (Quality)", "25%", "ROE·ROA·영업이익률·ROE 안정성"),
            ("안전성 (Safety)", "20%", "부채비율·유동비율·이자보상배율"),
            ("성장성 (Growth)", "15%", "매출·영업이익·EPS·FCF YoY 성장"),
            ("모멘텀 (Momentum)", "10%", "6·3·1개월 수익률 vs KOSPI"),
        ],
        "output": "각 종목에 0–100 복합 점수 부여",
    },
    {
        "id": "Stage 3",
        "name": "가치 함정 감지",
        "icon": "⚠️",
        "desc": "PER·PBR이 낮아도 구조적 문제가 있는 '가치 함정' 종목을 식별합니다.",
        "flags": [
            ("🔴 CRITICAL", "자동 실격", ["자기자본 마이너스 (기술적 부도)", "2년 연속 영업손실"]),
            ("🟠 HIGH", "2개 이상 시 실격", ["ROE -5% 미만", "부채비율 300% 초과", "3년 연속 FCF 적자", "매출 YoY 20% 이상 감소"]),
            ("🟡 MEDIUM", "점수 패널티 -2점", ["3년 연속 영업이익률 하락", "매출 YoY 5% 이상 감소", "이자보상배율 1.5 미만"]),
            ("🔵 LOW", "정보성 표시", ["지주회사 (구조적 할인)", "CAPEX/매출 15% 초과"]),
        ],
        "output": "CRITICAL·HIGH×2 이상 종목 완전 제외",
    },
    {
        "id": "Stage 4",
        "name": "최종 랭킹",
        "icon": "🏆",
        "desc": "잔존 종목의 복합 점수에서 리스크 페널티를 차감한 조정 점수로 최종 순위를 생성합니다.",
        "penalty": [
            ("MEDIUM 플래그 1개당", "-2점"),
            ("HIGH 플래그 1개당", "-5점"),
        ],
        "output": "상위 100개 후보 최종 확정",
    },
]

DATA_SOURCES = [
    {
        "name": "pykrx",
        "icon": "📈",
        "desc": "KRX 공식 데이터 래퍼 라이브러리",
        "provides": ["KOSPI·KOSDAQ 전 종목 코드", "일별 종가·거래대금·시가총액", "PER·PBR·배당수익률"],
        "limit": "무료, 요청 간 지연 필요",
    },
    {
        "name": "DART OpenAPI",
        "icon": "📋",
        "desc": "금융감독원 전자공시시스템 공식 API",
        "provides": ["연간 재무제표 (최근 3개년)", "매출·영업이익·순이익·자산·부채", "FCF·EPS·BPS·ROE·ROA"],
        "limit": "무료, 일 10,000건 한도",
    },
    {
        "name": "Cloudflare R2",
        "icon": "☁️",
        "desc": "객체 스토리지 (SQLite 배포용)",
        "provides": ["latest.db — 항상 최신 스크리닝 결과", "latest_metadata.json — 실행 요약", "history/YYYY-MM-DD.db — 7일 롤링 백업"],
        "limit": "무료 10 GB / 월",
    },
]

DISCLAIMER = (
    "본 서비스는 교육·정보 제공 목적으로만 운영됩니다. "
    "제공되는 스크리닝 결과는 투자 권유 또는 매수·매도 추천이 아니며, "
    "투자 결정에 따른 손익은 전적으로 본인 책임입니다. "
    "과거 데이터 기반 분석이므로 미래 수익을 보장하지 않습니다."
)


# ── 렌더 함수 ─────────────────────────────────────────────────────────────────

def render() -> None:
    """About 페이지를 렌더링한다."""
    st.title("ValueForge 소개")
    st.caption("KOSPI·KOSDAQ 한국 주식 가치 스크리너")

    st.markdown(
        "ValueForge는 KOSPI·KOSDAQ 전 종목(약 2,600개)을 **4단계 가치투자 파이프라인**으로 "
        "매일 자동 분석하여 유망 후보군을 제공합니다. "
        "모든 점수는 스크리닝 유니버스 내 상대 백분위로 산출되어 시장 환경 변화에 강건합니다."
    )

    st.divider()

    # ── 파이프라인 개요 ──────────────────────────────────────────────────────
    st.subheader("스크리닝 파이프라인")

    flow_cols = st.columns(4)
    for i, stage in enumerate(PIPELINE_STAGES):
        with flow_cols[i]:
            st.markdown(
                f"**{stage['icon']} {stage['id']}**  \n{stage['name']}"
            )

    st.divider()

    # ── 각 단계 상세 ─────────────────────────────────────────────────────────
    for stage in PIPELINE_STAGES:
        with st.expander(f"{stage['icon']} {stage['id']} — {stage['name']}", expanded=False):
            st.write(stage["desc"])

            if "criteria" in stage:
                st.markdown("**필터 기준**")
                rows = [{"지표": c[0], "기준": c[1], "근거": c[2]} for c in stage["criteria"]]
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if "scores" in stage:
                st.markdown("**점수 차원 및 가중치**")
                import pandas as pd
                rows = [{"차원": s[0], "가중치": s[1], "주요 지표": s[2]} for s in stage["scores"]]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.info("💡 가중치는 `config/screening_params.yaml`에서 코드 수정 없이 변경할 수 있습니다.")

            if "flags" in stage:
                for badge, rule, examples in stage["flags"]:
                    st.markdown(f"**{badge}** — {rule}")
                    for ex in examples:
                        st.markdown(f"  - {ex}")

            if "penalty" in stage:
                st.markdown("**리스크 페널티**")
                for label, val in stage["penalty"]:
                    st.markdown(f"  - {label}: `{val}`")

            st.caption(f"📤 출력: {stage['output']}")

    st.divider()

    # ── 데이터 소스 ──────────────────────────────────────────────────────────
    st.subheader("데이터 소스")

    cols = st.columns(len(DATA_SOURCES))
    for i, src in enumerate(DATA_SOURCES):
        with cols[i]:
            st.markdown(f"#### {src['icon']} {src['name']}")
            st.caption(src["desc"])
            for item in src["provides"]:
                st.markdown(f"- {item}")
            st.info(src["limit"])

    st.divider()

    # ── 업데이트 주기 ────────────────────────────────────────────────────────
    st.subheader("업데이트 주기")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            "**파이프라인**: 매 거래일 장 마감(15:30 KST) 후 약 1시간 30분 대기 후 자동 실행  \n"
            "**대시보드 캐시**: 30분마다 R2에서 최신 데이터 자동 갱신"
        )
    with col_b:
        st.markdown(
            "**백업 보존**: 최근 7일치 SQLite 파일 유지  \n"
            "**인프라 비용**: GitHub Actions + Cloudflare R2 + Streamlit Cloud 무료 티어 활용"
        )

    st.divider()

    # ── 면책 조항 ────────────────────────────────────────────────────────────
    st.subheader("면책 조항")
    st.warning(DISCLAIMER)
