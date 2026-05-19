import pandas as pd

from src.collectors.yfinance_fallback import (
    fetch_yfinance_daily_price_data,
    fetch_yfinance_price_history_1y,
)


def test_fetch_yfinance_daily_price_data_uses_market_suffixes(mocker):
    tickers = pd.DataFrame(
        [
            {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
            {"stock_code": "091990", "stock_name": "셀트리온헬스케어", "market": "KOSDAQ"},
        ]
    )
    calls = []

    def fake_download(symbol, period, interval, progress):
        calls.append((symbol, period, interval, progress))
        return pd.DataFrame(
            {"Close": [70000.0], "Volume": [1000]},
            index=pd.to_datetime(["2026-05-20"]),
        )

    mocker.patch("src.collectors.yfinance_fallback.yf.download", side_effect=fake_download)

    result = fetch_yfinance_daily_price_data("2026-05-20", tickers=tickers)

    assert calls == [
        ("005930.KS", "5d", "1d", False),
        ("091990.KQ", "5d", "1d", False),
    ]
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
    assert len(result) == 2
    assert result.loc[result["stock_code"] == "005930", "trading_value"].item() == 70_000_000.0
    assert result.loc[result["stock_code"] == "091990", "market"].item() == "KOSDAQ"
    assert result["per"].isna().all()


def test_fetch_yfinance_price_history_1y_normalizes_latest_252_rows(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    index = pd.date_range("2025-01-01", periods=260, freq="D")
    history = pd.DataFrame(
        {
            "Open": range(260),
            "High": range(1, 261),
            "Low": range(2, 262),
            "Close": range(3, 263),
            "Volume": range(4, 264),
        },
        index=index,
    )
    api = mocker.patch("src.collectors.yfinance_fallback.yf.download", return_value=history)

    result = fetch_yfinance_price_history_1y("2026-05-20", tickers=tickers)

    api.assert_called_once_with("005930.KS", period="1y", interval="1d", progress=False)
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
    assert result.iloc[0]["date"] == "2025-01-09"
    assert result.iloc[-1]["close"] == 262
    assert result.iloc[-1]["trading_value"] == 262 * 263


def test_fetch_yfinance_daily_price_data_returns_empty_frame_when_calls_fail(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    mocker.patch(
        "src.collectors.yfinance_fallback.yf.download",
        side_effect=RuntimeError("temporary failure"),
    )

    result = fetch_yfinance_daily_price_data("20260520", tickers=tickers)

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
