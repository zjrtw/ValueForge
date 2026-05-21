"""공유 합성 데이터 픽스처 — 스크리닝 파이프라인 통합 테스트용."""
import pytest
import pandas as pd

# 각 Stage에 전달할 명시적 파라미터 (config YAML에 의존하지 않음)
STAGE1_PARAMS = {
    "min_market_cap_billion": 30,
    "min_avg_daily_volume_million": 500,
    "min_per": 0.0,
    "max_per": 50.0,
    "max_pbr": 10.0,
    "min_listed_days": 365,
}

STAGE2_WEIGHTS = {
    "value": 0.30,
    "quality": 0.25,
    "safety": 0.20,
    "growth": 0.15,
    "momentum": 0.10,
}

STAGE3_PARAMS = {
    "max_debt_ratio": 300.0,
    "min_interest_coverage": 1.5,
    "max_revenue_decline_pct": -0.30,
}

STAGE4_PARAMS = {
    "penalty_per_medium_flag": 2.0,
    "penalty_per_high_flag": 5.0,
    "top_n": 100,
}

# 모든 Stage를 통과하는 기준 행
_VALID_BASE: dict = {
    # Stage 1 조건
    "market_cap": 5_000_000_000,        # 50억 KRW (≥ 30억 통과)
    "avg_trading_value_20d": 800_000_000,  # 8억 KRW (≥ 5억 통과)
    "per": 12.0,
    "pbr": 1.5,
    "listing_days": 1_000,
    "is_active": 1,
    # Stage 3 조건 (함정 없음)
    "total_equity": 500_000,
    "op_profit_yr1": 50_000,
    "op_profit_yr2": 45_000,
    "roe": 12.0,
    "roa": 6.0,
    "debt_to_equity": 1.0,
    "current_ratio": 1.8,
    "interest_coverage": 5.0,
    "fcf_yr1": 30_000,
    "fcf_yr2": 25_000,
    "fcf_yr3": 20_000,
    "op_margin_yr1": 0.12,   # yr1 > yr2 > yr3 → 하락 없음
    "op_margin_yr2": 0.10,
    "op_margin_yr3": 0.08,
    "revenue_growth_yoy": 0.08,
    "industry": "제조업",
    "capex": 50_000,
    "revenue": 500_000,
    # Stage 2 스코어링 입력
    "operating_margin": 0.10,
    "ebitda": 80_000,
    "total_debt": 200_000,
    "cash_and_equiv": 50_000,
    "operating_profit": 50_000,
    "eps": 1_000.0,
    "free_cash_flow": 30_000,
    "dividend_yield": 2.0,
    "return_6m": 0.08,
    "return_3m": 0.04,
    "return_1m": 0.02,
    "fiscal_year": 2024,
}

# 통합 테스트에서 참조할 종목 코드 그룹
CLEAN_CODES = [str(i + 1).zfill(6) for i in range(16)]  # 정상 종목 16개
TRAP_CODES = ["900001", "900002", "900003", "900004"]     # 가치 함정 4개
FAIL_CODES = (
    [f"8000{i+1:02d}" for i in range(4)]   # 시가총액 미달
    + [f"8010{i+1:02d}" for i in range(3)] # PER 초과
    + [f"8020{i+1:02d}" for i in range(3)] # 비활성 종목
)


@pytest.fixture(scope="session")
def synthetic_universe() -> pd.DataFrame:
    """30개 종목 합성 유니버스.

    구성:
    - 정상 종목 16개: Stage 1 통과, Stage 3 통과, 점수 분포 다양
    - 가치 함정 4개: Stage 1 통과, Stage 3 탈락
    - Stage 1 실패 10개: 시가총액 미달 4 / PER 초과 3 / 비활성 3
    """
    rows: list[dict] = []

    # 정상 종목 16개 — per·roe·revenue_growth 변화로 점수 분포 생성
    for i in range(16):
        rows.append({
            **_VALID_BASE,
            "stock_code": CLEAN_CODES[i],
            "per": 5.0 + i * 1.5,               # 5.0 ~ 27.5
            "roe": 20.0 - i * 0.5,               # 20.0 ~ 12.5
            "revenue_growth_yoy": 0.15 - i * 0.005,  # 0.15 ~ 0.075
        })

    # 가치 함정 ①: CRITICAL — 자기자본 음수
    rows.append({**_VALID_BASE, "stock_code": "900001", "total_equity": -100_000})

    # 가치 함정 ②: CRITICAL — 2년 연속 영업손실
    rows.append({
        **_VALID_BASE, "stock_code": "900002",
        "op_profit_yr1": -50_000, "op_profit_yr2": -30_000,
    })

    # 가치 함정 ③: HIGH 2개 — 음수 ROE + 부채비율 초과
    rows.append({**_VALID_BASE, "stock_code": "900003",
                 "roe": -8.0, "debt_to_equity": 3.5})

    # 가치 함정 ④: HIGH 2개 — 매출 급감 + 3년 연속 FCF 적자
    rows.append({
        **_VALID_BASE, "stock_code": "900004",
        "revenue_growth_yoy": -0.35,
        "fcf_yr1": -10_000, "fcf_yr2": -20_000, "fcf_yr3": -30_000,
    })

    # Stage 1 실패: 시가총액 미달 (10억 < 30억)
    for i in range(4):
        rows.append({**_VALID_BASE, "stock_code": f"8000{i+1:02d}",
                     "market_cap": 1_000_000_000})

    # Stage 1 실패: PER 초과 (60 > 50)
    for i in range(3):
        rows.append({**_VALID_BASE, "stock_code": f"8010{i+1:02d}", "per": 60.0})

    # Stage 1 실패: 비활성 종목
    for i in range(3):
        rows.append({**_VALID_BASE, "stock_code": f"8020{i+1:02d}", "is_active": 0})

    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def stage1_output(synthetic_universe: pd.DataFrame) -> pd.DataFrame:
    from src.screening.stage1_filter import stage1_filter
    return stage1_filter(synthetic_universe, params=STAGE1_PARAMS)


@pytest.fixture(scope="session")
def stage2_output(stage1_output: pd.DataFrame) -> pd.DataFrame:
    from src.screening.stage2_scorer import stage2_score
    return stage2_score(stage1_output, weights=STAGE2_WEIGHTS)


@pytest.fixture(scope="session")
def stage3_output(stage2_output: pd.DataFrame) -> pd.DataFrame:
    from src.screening.stage3_trap_detector import stage3_detect_traps
    return stage3_detect_traps(stage2_output, params=STAGE3_PARAMS)


@pytest.fixture(scope="session")
def stage4_output(stage3_output: pd.DataFrame) -> pd.DataFrame:
    from src.screening.stage4_ranker import stage4_rank
    return stage4_rank(stage3_output, params=STAGE4_PARAMS)
