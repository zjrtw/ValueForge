"""krx_tickers 수집기 단위 테스트.

pykrx API를 모킹하여 실제 네트워크 호출 없이 동작을 검증한다.
"""
import pytest

from src.collectors.krx_tickers import fetch_ticker_list

_FAKE_KOSPI = ["005930", "000660", "051910"]
_FAKE_KOSDAQ = ["091990", "263750", "035900"]

_FAKE_NAMES = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "051910": "LG화학",
    "091990": "셀트리온헬스케어",
    "263750": "펄어비스",
    "035900": "JYP Ent.",
}


@pytest.fixture(autouse=True)
def reset_ticker_settings(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 0)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSPI,KOSDAQ")


def _patch_pykrx(monkeypatch):
    """pykrx.stock API를 가짜 데이터로 패치한다."""
    def fake_ticker_list(date, market):
        return _FAKE_KOSPI if market == "KOSPI" else _FAKE_KOSDAQ

    def fake_ticker_name(code):
        return _FAKE_NAMES.get(code, code)

    monkeypatch.setattr("src.collectors.krx_tickers.stock.get_market_ticker_list", fake_ticker_list)
    monkeypatch.setattr("src.collectors.krx_tickers.stock.get_market_ticker_name", fake_ticker_name)
    monkeypatch.setattr("src.collectors.krx_tickers._rate_limiter.wait", lambda: None)


def test_fetch_ticker_list_returns_kospi_and_kosdaq_codes(monkeypatch):
    _patch_pykrx(monkeypatch)

    result = fetch_ticker_list()

    assert not result.empty
    assert list(result.columns) == ["stock_code", "stock_name", "market"]

    kospi = result[result["market"] == "KOSPI"]
    kosdaq = result[result["market"] == "KOSDAQ"]

    assert len(kospi) == len(_FAKE_KOSPI)
    assert len(kosdaq) == len(_FAKE_KOSDAQ)
    assert len(result) == len(_FAKE_KOSPI) + len(_FAKE_KOSDAQ)


def test_fetch_ticker_list_all_codes_are_six_digits(monkeypatch):
    _patch_pykrx(monkeypatch)

    result = fetch_ticker_list()

    assert result["stock_code"].str.len().unique().tolist() == [6]
    assert result["stock_code"].str.match(r"^\d{6}$").all()


def test_fetch_ticker_list_markets_are_valid(monkeypatch):
    _patch_pykrx(monkeypatch)

    result = fetch_ticker_list()

    assert set(result["market"]) == {"KOSPI", "KOSDAQ"}


def test_fetch_ticker_list_stock_names_are_populated(monkeypatch):
    _patch_pykrx(monkeypatch)

    result = fetch_ticker_list()

    samsung = result[result["stock_code"] == "005930"]
    assert not samsung.empty
    assert samsung.iloc[0]["stock_name"] == "삼성전자"


def test_fetch_ticker_list_respects_max_tickers_setting(monkeypatch):
    _patch_pykrx(monkeypatch)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 2)

    result = fetch_ticker_list()

    assert len(result) == 2


def test_fetch_ticker_list_with_max_tickers_zero_returns_all(monkeypatch):
    _patch_pykrx(monkeypatch)

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI) + len(_FAKE_KOSDAQ)


def test_fetch_ticker_list_respects_kospi_market_setting(monkeypatch):
    _patch_pykrx(monkeypatch)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSPI")

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI)
    assert set(result["market"]) == {"KOSPI"}


def test_fetch_ticker_list_respects_kosdaq_market_setting(monkeypatch):
    _patch_pykrx(monkeypatch)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSDAQ")

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSDAQ)
    assert set(result["market"]) == {"KOSDAQ"}


def test_fetch_ticker_list_respects_all_market_setting(monkeypatch):
    _patch_pykrx(monkeypatch)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "ALL")

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI) + len(_FAKE_KOSDAQ)
    assert set(result["market"]) == {"KOSPI", "KOSDAQ"}


def test_fetch_ticker_list_rejects_invalid_market_setting(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KONEX")

    with pytest.raises(ValueError, match="Invalid MARKETS value"):
        fetch_ticker_list()


def test_fetch_ticker_list_handles_ticker_list_error(monkeypatch):
    """시장별 API 호출 실패 시 해당 시장을 건너뛰고 계속 진행한다."""
    def fake_ticker_list(date, market):
        if market == "KOSPI":
            raise RuntimeError("API 오류")
        return _FAKE_KOSDAQ

    monkeypatch.setattr("src.collectors.krx_tickers.stock.get_market_ticker_list", fake_ticker_list)
    monkeypatch.setattr(
        "src.collectors.krx_tickers.stock.get_market_ticker_name",
        lambda code: _FAKE_NAMES.get(code, code),
    )
    monkeypatch.setattr("src.collectors.krx_tickers._rate_limiter.wait", lambda: None)

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSDAQ)
    assert set(result["market"]) == {"KOSDAQ"}


def test_fetch_ticker_list_handles_name_fetch_error(monkeypatch):
    """종목명 조회 실패 시 코드를 이름으로 대체한다."""
    monkeypatch.setattr(
        "src.collectors.krx_tickers.stock.get_market_ticker_list",
        lambda date, market: _FAKE_KOSPI if market == "KOSPI" else [],
    )
    monkeypatch.setattr(
        "src.collectors.krx_tickers.stock.get_market_ticker_name",
        lambda code: (_ for _ in ()).throw(RuntimeError("이름 조회 실패")),
    )
    monkeypatch.setattr("src.collectors.krx_tickers._rate_limiter.wait", lambda: None)

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI)
    for _, row in result.iterrows():
        assert row["stock_name"] == row["stock_code"]
