import sqlite3
import unittest
import json

import pandas as pd

from src.db.repository import Repository


class RepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.repo = Repository(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_upsert_stocks_inserts_and_updates_rows(self) -> None:
        inserted = self.repo.upsert_stocks(
            pd.DataFrame(
                [
                    {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
                    {"stock_code": "091990", "stock_name": "테스트", "market": "KOSDAQ"},
                ]
            )
        )
        updated = self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자우", "market": "KOSPI"}]
        )

        count = self.conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        name = self.conn.execute(
            "SELECT stock_name FROM stocks WHERE stock_code = ?", ("005930",)
        ).fetchone()[0]

        self.assertEqual(inserted, 2)
        self.assertEqual(updated, 1)
        self.assertEqual(count, 2)
        self.assertEqual(name, "삼성전자우")

    def test_upsert_prices_inserts_and_updates_unique_snapshot(self) -> None:
        self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
        )

        inserted = self.repo.upsert_prices(
            pd.DataFrame(
                [
                    {
                        "stock_code": "005930",
                        "date": "2026-05-20",
                        "close": 70000,
                        "volume": 1000,
                        "market_cap": 400_000_000,
                        "per": 10.5,
                        "pbr": 1.2,
                        "dividend_yield": 2.1,
                    }
                ]
            )
        )
        updated = self.repo.upsert_prices(
            [{"stock_code": "005930", "date": "2026-05-20", "close": 71000}]
        )

        row = self.conn.execute(
            "SELECT COUNT(*), close, per FROM prices WHERE stock_code = ?",
            ("005930",),
        ).fetchone()

        self.assertEqual(inserted, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 71000)
        self.assertIsNone(row[2])

    def test_upsert_fundamentals_inserts_and_updates_rows(self) -> None:
        self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
        )

        inserted = self.repo.upsert_fundamentals(
            [
                {
                    "stock_code": "005930",
                    "fiscal_year": 2025,
                    "fiscal_quarter": None,
                    "revenue": 300_000,
                    "operating_profit": 35_000,
                    "roe": 12.3,
                }
            ]
        )
        updated = self.repo.upsert_fundamentals(
            pd.DataFrame(
                [
                    {
                        "stock_code": "005930",
                        "fiscal_year": 2025,
                        "fiscal_quarter": None,
                        "revenue": 310_000,
                        "data_source": "manual",
                    }
                ]
            )
        )

        row = self.conn.execute(
            """
            SELECT COUNT(*), revenue, operating_profit, data_source
            FROM fundamentals
            WHERE stock_code = ? AND fiscal_year = ?
            """,
            ("005930", 2025),
        ).fetchone()

        self.assertEqual(inserted, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 310_000)
        self.assertIsNone(row[2])
        self.assertEqual(row[3], "manual")

    def test_upsert_methods_return_zero_for_empty_inputs(self) -> None:
        self.assertEqual(self.repo.upsert_stocks([]), 0)
        self.assertEqual(self.repo.upsert_prices(pd.DataFrame()), 0)
        self.assertEqual(self.repo.upsert_fundamentals([]), 0)

    def test_get_screening_dataset_joins_active_stocks_latest_price_and_fundamentals(self) -> None:
        self.repo.upsert_stocks(
            [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "반도체",
                    "listing_date": "2020-01-01",
                },
                {
                    "stock_code": "091990",
                    "stock_name": "테스트",
                    "market": "KOSDAQ",
                    "is_active": 0,
                },
            ]
        )
        self.repo.upsert_prices(
            [
                {
                    "stock_code": "005930",
                    "date": "2026-05-19",
                    "close": 69000,
                    "market_cap": 390_000,
                    "per": 9.5,
                    "pbr": 1.1,
                },
                {
                    "stock_code": "005930",
                    "date": "2026-05-20",
                    "close": 70000,
                    "market_cap": 400_000,
                    "per": 10.5,
                    "pbr": 1.2,
                    "dividend_yield": 2.1,
                },
            ]
        )
        self.repo.upsert_fundamentals(
            [
                {
                    "stock_code": "005930",
                    "fiscal_year": 2024,
                    "revenue": 250_000,
                    "roe": 10.0,
                },
                {
                    "stock_code": "005930",
                    "fiscal_year": 2025,
                    "revenue": 300_000,
                    "roe": 12.0,
                    "debt_to_equity": 35.0,
                },
            ]
        )

        result = self.repo.get_screening_dataset(run_date="2026-05-20")

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["stock_code"], "005930")
        self.assertEqual(row["price_date"], "2026-05-20")
        self.assertEqual(row["close"], 70000)
        self.assertEqual(row["fiscal_year"], 2025)
        self.assertEqual(row["revenue"], 300_000)
        self.assertEqual(row["roe"], 12.0)
        self.assertEqual(row["listing_days"], 2331)

    def test_get_screening_dataset_respects_run_date_price_cutoff(self) -> None:
        self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
        )
        self.repo.upsert_prices(
            [
                {"stock_code": "005930", "date": "2026-05-19", "close": 69000},
                {"stock_code": "005930", "date": "2026-05-20", "close": 70000},
            ]
        )

        result = self.repo.get_screening_dataset(run_date="2026-05-19")

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["price_date"], "2026-05-19")
        self.assertEqual(result.iloc[0]["close"], 69000)

    def test_record_run_start_creates_running_row(self) -> None:
        self.repo.record_run_start("2026-05-20", pipeline_version="0.1.0")

        row = self.conn.execute(
            """
            SELECT run_date, started_at, completed_at, status, pipeline_version
            FROM pipeline_runs
            WHERE run_date = ?
            """,
            ("2026-05-20",),
        ).fetchone()

        self.assertEqual(row[0], "2026-05-20")
        self.assertIsNotNone(row[1])
        self.assertIsNone(row[2])
        self.assertEqual(row[3], "RUNNING")
        self.assertEqual(row[4], "0.1.0")

    def test_record_run_success_updates_stats_and_warnings(self) -> None:
        self.repo.record_run_start("2026-05-20", pipeline_version="0.1.0")
        self.repo.record_run_success(
            "2026-05-20",
            stocks_collected=100,
            stocks_with_data=95,
            collection_errors=5,
            stage1_pass_count=30,
            stage2_score_count=28,
            stage3_trap_count=3,
            final_candidates=25,
            warnings=["일부 종목 누락"],
        )

        row = self.conn.execute(
            """
            SELECT status, completed_at, duration_seconds, stocks_collected,
                   stocks_with_data, collection_errors, stage1_pass_count,
                   stage2_score_count, stage3_trap_count, final_candidates,
                   error_message, warnings
            FROM pipeline_runs
            WHERE run_date = ?
            """,
            ("2026-05-20",),
        ).fetchone()

        self.assertEqual(row[0], "SUCCESS")
        self.assertIsNotNone(row[1])
        self.assertGreaterEqual(row[2], 0)
        self.assertEqual(row[3:10], (100, 95, 5, 30, 28, 3, 25))
        self.assertIsNone(row[10])
        self.assertEqual(json.loads(row[11]), ["일부 종목 누락"])

    def test_record_run_failure_updates_error_message(self) -> None:
        self.repo.record_run_start("2026-05-20")
        self.repo.record_run_failure(
            "2026-05-20",
            "DART API failure",
            stocks_collected=20,
            stocks_with_data=18,
            collection_errors=2,
            warnings=["재시도 초과"],
        )

        row = self.conn.execute(
            """
            SELECT status, completed_at, stocks_collected, stocks_with_data,
                   collection_errors, error_message, warnings
            FROM pipeline_runs
            WHERE run_date = ?
            """,
            ("2026-05-20",),
        ).fetchone()

        self.assertEqual(row[0], "FAILED")
        self.assertIsNotNone(row[1])
        self.assertEqual(row[2:5], (20, 18, 2))
        self.assertEqual(row[5], "DART API failure")
        self.assertEqual(json.loads(row[6]), ["재시도 초과"])

    def test_record_run_failure_can_create_row_without_start(self) -> None:
        self.repo.record_run_failure("2026-05-20", "early failure")

        row = self.conn.execute(
            """
            SELECT started_at, completed_at, status, error_message
            FROM pipeline_runs
            WHERE run_date = ?
            """,
            ("2026-05-20",),
        ).fetchone()

        self.assertIsNotNone(row[0])
        self.assertIsNotNone(row[1])
        self.assertEqual(row[2], "FAILED")
        self.assertEqual(row[3], "early failure")

    def test_upsert_scores_inserts_and_updates_rows(self) -> None:
        self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
        )

        inserted = self.repo.upsert_scores(
            [
                {
                    "stock_code": "005930",
                    "run_date": "2026-05-20",
                    "stage1_pass": 1,
                    "value_score": 80.0,
                    "composite_score": 75.0,
                    "final_rank": 2,
                }
            ]
        )
        updated = self.repo.upsert_scores(
            pd.DataFrame(
                [
                    {
                        "stock_code": "005930",
                        "run_date": "2026-05-20",
                        "stage1_pass": 1,
                        "value_score": 90.0,
                        "composite_score": 85.0,
                        "is_value_trap": 1,
                        "trap_flag_count": 2,
                        "final_rank": None,
                    }
                ]
            )
        )

        row = self.conn.execute(
            """
            SELECT COUNT(*), value_score, composite_score, is_value_trap,
                   trap_flag_count, final_rank
            FROM scores
            WHERE stock_code = ? AND run_date = ?
            """,
            ("005930", "2026-05-20"),
        ).fetchone()

        self.assertEqual(inserted, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 90.0)
        self.assertEqual(row[2], 85.0)
        self.assertEqual(row[3], 1)
        self.assertEqual(row[4], 2)
        self.assertIsNone(row[5])

    def test_upsert_rankings_inserts_and_updates_rows(self) -> None:
        self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
        )

        inserted = self.repo.upsert_rankings(
            [
                {
                    "run_date": "2026-05-20",
                    "rank": 2,
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "반도체",
                    "composite_score": 75.0,
                    "value_score": 80.0,
                    "risk_flag_count": 1,
                }
            ]
        )
        updated = self.repo.upsert_rankings(
            [
                {
                    "run_date": "2026-05-20",
                    "rank": 1,
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "반도체",
                    "composite_score": 88.0,
                    "value_score": 90.0,
                    "highest_severity": "LOW",
                }
            ]
        )

        row = self.conn.execute(
            """
            SELECT COUNT(*), rank, composite_score, value_score,
                   risk_flag_count, highest_severity
            FROM rankings
            WHERE stock_code = ? AND run_date = ?
            """,
            ("005930", "2026-05-20"),
        ).fetchone()

        self.assertEqual(inserted, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], 1)
        self.assertEqual(row[2], 88.0)
        self.assertEqual(row[3], 90.0)
        self.assertEqual(row[4], 0)
        self.assertEqual(row[5], "LOW")

    def test_upsert_risk_flags_replaces_flags_for_same_stock_and_run_date(self) -> None:
        self.repo.upsert_stocks(
            [{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}]
        )

        inserted = self.repo.upsert_risk_flags(
            [
                {
                    "stock_code": "005930",
                    "run_date": "2026-05-20",
                    "flag_type": "NEGATIVE_ROE",
                    "flag_description": "ROE 음수",
                    "severity": "HIGH",
                    "metric_value": -5.0,
                    "threshold_value": 0.0,
                },
                {
                    "stock_code": "005930",
                    "run_date": "2026-05-20",
                    "flag_type": "LOW_INTEREST_COVERAGE",
                    "severity": "MEDIUM",
                },
            ]
        )
        replaced = self.repo.upsert_risk_flags(
            pd.DataFrame(
                [
                    {
                        "stock_code": "005930",
                        "run_date": "2026-05-20",
                        "flag_type": "EXCESSIVE_DEBT",
                        "flag_description": "부채 과다",
                        "severity": "HIGH",
                        "metric_value": 350.0,
                        "threshold_value": 300.0,
                    }
                ]
            )
        )

        rows = self.conn.execute(
            """
            SELECT flag_type, severity, metric_value, threshold_value
            FROM risk_flags
            WHERE stock_code = ? AND run_date = ?
            """,
            ("005930", "2026-05-20"),
        ).fetchall()

        self.assertEqual(inserted, 2)
        self.assertEqual(replaced, 1)
        self.assertEqual(rows, [("EXCESSIVE_DEBT", "HIGH", 350.0, 300.0)])


if __name__ == "__main__":
    unittest.main()
