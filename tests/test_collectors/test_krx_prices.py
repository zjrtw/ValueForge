import pandas as pd

from src.collectors.krx_prices import (
    fetch_avg_trading_value_20d,
    fetch_daily_price_data,
    fetch_price_history_1y,
)


def test_fetch_daily_price_data_merges_krx_market_frames(mocker):
    tickers = pd.DataFrame(
        [
            {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI"},
            {"stock_code": "091990", "stock_name": "셀트리온헬스케어", "market": "KOSDAQ"},
        ]
    )

    def fake_ohlcv(_date, market):
        if market == "KOSPI":
            return pd.DataFrame(
                {
                    "시가": [69000, 119000],
                    "고가": [71000, 121000],
                    "저가": [68000, 118000],
                    "종가": [70000, 120000],
                    "거래량": [1_000_000, 2_000_000],
                    "거래대금": [100_000_000, 200_000_000],
                },
                index=["005930", "000660"],
            )
        return pd.DataFrame(
            {
                "시가": [79000],
                "고가": [81000],
                "저가": [78000],
                "종가": [80000],
                "거래량": [500_000],
                "거래대금": [300_000_000],
            },
            index=["091990"],
        )

    def fake_caps(_date, market):
        if market == "KOSPI":
            return pd.DataFrame({"시가총액": [400_000_000_000_000, 80_000_000_000_000]}, index=["005930", "000660"])
        return pd.DataFrame({"시가총액": [10_000_000_000_000]}, index=["091990"])

    def fake_fundamentals(_date, market):
        if market == "KOSPI":
            return pd.DataFrame({"PER": [10.5, 15.2], "PBR": [1.2, 1.8], "DIV": [2.1, 1.0]}, index=["005930", "000660"])
        return pd.DataFrame({"PER": [30.1], "PBR": [4.3], "DIV": [0.0]}, index=["091990"])

    mocker.patch("src.collectors.krx_prices.stock.get_market_ohlcv_by_ticker", side_effect=fake_ohlcv)
    mocker.patch("src.collectors.krx_prices.stock.get_market_cap_by_ticker", side_effect=fake_caps)
    mocker.patch(
        "src.collectors.krx_prices.stock.get_market_fundamental_by_ticker",
        side_effect=fake_fundamentals,
    )

    result = fetch_daily_price_data("2026-05-20", tickers=tickers)

    assert list(result.columns) == [
        "stock_code",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trading_value",
        "market_cap",
        "per",
        "pbr",
        "dividend_yield",
        "market",
    ]
    assert len(result) == 3
    assert result.loc[result["stock_code"] == "005930", "date"].item() == "2026-05-20"
    assert result.loc[result["stock_code"] == "005930", "close"].item() == 70000
    assert result.loc[result["stock_code"] == "005930", "volume"].item() == 1_000_000
    assert result.loc[result["stock_code"] == "000660", "market_cap"].item() == 80_000_000_000_000
    assert result.loc[result["stock_code"] == "091990", "dividend_yield"].item() == 0.0


def test_fetch_avg_trading_value_20d_uses_latest_20_values(mocker):
    tickers = pd.DataFrame(
        [
            {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI"},
        ]
    )
    calls = []

    def fake_history(fromdate, todate, ticker):
        calls.append((fromdate, todate, ticker))
        if ticker == "005930":
            return pd.DataFrame({"거래대금": list(range(1, 31))})
        return pd.DataFrame({"거래대금": [100] * 30})

    mocker.patch("src.collectors.krx_prices.stock.get_market_ohlcv", side_effect=fake_history)

    result = fetch_avg_trading_value_20d("2026-05-20", tickers=tickers)

    assert len(calls) == 2
    assert ("20260420", "20260520", "005930") in calls
    assert ("20260420", "20260520", "000660") in calls
    assert result.loc[result["stock_code"] == "005930", "date"].item() == "2026-05-20"
    assert result.loc[result["stock_code"] == "005930", "avg_trading_value_20d"].item() == 20.5
    assert result.loc[result["stock_code"] == "000660", "avg_trading_value_20d"].item() == 100.0


def test_fetch_avg_trading_value_20d_keeps_row_with_none_when_history_is_empty(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    mocker.patch(
        "src.collectors.krx_prices.stock.get_market_ohlcv",
        return_value=pd.DataFrame(columns=["거래대금"]),
    )

    result = fetch_avg_trading_value_20d("20260520", tickers=tickers)

    assert len(result) == 1
    assert result["avg_trading_value_20d"].isna().all()


def test_fetch_price_history_1y_collects_latest_252_ohlcv_rows(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    index = pd.date_range("2025-01-01", periods=260, freq="D")
    history = pd.DataFrame(
        {
            "시가": range(260),
            "고가": range(1, 261),
            "저가": range(2, 262),
            "종가": range(3, 263),
            "거래량": range(4, 264),
            "거래대금": range(5, 265),
        },
        index=index,
    )
    api = mocker.patch("src.collectors.krx_prices.stock.get_market_ohlcv", return_value=history)

    result = fetch_price_history_1y("2026-05-20", tickers=tickers)

    api.assert_called_once_with("20250515", "20260520", "005930")
    assert list(result.columns) == [
        "stock_code",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trading_value",
    ]
    assert len(result) == 252
    assert result["stock_code"].unique().tolist() == ["005930"]
    assert result.iloc[0]["date"] == "2025-01-09"
    assert result.iloc[-1]["close"] == 262


def test_fetch_price_history_1y_returns_empty_frame_when_calls_fail(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    mocker.patch(
        "src.collectors.krx_prices.stock.get_market_ohlcv",
        side_effect=RuntimeError("temporary failure"),
    )

    result = fetch_price_history_1y("20260520", tickers=tickers)

    assert result.empty
    assert list(result.columns) == [
        "stock_code",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "trading_value",
    ]


def test_fetch_daily_price_data_returns_empty_frame_when_market_call_fails(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    mocker.patch(
        "src.collectors.krx_prices.stock.get_market_ohlcv_by_ticker",
        side_effect=RuntimeError("temporary failure"),
    )

    result = fetch_daily_price_data("20260520", tickers=tickers, markets=["KOSPI"])

    assert result.empty
    assert list(result.columns) == [
        "stock_code",
        "date",
        "close",
        "trading_value",
        "market_cap",
        "per",
        "pbr",
        "dividend_yield",
        "market",
    ]
