"""data_loader 단위 테스트.

Streamlit 캐시 데코레이터를 identity 함수로 교체하고
인메모리 SQLite로 쿼리 로직을 검증한다.
"""
from __future__ import annotations

import sqlite3
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

# ── Streamlit 모킹: 테스트 환경에서 @st.cache_resource/@st.cache_data를 no-op으로 ──
_mock_st = types.ModuleType("streamlit")
_mock_st.cache_resource = lambda **kw: (lambda f: f)
_mock_st.cache_data = lambda **kw: (lambda f: f)
sys.modules.setdefault("streamlit", _mock_st)

# data_loader를 모킹된 streamlit이 로드된 후에 임포트
from src.ui.data_loader import (  # noqa: E402
    get_latest_run_date,
    load_metadata,
    load_rankings,
    load_stock_detail,
)

_RUN_DATE = "2025-01-20"


# ── 인메모리 DB 픽스처 ─────────────────────────────────────────────────────────

def _make_db() -> sqlite3.Connection:
    """스크리닝 결과가 있는 인메모리 SQLite DB를 생성한다."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE pipeline_runs (
            run_date TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );
        CREATE TABLE stocks (
            stock_code TEXT PRIMARY KEY,
            stock_name TEXT,
            market TEXT,
            sector TEXT,
            industry TEXT,
            listing_date TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            date TEXT,
            close REAL,
            volume INTEGER,
            per REAL,
            pbr REAL,
            market_cap REAL,
            dividend_yield REAL
        );
        CREATE TABLE fundamentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            fiscal_year INTEGER,
            fiscal_quarter INTEGER DEFAULT 0,
            revenue REAL,
            operating_profit REAL,
            net_profit REAL,
            roe REAL,
            debt_to_equity REAL,
            free_cash_flow REAL
        );
        CREATE TABLE scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            run_date TEXT,
            composite_score REAL,
            value_score REAL,
            quality_score REAL,
            safety_score REAL,
            growth_score REAL,
            momentum_score REAL,
            stage1_pass INTEGER DEFAULT 0,
            is_value_trap INTEGER DEFAULT 0,
            final_rank INTEGER
        );
        CREATE TABLE risk_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT,
            run_date TEXT,
            flag_type TEXT,
            flag_description TEXT,
            severity TEXT,
            metric_value REAL,
            threshold_value REAL
        );
        CREATE TABLE rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT,
            rank INTEGER,
            stock_code TEXT,
            stock_name TEXT,
            market TEXT,
            sector TEXT,
            composite_score REAL,
            value_score REAL,
            quality_score REAL,
            safety_score REAL,
            growth_score REAL,
            momentum_score REAL,
            market_cap_b REAL,
            per REAL,
            pbr REAL,
            roe REAL,
            dividend_yield REAL,
            debt_to_equity REAL,
            risk_flag_count INTEGER DEFAULT 0,
            highest_severity TEXT
        );
    """)

    # 파이프라인 실행 기록
    conn.execute(
        "INSERT INTO pipeline_runs VALUES (?, 'SUCCESS', '2025-01-20T08:00:00Z', '2025-01-20T09:30:00Z')",
        (_RUN_DATE,),
    )
    # 이전 실패 실행
    conn.execute(
        "INSERT INTO pipeline_runs VALUES ('2025-01-19', 'FAILED', NULL, NULL)"
    )

    # 종목
    stocks = [
        ("005930", "삼성전자", "KOSPI", "IT", "반도체", "1975-06-11"),
        ("000660", "SK하이닉스", "KOSPI", "IT", "반도체", "1996-12-26"),
        ("035420", "NAVER", "KOSPI", "IT", "인터넷", "2002-10-29"),
        ("086520", "에코프로", "KOSDAQ", "소재", "2차전지", "2007-03-23"),
    ]
    conn.executemany(
        "INSERT INTO stocks (stock_code, stock_name, market, sector, industry, listing_date) VALUES (?,?,?,?,?,?)",
        stocks,
    )

    # 랭킹
    rankings = [
        (_RUN_DATE, 1, "005930", "삼성전자", "KOSPI", "IT", 82.5, 85.0, 80.0, 78.0, 75.0, 70.0, 400.0, 9.0, 1.2, 18.0, 2.5, 0.5, 0, None),
        (_RUN_DATE, 2, "000660", "SK하이닉스", "KOSPI", "IT", 76.3, 78.0, 75.0, 72.0, 70.0, 65.0, 50.0, 11.0, 1.5, 15.0, 1.5, 0.8, 1, "MEDIUM"),
        (_RUN_DATE, 3, "035420", "NAVER", "KOSPI", "IT", 70.1, 72.0, 68.0, 71.0, 65.0, 60.0, 30.0, 25.0, 3.0, 10.0, 0.5, 0.3, 0, None),
        (_RUN_DATE, 4, "086520", "에코프로", "KOSDAQ", "소재", 65.8, 70.0, 60.0, 55.0, 75.0, 80.0, 5.0, 60.0, 8.0, 25.0, 0.0, 2.5, 2, "HIGH"),
    ]
    conn.executemany(
        """INSERT INTO rankings (run_date, rank, stock_code, stock_name, market, sector,
           composite_score, value_score, quality_score, safety_score, growth_score, momentum_score,
           market_cap_b, per, pbr, roe, dividend_yield, debt_to_equity, risk_flag_count, highest_severity)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rankings,
    )

    # scores
    conn.execute(
        "INSERT INTO scores (stock_code, run_date, composite_score, stage1_pass, is_value_trap, final_rank) "
        "VALUES ('005930', ?, 82.5, 1, 0, 1)",
        (_RUN_DATE,),
    )

    # risk_flags (SK하이닉스에 MEDIUM 플래그)
    conn.execute(
        "INSERT INTO risk_flags (stock_code, run_date, flag_type, flag_description, severity) "
        "VALUES ('000660', ?, 'DECLINING_REVENUE', '매출 YoY 5% 이상 감소', 'MEDIUM')",
        (_RUN_DATE,),
    )

    # prices (삼성전자 최근 2일)
    conn.execute(
        "INSERT INTO prices (stock_code, date, close, volume, per, pbr) "
        "VALUES ('005930', '2025-01-20', 72000, 15000000, 9.0, 1.2)"
    )
    conn.execute(
        "INSERT INTO prices (stock_code, date, close, volume, per, pbr) "
        "VALUES ('005930', '2025-01-19', 71000, 12000000, 8.9, 1.19)"
    )

    # fundamentals (삼성전자 2년)
    conn.execute(
        "INSERT INTO fundamentals (stock_code, fiscal_year, fiscal_quarter, revenue, operating_profit, net_profit, roe, debt_to_equity, free_cash_flow) "
        "VALUES ('005930', 2024, 0, 320000, 32000, 26000, 18.0, 0.5, 20000)"
    )
    conn.execute(
        "INSERT INTO fundamentals (stock_code, fiscal_year, fiscal_quarter, revenue, operating_profit, net_profit, roe, debt_to_equity, free_cash_flow) "
        "VALUES ('005930', 2023, 0, 258000, 6000, 15000, 9.0, 0.4, 5000)"
    )

    conn.commit()
    return conn


class GetLatestRunDateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _make_db()

    def tearDown(self) -> None:
        self.conn.close()

    def test_returns_most_recent_success_date(self) -> None:
        result = get_latest_run_date(self.conn)
        self.assertEqual(result, _RUN_DATE)

    def test_ignores_failed_runs(self) -> None:
        result = get_latest_run_date(self.conn)
        self.assertNotEqual(result, "2025-01-19")

    def test_returns_none_when_no_success(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE pipeline_runs (run_date TEXT, status TEXT)")
        conn.execute("INSERT INTO pipeline_runs VALUES ('2025-01-19', 'FAILED')")
        conn.commit()
        self.assertIsNone(get_latest_run_date(conn))
        conn.close()


class LoadRankingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _make_db()

    def tearDown(self) -> None:
        self.conn.close()

    def test_returns_dataframe(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings()
        self.assertIsInstance(result, pd.DataFrame)

    def test_returns_all_stocks_by_default(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings()
        self.assertEqual(len(result), 4)

    def test_sorted_by_rank_ascending(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings()
        ranks = result["rank"].tolist()
        self.assertEqual(ranks, sorted(ranks))

    def test_market_filter_kospi(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings(market="KOSPI")
        self.assertTrue((result["market"] == "KOSPI").all())
        self.assertEqual(len(result), 3)

    def test_market_filter_kosdaq(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings(market="KOSDAQ")
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["stock_code"], "086520")

    def test_min_score_filter(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings(min_score=75.0)
        self.assertTrue((result["composite_score"] >= 75.0).all())
        self.assertEqual(len(result), 2)

    def test_combined_filters(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings(market="KOSPI", min_score=75.0)
        self.assertEqual(len(result), 2)
        self.assertTrue((result["market"] == "KOSPI").all())

    def test_contains_listing_date_from_stocks(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings()
        self.assertIn("listing_date", result.columns)

    def test_empty_result_when_no_match(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings(min_score=99.0)
        self.assertTrue(result.empty)

    def test_uses_latest_success_run_date_only(self) -> None:
        # 이전 실패 실행 데이터가 섞이지 않아야 함
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_rankings()
        self.assertTrue((result["run_date"] == _RUN_DATE).all())


class LoadStockDetailTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _make_db()

    def tearDown(self) -> None:
        self.conn.close()

    def test_returns_dict_with_expected_keys(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        self.assertIn("scores", result)
        self.assertIn("flags", result)
        self.assertIn("fundamentals", result)
        self.assertIn("prices", result)

    def test_all_values_are_dataframes(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        for key, val in result.items():
            self.assertIsInstance(val, pd.DataFrame, f"{key} is not a DataFrame")

    def test_scores_has_one_row(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        self.assertEqual(len(result["scores"]), 1)

    def test_scores_contains_composite_score(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        self.assertAlmostEqual(result["scores"].iloc[0]["composite_score"], 82.5)

    def test_flags_returns_correct_stock(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("000660")
        self.assertEqual(len(result["flags"]), 1)
        self.assertEqual(result["flags"].iloc[0]["flag_type"], "DECLINING_REVENUE")

    def test_flags_empty_for_clean_stock(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        self.assertTrue(result["flags"].empty)

    def test_fundamentals_ordered_by_year_desc(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        years = result["fundamentals"]["fiscal_year"].tolist()
        self.assertEqual(years, sorted(years, reverse=True))

    def test_fundamentals_limited_to_6(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        self.assertLessEqual(len(result["fundamentals"]), 6)

    def test_prices_ordered_by_date_desc(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        dates = result["prices"]["date"].tolist()
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_prices_limited_to_252(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        self.assertLessEqual(len(result["prices"]), 252)

    def test_prices_columns(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("005930")
        expected = {"date", "close", "volume", "per", "pbr"}
        self.assertTrue(expected.issubset(set(result["prices"].columns)))

    def test_unknown_stock_returns_empty_frames(self) -> None:
        with patch("src.ui.data_loader.get_db_connection", return_value=self.conn):
            result = load_stock_detail("999999")
        for key in ("scores", "flags", "fundamentals", "prices"):
            self.assertTrue(result[key].empty, f"{key} should be empty for unknown stock")


class LoadMetadataTest(unittest.TestCase):
    def test_returns_dict_from_downloader(self) -> None:
        meta = {
            "run_date": "2025-01-20",
            "final_candidates": 73,
            "top_candidates": [],
        }
        with patch("src.ui.data_loader.get_metadata", return_value=meta):
            result = load_metadata()
        self.assertEqual(result["run_date"], "2025-01-20")
        self.assertEqual(result["final_candidates"], 73)

    def test_passes_through_all_fields(self) -> None:
        meta = {"a": 1, "b": "two", "c": [3]}
        with patch("src.ui.data_loader.get_metadata", return_value=meta):
            result = load_metadata()
        self.assertEqual(result, meta)


if __name__ == "__main__":
    unittest.main()
