import pandas as pd

from src.collectors.market_ratios import calculate_market_ratios


def test_calculate_market_ratios_computes_per_pbr_div_yd():
    prices = pd.DataFrame(
        [
            {"stock_code": "005930", "date": "2026-05-20", "close": 70000},
            {"stock_code": "000660", "date": "2026-05-20", "close": 120000},
        ]
    )
    fundamentals = pd.DataFrame(
        [
            {"stock_code": "005930", "fiscal_year": 2025, "eps": 7000, "bps": 35000, "dps": 700},
            {"stock_code": "000660", "fiscal_year": 2025, "eps": 12000, "bps": 60000, "dps": 1200},
        ]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 2
    samsung_row = result[result["stock_code"] == "005930"].iloc[0]
    assert samsung_row["per"] == 10.0  # 70000 / 7000
    assert samsung_row["pbr"] == 2.0   # 70000 / 35000
    assert samsung_row["dividend_yield"] == 0.01  # 700 / 70000

    sk_row = result[result["stock_code"] == "000660"].iloc[0]
    assert sk_row["per"] == 10.0  # 120000 / 12000
    assert sk_row["pbr"] == 2.0   # 120000 / 60000
    assert sk_row["dividend_yield"] == 0.01  # 1200 / 120000


def test_calculate_market_ratios_handles_zero_eps():
    prices = pd.DataFrame([{"stock_code": "005930", "date": "2026-05-20", "close": 70000}])
    fundamentals = pd.DataFrame(
        [{"stock_code": "005930", "fiscal_year": 2025, "eps": 0, "bps": 35000, "dps": 700}]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 1
    assert result.iloc[0]["per"] is None
    assert result.iloc[0]["pbr"] == 2.0
    assert result.iloc[0]["dividend_yield"] == 0.01


def test_calculate_market_ratios_handles_none_values():
    prices = pd.DataFrame([{"stock_code": "005930", "date": "2026-05-20", "close": 70000}])
    fundamentals = pd.DataFrame(
        [{"stock_code": "005930", "fiscal_year": 2025, "eps": 7000, "bps": None, "dps": 700}]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 1
    assert result.iloc[0]["per"] == 10.0
    assert result.iloc[0]["pbr"] is None
    assert result.iloc[0]["dividend_yield"] == 0.01


def test_calculate_market_ratios_handles_missing_dps():
    prices = pd.DataFrame([{"stock_code": "005930", "date": "2026-05-20", "close": 70000}])
    fundamentals = pd.DataFrame(
        [{"stock_code": "005930", "fiscal_year": 2025, "eps": 7000, "bps": 35000, "dps": None}]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 1
    assert result.iloc[0]["per"] == 10.0
    assert result.iloc[0]["pbr"] == 2.0
    assert result.iloc[0]["dividend_yield"] is None


def test_calculate_market_ratios_handles_zero_close():
    prices = pd.DataFrame([{"stock_code": "005930", "date": "2026-05-20", "close": 0}])
    fundamentals = pd.DataFrame(
        [{"stock_code": "005930", "fiscal_year": 2025, "eps": 7000, "bps": 35000, "dps": 700}]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 1
    assert result.iloc[0]["per"] is None
    assert result.iloc[0]["pbr"] is None
    assert result.iloc[0]["dividend_yield"] is None


def test_calculate_market_ratios_uses_latest_fiscal_year():
    prices = pd.DataFrame([{"stock_code": "005930", "date": "2026-05-20", "close": 70000}])
    fundamentals = pd.DataFrame(
        [
            {"stock_code": "005930", "fiscal_year": 2023, "eps": 5000, "bps": 25000, "dps": 500},
            {"stock_code": "005930", "fiscal_year": 2025, "eps": 7000, "bps": 35000, "dps": 700},
        ]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 1
    assert result.iloc[0]["per"] == 10.0  # Uses 2025 data
    assert result.iloc[0]["pbr"] == 2.0
    assert result.iloc[0]["dividend_yield"] == 0.01


def test_calculate_market_ratios_handles_no_matching_fundamentals():
    prices = pd.DataFrame([{"stock_code": "005930", "date": "2026-05-20", "close": 70000}])
    fundamentals = pd.DataFrame(
        [{"stock_code": "000660", "fiscal_year": 2025, "eps": 12000, "bps": 60000, "dps": 1200}]
    )

    result = calculate_market_ratios(prices, fundamentals)

    assert len(result) == 1
    assert result.iloc[0]["stock_code"] == "005930"
    assert pd.isna(result.iloc[0]["per"])
    assert pd.isna(result.iloc[0]["pbr"])
    assert pd.isna(result.iloc[0]["dividend_yield"])


def test_calculate_market_ratios_returns_empty_for_empty_inputs():
    prices = pd.DataFrame(columns=["stock_code", "date", "close"])
    fundamentals = pd.DataFrame(columns=["stock_code", "fiscal_year", "eps", "bps", "dps"])

    result = calculate_market_ratios(prices, fundamentals)

    assert result.empty
    assert list(result.columns) == ["stock_code", "date", "per", "pbr", "dividend_yield"]


def test_calculate_market_ratios_returns_empty_for_none_inputs():
    result = calculate_market_ratios(
        pd.DataFrame(columns=["stock_code", "date", "close"]),
        pd.DataFrame(columns=["stock_code", "fiscal_year", "eps", "bps", "dps"]),
    )

    assert result.empty
