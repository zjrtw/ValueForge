"""About 페이지 — 방법론 설명, 데이터 소스 안내."""
from __future__ import annotations

from typing import Any

import streamlit as st

# ── 방법론 상수 ───────────────────────────────────────────────────────────────

PIPELINE_STAGES: list[dict[str, Any]] = [
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

DATA_SOURCES: list[dict[str, Any]] = [
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

    # ── 지표별 해석 가이드 ───────────────────────────────────────────────────
    st.subheader("📖 지표별 해석 가이드")

    with st.expander("**가치 지표** — PER, PBR, EV/EBITDA, 배당수익률", expanded=True):
        guide_cols = st.columns(4)
        metrics = [
            {
                "name": "PER (주가수익비율)",
                "formula": "주가 / EPS",
                "guide": [
                    "🟢 < 10: 저평가",
                    "🟡 10-20: 중간 평가",
                    "🔴 > 20: 고평가",
                ]
            },
            {
                "name": "PBR (주가순자산비율)",
                "formula": "주가 / 순자산",
                "guide": [
                    "🟢 < 1.0: 저평가 (순자산 이하)",
                    "🟡 1.0-3.0: 중간 평가",
                    "🔴 > 3.0: 고평가",
                ]
            },
            {
                "name": "배당수익률",
                "formula": "배당금 / 주가 × 100",
                "guide": [
                    "🟢 > 3%: 배당 매력적",
                    "🟡 1-3%: 중간",
                    "🔴 < 1%: 배당 낮음",
                ]
            },
            {
                "name": "EV/EBITDA",
                "formula": "기업가치 / 영업이익",
                "guide": [
                    "🟢 < 8배: 저평가",
                    "🟡 8-12배: 중간",
                    "🔴 > 12배: 고평가",
                ]
            },
        ]
        for i, metric in enumerate(metrics):
            with guide_cols[i % 4]:
                st.markdown(f"**{metric['name']}**")
                st.caption(f"계산식: {metric['formula']}")
                for g in metric["guide"]:
                    st.markdown(g)

    with st.expander("**품질 지표** — ROE, ROA, 영업이익률"):
        guide_cols = st.columns(3)
        metrics = [
            {
                "name": "ROE (자기자본수익률)",
                "guide": [
                    "🟢 > 15%: 우수한 경영",
                    "🟡 10-15%: 양호",
                    "🔴 < 10%: 약세",
                    "🔴 < 0%: 손실 (제외)",
                ]
            },
            {
                "name": "ROA (자산수익률)",
                "guide": [
                    "🟢 > 8%: 우수",
                    "🟡 5-8%: 양호",
                    "🔴 < 5%: 약세",
                ]
            },
            {
                "name": "영업이익률",
                "guide": [
                    "🟢 > 10%: 우수한 체질",
                    "🟡 5-10%: 양호",
                    "🔴 < 5%: 박리다매",
                    "🔴 < 0%: 적자 (함정)",
                ]
            },
        ]
        for i, metric in enumerate(metrics):
            with guide_cols[i % 3]:
                st.markdown(f"**{metric['name']}**")
                for g in metric["guide"]:
                    st.markdown(g)

    with st.expander("**안전성 지표** — 부채, 유동성, 이자보상배율"):
        guide_cols = st.columns(3)
        metrics = [
            {
                "name": "부채비율 (Debt/Equity)",
                "guide": [
                    "🟢 < 100%: 안전",
                    "🟡 100-300%: 주의",
                    "🔴 > 300%: 과도한 부채",
                ]
            },
            {
                "name": "유동비율 (유동자산/유동부채)",
                "guide": [
                    "🟢 > 1.5배: 우수",
                    "🟡 1.0-1.5배: 양호",
                    "🔴 < 1.0배: 유동성 위험",
                ]
            },
            {
                "name": "이자보상배율",
                "guide": [
                    "🟢 > 5배: 이자 충당 용이",
                    "🟡 1.5-5배: 양호",
                    "🔴 < 1.5배: 이자 부담 높음",
                ]
            },
        ]
        for i, metric in enumerate(metrics):
            with guide_cols[i % 3]:
                st.markdown(f"**{metric['name']}**")
                for g in metric["guide"]:
                    st.markdown(g)

    with st.expander("**성장 & 모멘텀** — YoY 성장, 수익률"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**성장성 (Growth) — YoY 성장률**")
            st.markdown("""
            - **매출 성장**: > 15%/년 우수, < -5% 주의
            - **영업이익 성장**: > 20%/년 우수, < -10% 주의
            - **EPS 성장**: > 25%/년 우수, 음수 주의
            - **FCF 성장**: 양수 지속 우수, 3년 연속 적자 = 함정
            """)
        with col2:
            st.markdown("**모멘텀 (Momentum) — 시장 대비 수익률**")
            st.markdown("""
            - **6개월**: 연간화 수익률 vs KOSPI
            - **3개월**: 분기 수익률 vs KOSPI
            - **1개월**: 월간 수익률 vs KOSPI

            🟢 양수: 시장 대비 강세
            🔴 음수: 시장 대비 약세
            """)

    st.info(
        "💡 **점수 해석**: Stage 2의 각 차원 점수는 유니버스 내 **백분위 순위**입니다. "
        "따라서 절대값보다는 **상대 순위**가 중요하며, 높을수록 유리합니다."
    )

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

    # ── 데이터 상태 및 FAQ ───────────────────────────────────────────────────
    st.subheader("❓ 자주 묻는 질문")

    with st.expander("왜 섹터, 성장, 모멘텀, 배당 데이터가 보이지 않나요?"):
        st.markdown("""
        **데이터는 수집되고 있습니다!** 하지만 표시 위치가 다릅니다:

        | 지표 | 수집 상태 | 사용 위치 |
        |------|---------|---------|
        | **성장** | ✅ 수집 (DART) | Stage 2 점수에 포함 (15% 가중치) |
        | **모멘텀** | ✅ 수집 (KRX) | Stage 2 점수에 포함 (10% 가중치) |
        | **배당** | ✅ 수집 (KRX) | 가치 점수 + 상세페이지 배당수익률 |
        | **섹터** | ✅ 수집 (KRX) | 상세페이지 업종 표시 |

        **따라서:**
        - 📊 **랭킹 페이지**: 최종 점수만 표시 (5개 차원이 이미 포함됨)
        - 📄 **상세 페이지**: 각 종목의 세부 점수·배당·업종 확인 가능
        - 🔍 **About 페이지**: 위의 "지표별 해석 가이드" 참고
        """)

    with st.expander("점수 50점은 좋은 건가요? 70점은?"):
        st.markdown("""
        **점수는 상대 순위입니다** (절대 평가 아님):

        - 🟢 **상위 10%** (약 90-100점): 유니버스 내 최상위
        - 🟡 **상위 25%** (약 75-90점): 양호
        - 🔵 **상위 50%** (약 50-75점): 중간
        - 🔴 **하위 50%** (< 50점): 약세

        **ValueForge의 최종 100명은 이미 여러 필터를 통과한 후보들입니다.**
        따라서 최종 100명 내에서는 모두 일정 수준 이상의 가치투자 종목입니다.

        더 선별하려면:
        - 📈 **점수 높음** (80점 이상): 거의 완벽한 종목
        - 📊 **특정 차원 강세**: 예) 배당 관심 → 배당수익률 높은 종목
        - 🚩 **리스크 플래그 없음**: 함정을 피한 종목 (Stage 3 통과)
        """)

    with st.expander("왜 Stage 1에서 700명이 탈락하고 Stage 2에서 또 탈락하나요?"):
        st.markdown("""
        **이것이 정상입니다!** 가치 함정을 거르기 위한 단계적 필터입니다:

        ```
        전체 2,600개 → Stage 1 필터 (PER, PBR) → 약 700~800개
                   → Stage 2 점수 (5차원) → 약 700~800개 (재무 데이터 필요)
                   → Stage 3 함정 감지 → 약 100~200개 (함정 제외)
                   → Stage 4 랭킹 → 최종 100개
        ```

        각 단계가 엄격할수록 최종 후보의 품질이 높아집니다.
        """)

    with st.expander("성장·모멘텀 점수가 항상 0인가요?"):
        st.markdown("""
        **네, 현재는 0입니다.** 이는 **정상**입니다:

        | 지표 | 필요 데이터 | 현재 상태 | 언제 활성화? |
        |------|-----------|---------|-----------|
        | **성장** | 전년도 재무 데이터 | ❌ 없음 (처음 수집) | ~1년 후 |
        | **모멘텀** | 6개월 가격 이력 | ❌ 없음 (오늘 가격만) | ~6개월 후 |

        **왜 0이 되나요?**
        - 성장률 = 2025년 vs 2024년 비교 → 2024년 데이터 없음
        - 모멘텀 = 지난 6개월 수익률 → 가격 이력 부족

        **따라서:**
        - 📅 2026년 내내 매일 실행 누적
        - 📊 2026년 말: 모멘텀 활성화 (6개월 데이터 모임)
        - 📈 2027년 초: 성장률 활성화 (전년도 데이터 모임)

        **현재는 안심하세요.** 데이터가 쌓이면 자동으로 점수가 계산됩니다!
        """)

    with st.expander("배당, 성장, 모멘텀 점수를 개별 보기 가능한가요?"):
        st.markdown("""
        **현재**: 🔴 최종 복합 점수만 표시

        **향후 개선 예정** (M6-3 이후):
        - 상세 페이지에서 5개 차원 점수 개별 표시
        - 배당, 성장, 모멘텀 차트 추가
        - 사용자 정의 필터 (예: "배당 > 3% + 성장 > 15%" 필터)

        현재는 최종 점수로 간접적으로 판단하세요.
        높은 종목 = 5개 차원이 모두 우수하다는 뜻입니다.
        """)

    st.divider()

    # ── 면책 조항 ────────────────────────────────────────────────────────────
    st.subheader("면책 조항")
    st.warning(DISCLAIMER)
