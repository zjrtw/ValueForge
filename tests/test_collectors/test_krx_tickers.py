import pytest

from src.collectors.krx_tickers import fetch_ticker_list


@pytest.fixture(autouse=True)
def reset_ticker_settings(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 0)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSPI,KOSDAQ")


def test_fetch_ticker_list_returns_kospi_and_kosdaq_codes():
    result = fetch_ticker_list()

    assert not result.empty
    assert list(result.columns) == ["stock_code", "stock_name", "market"]

    kospi = result[result["market"] == "KOSPI"]
    kosdaq = result[result["market"] == "KOSDAQ"]

    assert len(kospi) == 20
    assert len(kosdaq) == 20
    assert len(result) == 40


def test_fetch_ticker_list_all_codes_are_six_digits():
    result = fetch_ticker_list()

    assert result["stock_code"].str.len().unique().tolist() == [6]
    assert result["stock_code"].str.match(r"^\d{6}$").all()


def test_fetch_ticker_list_markets_are_valid():
    result = fetch_ticker_list()

    valid_markets = {"KOSPI", "KOSDAQ"}
    assert set(result["market"]) == valid_markets


def test_fetch_ticker_list_stock_names_match_codes():
    result = fetch_ticker_list()

    for _, row in result.iterrows():
        assert row["stock_name"] == row["stock_code"]


def test_fetch_ticker_list_respects_max_tickers_setting(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 10)

    result = fetch_ticker_list()

    assert len(result) == 10
    assert result["market"].value_counts().get("KOSPI", 0) == 10


def test_fetch_ticker_list_with_max_tickers_zero_returns_all(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 0)

    result = fetch_ticker_list()

    assert len(result) == 40


def test_fetch_ticker_list_respects_kospi_market_setting(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSPI")

    result = fetch_ticker_list()

    assert len(result) == 20
    assert set(result["market"]) == {"KOSPI"}


def test_fetch_ticker_list_respects_kosdaq_market_setting(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSDAQ")

    result = fetch_ticker_list()

    assert len(result) == 20
    assert set(result["market"]) == {"KOSDAQ"}


def test_fetch_ticker_list_respects_all_market_setting(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "ALL")

    result = fetch_ticker_list()

    assert len(result) == 40
    assert set(result["market"]) == {"KOSPI", "KOSDAQ"}


def test_fetch_ticker_list_rejects_invalid_market_setting(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KONEX")

    try:
        fetch_ticker_list()
    except ValueError as exc:
        assert "Invalid MARKETS value" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
