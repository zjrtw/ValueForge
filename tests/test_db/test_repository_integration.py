import json
import sqlite3
import unittest

from src.db.repository import Repository


class RepositoryIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.repo = Repository(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_full_db_write_and_read_flow_uses_in_memory_sqlite(self) -> None:
        run_date = "2026-05-20"

        self.repo.record_run_start(run_date, pipeline_version="0.1.0")
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
                    "stock_name": "테스트바이오",
                    "market": "KOSDAQ",
                    "sector": "헬스케어",
                    "listing_date": "2022-01-01",
                },
            ]
        )
        self.repo.upsert_prices(
            [
                {
                    "stock_code": "005930",
                    "date": run_date,
                    "close": 70000,
                    "volume": 1_000_000,
                    "market_cap": 400_000,
                    "per": 10.5,
                    "pbr": 1.2,
                    "dividend_yield": 2.1,
                },
                {
                    "stock_code": "091990",
                    "date": run_date,
                    "close": 80000,
                    "volume": 500_000,
                    "market_cap": 50_000,
                    "per": 18.0,
                    "pbr": 2.0,
                    "dividend_yield": 0.0,
                },
            ]
        )
        self.repo.upsert_fundamentals(
            [
                {
                    "stock_code": "005930",
                    "fiscal_year": 2025,
                    "revenue": 300_000,
                    "operating_profit": 35_000,
                    "roe": 12.0,
                    "debt_to_equity": 35.0,
                },
                {
                    "stock_code": "091990",
                    "fiscal_year": 2025,
                    "revenue": 20_000,
                    "operating_profit": 1_000,
                    "roe": 7.0,
                    "debt_to_equity": 80.0,
                },
            ]
        )

        dataset = self.repo.get_screening_dataset(run_date=run_date)
        self.assertEqual(set(dataset["stock_code"].tolist()), {"005930", "091990"})
        self.assertEqual(dataset.loc[dataset["stock_code"] == "005930", "roe"].item(), 12.0)

        self.repo.upsert_scores(
            [
                {
                    "stock_code": "005930",
                    "run_date": run_date,
                    "stage1_pass": 1,
                    "value_score": 80.0,
                    "quality_score": 75.0,
                    "safety_score": 85.0,
                    "growth_score": 70.0,
                    "momentum_score": 60.0,
                    "composite_score": 76.5,
                    "final_rank": 1,
                },
                {
                    "stock_code": "091990",
                    "run_date": run_date,
                    "stage1_pass": 1,
                    "value_score": 60.0,
                    "composite_score": 62.0,
                    "is_value_trap": 1,
                    "trap_flag_count": 1,
                },
            ]
        )
        self.repo.upsert_risk_flags(
            [
                {
                    "stock_code": "091990",
                    "run_date": run_date,
                    "flag_type": "LOW_INTEREST_COVERAGE",
                    "flag_description": "이자보상배율 낮음",
                    "severity": "MEDIUM",
                    "metric_value": 1.2,
                    "threshold_value": 1.5,
                }
            ]
        )
        self.repo.upsert_rankings(
            [
                {
                    "run_date": run_date,
                    "rank": 1,
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "반도체",
                    "composite_score": 76.5,
                    "value_score": 80.0,
                    "quality_score": 75.0,
                    "safety_score": 85.0,
                    "growth_score": 70.0,
                    "momentum_score": 60.0,
                    "market_cap_b": 400_000,
                    "per": 10.5,
                    "pbr": 1.2,
                    "roe": 12.0,
                    "dividend_yield": 2.1,
                    "debt_to_equity": 35.0,
                    "risk_flag_count": 0,
                }
            ]
        )
        self.repo.record_run_success(
            run_date,
            stocks_collected=2,
            stocks_with_data=2,
            stage1_pass_count=2,
            stage2_score_count=2,
            stage3_trap_count=1,
            final_candidates=1,
            warnings=["테스트 경고"],
        )

        ranking = self.conn.execute(
            "SELECT rank, stock_code, composite_score FROM rankings WHERE run_date = ?",
            (run_date,),
        ).fetchone()
        flag = self.conn.execute(
            "SELECT flag_type, severity FROM risk_flags WHERE stock_code = ?",
            ("091990",),
        ).fetchone()
        run = self.conn.execute(
            """
            SELECT status, stocks_collected, stocks_with_data, stage1_pass_count,
                   stage2_score_count, stage3_trap_count, final_candidates, warnings
            FROM pipeline_runs
            WHERE run_date = ?
            """,
            (run_date,),
        ).fetchone()

        self.assertEqual(ranking, (1, "005930", 76.5))
        self.assertEqual(flag, ("LOW_INTEREST_COVERAGE", "MEDIUM"))
        self.assertEqual(run[:7], ("SUCCESS", 2, 2, 2, 2, 1, 1))
        self.assertEqual(json.loads(run[7]), ["테스트 경고"])


if __name__ == "__main__":
    unittest.main()
