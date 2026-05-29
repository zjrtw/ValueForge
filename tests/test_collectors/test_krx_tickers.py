"""krx_tickers 수집기 단위 테스트.

krx_client.fetch_issue_base_info 를 모킹하여 실제 네트워크 호출 없이 동작을 검증한다.
"""
import pytest

from src.collectors.krx_tickers import fetch_ticker_list

# KRX Open API stk_isu_base_info / ksq_isu_base_info 응답 형식
_FAKE_KOSPI = [
    {"ISU_SRT_CD": "005930", "ISU_NM": "삼성전자보통주", "ISU_ABBRV": "삼성전자",  "LIST_DD": "19750611", "LIST_SHRS": "5969782550"},
    {"ISU_SRT_CD": "000660", "ISU_NM": "SK하이닉스보통주", "ISU_ABBRV": "SK하이닉스", "LIST_DD": "19960326", "LIST_SHRS": "728002365"},
    {"ISU_SRT_CD": "051910", "ISU_NM": "LG화학보통주",   "ISU_ABBRV": "LG화학",    "LIST_DD": "20010714", "LIST_SHRS": "70592343"},
]
_FAKE_KOSDAQ = [
    {"ISU_SRT_CD": "091990", "ISU_NM": "셀트리온헬스케어보통주", "ISU_ABBRV": "셀트리온헬스케어", "LIST_DD": "20120229", "LIST_SHRS": "130628849"},
    {"ISU_SRT_CD": "263750", "ISU_NM": "펄어비스보통주",         "ISU_ABBRV": "펄어비스",         "LIST_DD": "20170904", "LIST_SHRS": "18576213"},
    {"ISU_SRT_CD": "035900", "ISU_NM": "JYP Ent.보통주",        "ISU_ABBRV": "JYP Ent.",        "LIST_DD": "20010115", "LIST_SHRS": "74845685"},
]


def _fake_issue_base_info(endpoint: str, bas_dd: str) -> list[dict]:
    if "stk" in endpoint:
        return _FAKE_KOSPI
    return _FAKE_KOSDAQ


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 0)
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSPI,KOSDAQ")


@pytest.fixture()
def patch_api(monkeypatch):
    monkeypatch.setattr(
        "src.collectors.krx_tickers.fetch_issue_base_info",
        _fake_issue_base_info,
    )


# ── fetch_ticker_list ────────────────────────────────────────────────────────

def test_returns_kospi_and_kosdaq(patch_api):
    result = fetch_ticker_list()

    assert not result.empty
    assert list(result.columns) == ["stock_code", "stock_name", "market", "listing_date", "shares_outstanding"]
    assert len(result[result["market"] == "KOSPI"]) == len(_FAKE_KOSPI)
    assert len(result[result["market"] == "KOSDAQ"]) == len(_FAKE_KOSDAQ)


def test_all_codes_are_six_digit_numeric(patch_api):
    result = fetch_ticker_list()

    assert result["stock_code"].str.len().unique().tolist() == [6]
    assert result["stock_code"].str.match(r"^\d{6}$").all()


def test_stock_names_use_abbreviation(patch_api):
    result = fetch_ticker_list()

    samsung = result[result["stock_code"] == "005930"]
    assert not samsung.empty
    assert samsung.iloc[0]["stock_name"] == "삼성전자"


def test_respects_max_tickers(monkeypatch, patch_api):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MAX_TICKERS", 2)

    result = fetch_ticker_list()

    assert len(result) == 2


def test_max_tickers_zero_returns_all(patch_api):
    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI) + len(_FAKE_KOSDAQ)


def test_kospi_only_market_setting(monkeypatch, patch_api):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSPI")

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI)
    assert set(result["market"]) == {"KOSPI"}


def test_kosdaq_only_market_setting(monkeypatch, patch_api):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KOSDAQ")

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSDAQ)
    assert set(result["market"]) == {"KOSDAQ"}


def test_all_market_setting(monkeypatch, patch_api):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "ALL")

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSPI) + len(_FAKE_KOSDAQ)
    assert set(result["market"]) == {"KOSPI", "KOSDAQ"}


def test_invalid_market_raises(monkeypatch):
    monkeypatch.setattr("src.collectors.krx_tickers.settings.MARKETS", "KONEX")

    with pytest.raises(ValueError, match="Invalid MARKETS value"):
        fetch_ticker_list()


def test_api_error_skips_market(monkeypatch):
    """한 시장 API 호출 실패 시 해당 시장을 건너뛰고 나머지를 반환한다."""
    def failing_kospi(endpoint: str, bas_dd: str) -> list[dict]:
        if "stk" in endpoint:
            raise RuntimeError("API 오류")
        return _FAKE_KOSDAQ

    monkeypatch.setattr("src.collectors.krx_tickers.fetch_issue_base_info", failing_kospi)

    result = fetch_ticker_list()

    assert len(result) == len(_FAKE_KOSDAQ)
    assert set(result["market"]) == {"KOSDAQ"}


# ── fetch_ticker_list: listing_date inclusion ──────────────────────────────

def test_listing_date_format(patch_api):
    """fetch_ticker_list에서 반환하는 listing_date가 YYYY-MM-DD 형식인지 확인."""
    result = fetch_ticker_list()

    dates = result["listing_date"].dropna()
    assert dates.str.match(r"^\d{4}-\d{2}-\d{2}$").all(), "날짜가 YYYY-MM-DD 형식이어야 함"


def test_listing_date_slash_format(monkeypatch):
    """LIST_DD가 YYYY/MM/DD 형식인 경우도 정상 처리된다."""
    slash_data = [{"ISU_SRT_CD": "005930", "ISU_ABBRV": "삼성전자", "LIST_DD": "1975/06/11", "LIST_SHRS": "5969782550"}]
    monkeypatch.setattr(
        "src.collectors.krx_tickers.fetch_issue_base_info",
        lambda ep, d: slash_data if "stk" in ep else [],
    )

    result = fetch_ticker_list()

    assert result.iloc[0]["listing_date"] == "1975-06-11"


def test_shares_outstanding_is_integer(patch_api):
    result = fetch_ticker_list()

    non_null = result["shares_outstanding"].dropna()
    assert (non_null == non_null.astype(int)).all()


# ── Auto-fallback (empty response retry) ─────────────────────────────────────

def test_fetch_ticker_list_retries_on_empty_response(monkeypatch):
    """기준일 데이터 없으면 자동으로 이전 거래일로 재시도한다."""
    call_count = {"stk": 0, "ksq": 0}

    def counting_fetch_issue_base_info(endpoint: str, bas_dd: str) -> list[dict]:
        if "stk" in endpoint:
            call_count["stk"] += 1
            # 첫 호출(20260529)은 빈 응답, 두 번째(20260528)는 데이터 반환
            if bas_dd == "20260529":
                return []
            return _FAKE_KOSPI
        call_count["ksq"] += 1
        # 첫 호출은 빈 응답, 재시도는 데이터 반환
        if bas_dd == "20260529":
            return []
        return _FAKE_KOSDAQ

    monkeypatch.setattr("src.collectors.krx_tickers.fetch_issue_base_info", counting_fetch_issue_base_info)

    result = fetch_ticker_list("2026-05-29")

    # 각 시장별 2회 호출 (초회 실패 + 재시도 성공)
    assert call_count["stk"] == 2
    assert call_count["ksq"] == 2
    # 데이터는 정상 반환
    assert not result.empty
    assert len(result) == len(_FAKE_KOSPI) + len(_FAKE_KOSDAQ)
