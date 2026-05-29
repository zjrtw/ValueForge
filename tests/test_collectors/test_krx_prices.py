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

    def fake_market_daily(endpoint, bas_dd):
        if endpoint == "stk_bydd_trd":
            return [
                {
                    "ISU_SRT_CD": "005930",
                    "TDD_OPNPRC": "69000",
                    "TDD_HGPRC": "71000",
                    "TDD_LWPRC": "68000",
                    "TDD_CLSPRC": "70000",
                    "ACC_TRDVOL": "1000000",
                    "ACC_TRDVAL": "100000000",
                    "MKTCAP": "400000000000000",
                },
                {
                    "ISU_SRT_CD": "000660",
                    "TDD_OPNPRC": "119000",
                    "TDD_HGPRC": "121000",
                    "TDD_LWPRC": "118000",
                    "TDD_CLSPRC": "120000",
                    "ACC_TRDVOL": "2000000",
                    "ACC_TRDVAL": "200000000",
                    "MKTCAP": "80000000000000",
                },
            ]
        else:  # ksq_bydd_trd
            return [
                {
                    "ISU_SRT_CD": "091990",
                    "TDD_OPNPRC": "79000",
                    "TDD_HGPRC": "81000",
                    "TDD_LWPRC": "78000",
                    "TDD_CLSPRC": "80000",
                    "ACC_TRDVOL": "500000",
                    "ACC_TRDVAL": "300000000",
                    "MKTCAP": "10000000000000",
                },
            ]

    mocker.patch("src.collectors.krx_prices.fetch_market_daily", side_effect=fake_market_daily)

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
    assert pd.isna(result.loc[result["stock_code"] == "091990", "dividend_yield"].item())


def test_fetch_avg_trading_value_20d_uses_latest_20_values(mocker):
    from datetime import date, timedelta

    tickers = pd.DataFrame(
        [
            {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI"},
        ]
    )

    def fake_market_daily(endpoint, bas_dd):
        if endpoint == "stk_bydd_trd":
            val_005930 = int(bas_dd[-2:]) + (int(bas_dd[-4:-2]) * 100)
            return [
                {
                    "ISU_SRT_CD": "005930",
                    "TDD_CLSPRC": "70000",
                    "ACC_TRDVAL": str(val_005930),
                },
                {
                    "ISU_SRT_CD": "000660",
                    "TDD_CLSPRC": "120000",
                    "ACC_TRDVAL": "100",
                },
            ]
        return []

    mocker.patch("src.collectors.krx_prices.fetch_market_daily", side_effect=fake_market_daily)
    mocker.patch("src.collectors.krx_prices.is_trading_day", return_value=True)

    result = fetch_avg_trading_value_20d("2026-05-20", tickers=tickers, lookback_days=20)

    assert result.loc[result["stock_code"] == "005930", "date"].item() == "2026-05-20"
    assert result.loc[result["stock_code"] == "000660", "avg_trading_value_20d"].item() == 100.0


def test_fetch_avg_trading_value_20d_keeps_row_with_none_when_history_is_empty(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    mocker.patch("src.collectors.krx_prices.fetch_market_daily", return_value=[])
    mocker.patch("src.collectors.krx_prices.is_trading_day", return_value=True)

    result = fetch_avg_trading_value_20d("20260520", tickers=tickers, lookback_days=20)

    assert len(result) == 1
    assert pd.isna(result["avg_trading_value_20d"].iloc[0])


def test_fetch_price_history_1y_collects_latest_252_ohlcv_rows(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )

    def fake_market_daily(endpoint, bas_dd):
        if endpoint == "stk_bydd_trd":
            day = int(bas_dd[-2:])
            return [
                {
                    "ISU_SRT_CD": "005930",
                    "TDD_OPNPRC": str(60000 + day),
                    "TDD_HGPRC": str(61000 + day),
                    "TDD_LWPRC": str(59000 + day),
                    "TDD_CLSPRC": str(60500 + day),
                    "ACC_TRDVOL": "1000000",
                    "ACC_TRDVAL": "100000000",
                },
            ]
        return []

    mocker.patch("src.collectors.krx_prices.fetch_market_daily", side_effect=fake_market_daily)
    mocker.patch("src.collectors.krx_prices.is_trading_day", return_value=True)

    result = fetch_price_history_1y("2026-05-20", tickers=tickers, lookback_days=260, max_rows_per_ticker=252)

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
    assert result["stock_code"].unique().tolist() == ["005930"]


def test_fetch_price_history_1y_returns_empty_frame_when_calls_fail(mocker):
    tickers = pd.DataFrame(
        [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
    )
    mocker.patch("src.collectors.krx_prices.fetch_market_daily", side_effect=RuntimeError("temporary failure"))
    mocker.patch("src.collectors.krx_prices.is_trading_day", return_value=True)

    result = fetch_price_history_1y("20260520", tickers=tickers, lookback_days=20)

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
        "src.collectors.krx_prices.fetch_market_daily",
        side_effect=RuntimeError("temporary failure"),
    )

    result = fetch_daily_price_data("20260520", tickers=tickers, markets=["KOSPI"])

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
        "market_cap",
        "per",
        "pbr",
        "dividend_yield",
        "market",
    ]
