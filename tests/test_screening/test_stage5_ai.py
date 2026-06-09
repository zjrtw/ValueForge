from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.collectors.news_collector import NewsArticle
from src.db.repository import Repository
from src.db.schema import initialize_schema
from src.screening.stage5_ai_analysis import _parse_sentiment, stage5_ai_analysis

# ---------------------------------------------------------------------------
# 공통 파라미터
# ---------------------------------------------------------------------------

_PARAMS = {
    "enabled": True,
    "top_n": 3,
    "model": "gemini-1.5-flash",
    "rate_limit_sleep": 0,
}

_RUN_DATE = "2026-06-04"

_POSITIVE_RESPONSE = "저평가된 우량주로 판단됩니다.\n투자의견: 긍정"
_NEGATIVE_RESPONSE = "재무 리스크가 확인됩니다.\n투자의견: 부정"
_NEUTRAL_RESPONSE  = "현 시점에서 중립적 시각을 유지합니다.\n투자의견: 중립"


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    initialize_schema(conn)
    # ai_insights FK(ticker → stocks.stock_code) 충족을 위해 테스트 종목 삽입
    conn.executemany(
        "INSERT INTO stocks (stock_code, stock_name, market, is_active) VALUES (?, ?, 'KOSPI', 1)",
        [(str(100001 + i), f"테스트종목{i + 1}") for i in range(10)],
    )
    conn.commit()
    yield conn
    conn.close()


def _make_ranked_df(n: int = 5) -> pd.DataFrame:
    rows = [
        {
            "stock_code": str(100001 + i),
            "stock_name": f"테스트종목{i + 1}",
            "market": "KOSPI",
            "sector": "제조업",
            "composite_score": 80.0 - i * 2,
            "per": 12.0 + i,
            "pbr": 1.5,
            "roe": 15.0,
            "dividend_yield": 2.5,
            "adjusted_score": 78.0 - i * 2,
            "final_rank": i + 1,
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


def _mock_client(mocker, *, available: bool = True, response: str = _POSITIVE_RESPONSE):
    client = mocker.MagicMock()
    client.is_available.return_value = available
    client.generate.return_value = response
    return client


# ---------------------------------------------------------------------------
# 건너뜀 동작 테스트
# ---------------------------------------------------------------------------


class TestStage5Skip:
    def test_skips_when_client_unavailable(self, mocker, db_conn):
        client = _mock_client(mocker, available=False)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        result = stage5_ai_analysis(
            _make_ranked_df(), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        assert result == 0
        client.generate.assert_not_called()

    def test_skips_when_disabled_in_params(self, mocker, db_conn):
        client = _mock_client(mocker)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        result = stage5_ai_analysis(
            _make_ranked_df(), db_conn, _RUN_DATE,
            params={**_PARAMS, "enabled": False}, gemini_client=client,
        )
        assert result == 0
        client.generate.assert_not_called()

    def test_no_ai_insights_saved_when_skipped(self, mocker, db_conn):
        client = _mock_client(mocker, available=False)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        row = db_conn.execute("SELECT COUNT(*) FROM ai_insights").fetchone()
        assert row[0] == 0


# ---------------------------------------------------------------------------
# 저장 동작 테스트
# ---------------------------------------------------------------------------


class TestStage5Save:
    def test_returns_count_of_saved_insights(self, mocker, db_conn):
        client = _mock_client(mocker)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        result = stage5_ai_analysis(
            _make_ranked_df(5), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        assert result == 3  # top_n=3

    def test_saves_only_top_n_stocks(self, mocker, db_conn):
        client = _mock_client(mocker)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(10), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        row = db_conn.execute("SELECT COUNT(*) FROM ai_insights").fetchone()
        assert row[0] == 3

    def test_saved_record_has_correct_ticker_and_run_date(self, mocker, db_conn):
        client = _mock_client(mocker)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        repo = Repository(db_conn)
        record = repo.get_ai_insight("100001", _RUN_DATE)
        assert record is not None
        assert record["ticker"] == "100001"
        assert record["run_date"] == _RUN_DATE

    def test_saved_record_contains_guide_text(self, mocker, db_conn):
        client = _mock_client(mocker, response=_POSITIVE_RESPONSE)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        repo = Repository(db_conn)
        record = repo.get_ai_insight("100001", _RUN_DATE)
        assert record["guide_text"] == _POSITIVE_RESPONSE

    def test_saved_record_contains_model_used(self, mocker, db_conn):
        client = _mock_client(mocker)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1, "model": "gemini-1.5-flash"}, gemini_client=client,
        )
        repo = Repository(db_conn)
        record = repo.get_ai_insight("100001", _RUN_DATE)
        assert record["model_used"] == "gemini-1.5-flash"

    def test_upsert_overwrites_existing_record(self, mocker, db_conn):
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])
        p = {**_PARAMS, "top_n": 1}

        client1 = _mock_client(mocker, response="초기 응답\n투자의견: 중립")
        stage5_ai_analysis(_make_ranked_df(1), db_conn, _RUN_DATE, params=p, gemini_client=client1)

        client2 = _mock_client(mocker, response="갱신 응답\n투자의견: 긍정")
        stage5_ai_analysis(_make_ranked_df(1), db_conn, _RUN_DATE, params=p, gemini_client=client2)

        row = db_conn.execute("SELECT COUNT(*) FROM ai_insights").fetchone()
        assert row[0] == 1

        repo = Repository(db_conn)
        record = repo.get_ai_insight("100001", _RUN_DATE)
        assert "갱신 응답" in record["guide_text"]


# ---------------------------------------------------------------------------
# 감성 파싱 테스트
# ---------------------------------------------------------------------------


class TestSentimentParsing:
    def test_positive_sentiment_from_response(self, mocker, db_conn):
        client = _mock_client(mocker, response=_POSITIVE_RESPONSE)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        record = Repository(db_conn).get_ai_insight("100001", _RUN_DATE)
        assert record["sentiment"] == "긍정"

    def test_negative_sentiment_from_response(self, mocker, db_conn):
        client = _mock_client(mocker, response=_NEGATIVE_RESPONSE)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        record = Repository(db_conn).get_ai_insight("100001", _RUN_DATE)
        assert record["sentiment"] == "부정"

    def test_neutral_sentiment_as_default(self, mocker, db_conn):
        client = _mock_client(mocker, response="마커 없는 응답입니다.")
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        record = Repository(db_conn).get_ai_insight("100001", _RUN_DATE)
        assert record["sentiment"] == "중립"

    def test_parse_sentiment_unit_positive(self):
        assert _parse_sentiment("좋습니다.\n투자의견: 긍정") == "긍정"

    def test_parse_sentiment_unit_negative(self):
        assert _parse_sentiment("위험합니다.\n투자의견: 부정") == "부정"

    def test_parse_sentiment_unit_no_colon_space(self):
        assert _parse_sentiment("투자의견:긍정") == "긍정"

    def test_parse_sentiment_unit_neutral_default(self):
        assert _parse_sentiment("아무 마커도 없는 텍스트") == "중립"

    def test_parse_sentiment_unit_neutral_explicit(self):
        assert _parse_sentiment("투자의견: 중립") == "중립"


# ---------------------------------------------------------------------------
# 뉴스 수집 연동 테스트
# ---------------------------------------------------------------------------


class TestStage5NewsFetch:
    def test_fetch_news_called_for_each_top_n_stock(self, mocker, db_conn):
        client = _mock_client(mocker)
        fetch_mock = mocker.patch(
            "src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[]
        )
        stage5_ai_analysis(
            _make_ranked_df(5), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        assert fetch_mock.call_count == 3  # top_n=3

    def test_news_articles_included_in_prompt(self, mocker, db_conn):
        articles = [
            NewsArticle(title="삼성전자 호실적", link="http://example.com/1", published_at="2026.06.04 09:00"),
        ]
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=articles)
        client = _mock_client(mocker)
        prompts_captured = []
        original_generate = client.generate.side_effect

        def capture_generate(prompt):
            prompts_captured.append(prompt)
            return _POSITIVE_RESPONSE
        client.generate.side_effect = capture_generate

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        assert any("삼성전자 호실적" in p for p in prompts_captured)

    def test_no_news_section_when_empty(self, mocker, db_conn):
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])
        client = _mock_client(mocker)
        prompts_captured = []

        def capture_generate(prompt):
            prompts_captured.append(prompt)
            return _POSITIVE_RESPONSE
        client.generate.side_effect = capture_generate

        stage5_ai_analysis(
            _make_ranked_df(1), db_conn, _RUN_DATE,
            params={**_PARAMS, "top_n": 1}, gemini_client=client,
        )
        assert "(수집된 뉴스 없음)" in prompts_captured[0]


# ---------------------------------------------------------------------------
# 오류 처리 테스트
# ---------------------------------------------------------------------------


class TestStage5ErrorHandling:
    def test_gemini_failure_skips_stock_and_continues(self, mocker, db_conn):
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])
        client = mocker.MagicMock()
        client.is_available.return_value = True

        call_count = 0
        def side_effect(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("API 오류")
            return _POSITIVE_RESPONSE

        client.generate.side_effect = side_effect

        result = stage5_ai_analysis(
            _make_ranked_df(5), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        # 첫 번째 실패, 나머지 2개 성공
        assert result == 2
        row = db_conn.execute("SELECT COUNT(*) FROM ai_insights").fetchone()
        assert row[0] == 2

    def test_all_gemini_failures_returns_zero(self, mocker, db_conn):
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])
        client = mocker.MagicMock()
        client.is_available.return_value = True
        client.generate.side_effect = RuntimeError("모든 요청 실패")

        result = stage5_ai_analysis(
            _make_ranked_df(3), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        assert result == 0

    def test_empty_ranked_df_returns_zero(self, mocker, db_conn):
        client = _mock_client(mocker)
        mocker.patch("src.screening.stage5_ai_analysis.fetch_stock_news", return_value=[])

        result = stage5_ai_analysis(
            pd.DataFrame(), db_conn, _RUN_DATE,
            params=_PARAMS, gemini_client=client,
        )
        assert result == 0
