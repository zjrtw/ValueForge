import pandas as pd
import pytest

from src.collectors import dart_financials
from src.collectors.dart_financials import (
    fetch_financial_statements,
    normalize_financial_statement,
)


@pytest.fixture(autouse=True)
def reset_quota_tracker():
    dart_financials._quota_tracker.reset()
    yield
    dart_financials._quota_tracker.reset()


def test_normalize_financial_statement_maps_dart_accounts_to_fundamentals():
    raw = pd.DataFrame(
        [
            {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "10,000"},
            {"sj_div": "IS", "account_nm": "매출총이익", "thstrm_amount": "4,000"},
            {"sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "2,000"},
            {"sj_div": "IS", "account_nm": "당기순이익", "thstrm_amount": "1,000"},
            {"sj_div": "BS", "account_nm": "자산총계", "thstrm_amount": "20,000"},
            {"sj_div": "BS", "account_nm": "유동자산", "thstrm_amount": "8,000"},
            {"sj_div": "BS", "account_nm": "현금및현금성자산", "thstrm_amount": "3,000"},
            {"sj_div": "BS", "account_nm": "부채총계", "thstrm_amount": "5,000"},
            {"sj_div": "BS", "account_nm": "유동부채", "thstrm_amount": "2,500"},
            {"sj_div": "BS", "account_nm": "자본총계", "thstrm_amount": "15,000"},
            {"sj_div": "CF", "account_nm": "영업활동현금흐름", "thstrm_amount": "1,500"},
            {"sj_div": "CF", "account_nm": "유형자산의 취득", "thstrm_amount": "(500)"},
            {"sj_div": "IS", "account_nm": "기본주당이익", "thstrm_amount": "1,234"},
        ]
    )

    result = normalize_financial_statement(raw, "5930", 2025)

    assert result is not None
    assert result["stock_code"] == "005930"
    assert result["fiscal_year"] == 2025
    assert result["fiscal_quarter"] == 0
    assert result["revenue"] == 10_000
    assert result["operating_profit"] == 2_000
    assert result["capex"] == -500
    assert result["free_cash_flow"] == 1_000
    assert result["eps"] == 1_234
    assert result["roe"] == 1_000 / 15_000
    assert result["current_ratio"] == 8_000 / 2_500
    assert result["data_source"] == "dart"


def test_normalize_financial_statement_treats_positive_capex_as_cash_outflow():
    raw = pd.DataFrame(
        [
            {"sj_div": "CF", "account_nm": "영업활동현금흐름", "thstrm_amount": "1,500"},
            {"sj_div": "CF", "account_nm": "유형자산의 취득", "thstrm_amount": "500"},
        ]
    )

    result = normalize_financial_statement(raw, "005930", 2025)

    assert result is not None
    assert result["capex"] == -500
    assert result["free_cash_flow"] == 1_000


def test_normalize_financial_statement_returns_none_for_empty_data():
    result = normalize_financial_statement(pd.DataFrame(), "005930", 2025)

    assert result is None


def test_fetch_financial_statements_collects_requested_years(monkeypatch):
    class FakeDart:
        def __init__(self):
            self.calls = []

        def finstate(self, code, year, reprt_code):
            self.calls.append((code, year, reprt_code))
            return pd.DataFrame(
                [
                    {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": str(year)},
                    {"sj_div": "BS", "account_nm": "자산총계", "thstrm_amount": "100"},
                ]
            )

    fake = FakeDart()
    tickers = pd.DataFrame(
        [
            {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI"},
        ]
    )
    monkeypatch.setattr("src.collectors.dart_financials.settings.MAX_TICKERS", 0)

    result = fetch_financial_statements(tickers, years=2, base_year=2025, client=fake)

    assert fake.calls == [
        ("005930", 2024, "11011"),
        ("005930", 2025, "11011"),
        ("000660", 2024, "11011"),
        ("000660", 2025, "11011"),
    ]
    assert len(result) == 4
    assert result.loc[0, "revenue"] == 2024
    assert result.loc[3, "stock_code"] == "000660"


def test_fetch_financial_statements_stops_when_quota_exhausted(monkeypatch):
    class FakeDart:
        def __init__(self):
            self.calls = []

        def finstate(self, code, year, reprt_code):
            self.calls.append((code, year, reprt_code))
            return pd.DataFrame(
                [
                    {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": str(year)},
                    {"sj_div": "BS", "account_nm": "자산총계", "thstrm_amount": "100"},
                ]
            )

    fake = FakeDart()
    tickers = pd.DataFrame(
        [
            {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI"},
        ]
    )
    monkeypatch.setattr("src.collectors.dart_financials.settings.MAX_TICKERS", 0)
    dart_financials._quota_tracker.add_calls(9999)

    result = fetch_financial_statements(tickers, years=2, base_year=2025, client=fake)

    assert len(fake.calls) == 1
    assert fake.calls[0] == ("005930", 2024, "11011")
    assert len(result) == 1
    assert result.loc[0, "stock_code"] == "005930"
