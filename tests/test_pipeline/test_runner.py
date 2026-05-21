"""파이프라인 러너 단위 테스트.

실제 API·R2 호출 없이 pytest-mock으로 의존성을 모킹한다.
"""
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.pipeline.runner import (
    _build_rankings_df,
    _build_risk_flags,
    _build_scores_df,
    _enrich_multiyear,
    _highest_severity,
    _resolve_date,
    run_pipeline,
)
from src.screening.stage3_trap_detector import FLAG_SPECS

_RUN_DATE = date(2025, 1, 20)

# ── 합성 데이터 ─────────────────────────────────────────────────────────────

_TICKERS = pd.DataFrame([
    {"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"},
    {"stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI"},
])

_PRICES = pd.DataFrame([
    {"stock_code": "005930", "date": "2025-01-20", "close": 70000.0,
     "market_cap": 5e9, "per": 12.0, "pbr": 1.5, "dividend_yield": 2.0},
    {"stock_code": "000660", "date": "2025-01-20", "close": 180000.0,
     "market_cap": 4e9, "per": 10.0, "pbr": 1.2, "dividend_yield": 1.5},
])

_AVG_VOL = pd.DataFrame([
    {"stock_code": "005930", "avg_trading_value_20d": 1e9},
    {"stock_code": "000660", "avg_trading_value_20d": 8e8},
])

_FUNDAMENTALS = pd.DataFrame([
    {"stock_code": "005930", "fiscal_year": 2024, "fiscal_quarter": 0,
     "revenue": 300e6, "operating_profit": 30e6, "total_equity": 50e6,
     "roe": 15.0, "roa": 8.0, "debt_to_equity": 1.0, "current_ratio": 2.0,
     "interest_coverage": 8.0, "free_cash_flow": 20e6, "operating_margin": 0.10},
    {"stock_code": "000660", "fiscal_year": 2024, "fiscal_quarter": 0,
     "revenue": 200e6, "operating_profit": 25e6, "total_equity": 40e6,
     "roe": 12.0, "roa": 6.0, "debt_to_equity": 0.8, "current_ratio": 1.8,
     "interest_coverage": 6.0, "free_cash_flow": 15e6, "operating_margin": 0.12},
])

_SCREENING_DATASET = pd.DataFrame([
    {
        "stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI",
        "is_active": 1, "listing_days": 1000,
        "market_cap": 5e9, "per": 12.0, "pbr": 1.5, "dividend_yield": 2.0,
        "avg_trading_value_20d": 1e9,
        "total_equity": 50e6, "roe": 15.0, "roa": 8.0,
        "operating_margin": 0.10, "debt_to_equity": 1.0, "current_ratio": 2.0,
        "interest_coverage": 8.0, "ebitda": 35e6, "total_debt": 20e6,
        "cash_and_equiv": 10e6, "operating_profit": 30e6, "eps": 5000.0,
        "free_cash_flow": 20e6, "revenue": 300e6, "capex": 15e6,
        "return_6m": 0.08, "return_3m": 0.04, "return_1m": 0.02,
        "industry": "반도체", "fiscal_year": 2024,
    },
    {
        "stock_code": "000660", "stock_name": "SK하이닉스", "market": "KOSPI",
        "is_active": 1, "listing_days": 800,
        "market_cap": 4e9, "per": 10.0, "pbr": 1.2, "dividend_yield": 1.5,
        "avg_trading_value_20d": 8e8,
        "total_equity": 40e6, "roe": 12.0, "roa": 6.0,
        "operating_margin": 0.12, "debt_to_equity": 0.8, "current_ratio": 1.8,
        "interest_coverage": 6.0, "ebitda": 28e6, "total_debt": 15e6,
        "cash_and_equiv": 8e6, "operating_profit": 25e6, "eps": 4000.0,
        "free_cash_flow": 15e6, "revenue": 200e6, "capex": 10e6,
        "return_6m": 0.06, "return_3m": 0.03, "return_1m": 0.01,
        "industry": "반도체", "fiscal_year": 2024,
    },
])


def _patch_collectors():
    """수집기 의존성 패치 컨텍스트 관리자."""
    patches = [
        patch("src.pipeline.runner.fetch_ticker_list", return_value=_TICKERS),
        patch("src.pipeline.runner.fetch_daily_price_data", return_value=_PRICES),
        patch("src.pipeline.runner.fetch_avg_trading_value_20d", return_value=_AVG_VOL),
        patch("src.pipeline.runner.fetch_financial_statements", return_value=_FUNDAMENTALS),
        patch("src.pipeline.runner.R2Uploader"),
    ]
    return patches


class ResolveDateTest(unittest.TestCase):
    def test_today_resolves_to_today(self) -> None:
        result = _resolve_date("today")
        self.assertEqual(result, date.today())

    def test_none_resolves_to_today(self) -> None:
        result = _resolve_date(None)
        self.assertEqual(result, date.today())

    def test_iso_date_string(self) -> None:
        result = _resolve_date("2025-01-20")
        self.assertEqual(result, date(2025, 1, 20))


class BuildScoresDfTest(unittest.TestCase):
    def _make_stage3(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "stock_code": "005930",
            "composite_score": 75.0,
            "value_score": 80.0,
            "quality_score": 70.0,
            "safety_score": 75.0,
            "growth_score": 65.0,
            "momentum_score": 60.0,
            "is_value_trap": False,
            "critical_flag_count": 0,
            "high_flag_count": 0,
            "medium_flag_count": 1,
            "low_flag_count": 0,
            "risk_flags": "DECLINING_REVENUE",
        }])

    def _make_ranked(self) -> pd.DataFrame:
        return pd.DataFrame([{"stock_code": "005930", "final_rank": 1}])

    def test_adds_run_date(self) -> None:
        result = _build_scores_df(self._make_stage3(), self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["run_date"], "2025-01-20")

    def test_stage1_pass_is_one(self) -> None:
        result = _build_scores_df(self._make_stage3(), self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["stage1_pass"], 1)

    def test_trap_flag_count_summed(self) -> None:
        result = _build_scores_df(self._make_stage3(), self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["trap_flag_count"], 1)

    def test_final_rank_mapped_from_stage4(self) -> None:
        result = _build_scores_df(self._make_stage3(), self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["final_rank"], 1)

    def test_trap_has_null_final_rank(self) -> None:
        stage3 = self._make_stage3()
        stage3.iloc[0, stage3.columns.get_loc("is_value_trap")] = True
        result = _build_scores_df(stage3, pd.DataFrame(columns=["stock_code", "final_rank"]), "2025-01-20")
        self.assertTrue(pd.isna(result.iloc[0]["final_rank"]))


class BuildRiskFlagsTest(unittest.TestCase):
    def test_empty_flags_produces_no_rows(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930", "risk_flags": ""}])
        result = _build_risk_flags(df, "2025-01-20")
        self.assertEqual(result, [])

    def test_single_flag_produces_one_row(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930", "risk_flags": "EXCESSIVE_DEBT"}])
        result = _build_risk_flags(df, "2025-01-20")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["flag_type"], "EXCESSIVE_DEBT")
        self.assertEqual(result[0]["stock_code"], "005930")
        self.assertEqual(result[0]["run_date"], "2025-01-20")

    def test_multiple_flags_produce_multiple_rows(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930", "risk_flags": "NEGATIVE_ROE,EXCESSIVE_DEBT"}])
        result = _build_risk_flags(df, "2025-01-20")
        self.assertEqual(len(result), 2)
        types = {r["flag_type"] for r in result}
        self.assertIn("NEGATIVE_ROE", types)
        self.assertIn("EXCESSIVE_DEBT", types)

    def test_severity_from_flag_spec(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930", "risk_flags": "NEGATIVE_EQUITY"}])
        result = _build_risk_flags(df, "2025-01-20")
        self.assertEqual(result[0]["severity"], "CRITICAL")

    def test_unknown_flag_name_skipped(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930", "risk_flags": "UNKNOWN_FLAG"}])
        result = _build_risk_flags(df, "2025-01-20")
        self.assertEqual(result, [])


class BuildRankingsDfTest(unittest.TestCase):
    def _make_ranked(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "market": "KOSPI",
            "final_rank": 1,
            "composite_score": 75.0,
            "value_score": 80.0,
            "quality_score": 70.0,
            "safety_score": 75.0,
            "growth_score": 65.0,
            "momentum_score": 60.0,
            "market_cap": 5e9,
            "critical_flag_count": 0,
            "high_flag_count": 0,
            "medium_flag_count": 1,
            "low_flag_count": 0,
        }])

    def test_adds_run_date(self) -> None:
        result = _build_rankings_df(self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["run_date"], "2025-01-20")

    def test_rank_equals_final_rank(self) -> None:
        result = _build_rankings_df(self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["rank"], 1)

    def test_market_cap_b_converted(self) -> None:
        result = _build_rankings_df(self._make_ranked(), "2025-01-20")
        self.assertAlmostEqual(result.iloc[0]["market_cap_b"], 5.0)

    def test_risk_flag_count_summed(self) -> None:
        result = _build_rankings_df(self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["risk_flag_count"], 1)

    def test_highest_severity_medium(self) -> None:
        result = _build_rankings_df(self._make_ranked(), "2025-01-20")
        self.assertEqual(result.iloc[0]["highest_severity"], "MEDIUM")

    def test_highest_severity_none_when_no_flags(self) -> None:
        ranked = self._make_ranked()
        ranked.iloc[0, ranked.columns.get_loc("medium_flag_count")] = 0
        result = _build_rankings_df(ranked, "2025-01-20")
        self.assertIsNone(result.iloc[0]["highest_severity"])


class HighestSeverityTest(unittest.TestCase):
    def _row(self, c=0, h=0, m=0, lo=0) -> pd.Series:
        return pd.Series({
            "critical_flag_count": c, "high_flag_count": h,
            "medium_flag_count": m, "low_flag_count": lo,
        })

    def test_critical_takes_precedence(self) -> None:
        self.assertEqual(_highest_severity(self._row(c=1, h=1, m=1, lo=1)), "CRITICAL")

    def test_high_when_no_critical(self) -> None:
        self.assertEqual(_highest_severity(self._row(h=1, m=1)), "HIGH")

    def test_medium_when_no_high(self) -> None:
        self.assertEqual(_highest_severity(self._row(m=2)), "MEDIUM")

    def test_low_when_only_low(self) -> None:
        self.assertEqual(_highest_severity(self._row(lo=1)), "LOW")

    def test_none_when_no_flags(self) -> None:
        self.assertIsNone(_highest_severity(self._row()))


class EnrichMultiyearTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE fundamentals (
                stock_code TEXT, fiscal_year INTEGER, fiscal_quarter INTEGER,
                operating_profit REAL, free_cash_flow REAL, operating_margin REAL
            )
        """)
        rows = [
            ("005930", 2024, 0, 30e6, 20e6, 0.10),
            ("005930", 2023, 0, 25e6, 15e6, 0.08),
            ("005930", 2022, 0, 20e6, 12e6, 0.07),
        ]
        self.conn.executemany(
            "INSERT INTO fundamentals VALUES (?,?,?,?,?,?)", rows
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_adds_yr1_yr2_yr3_columns(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930"}])
        result = _enrich_multiyear(df, self.conn)
        for col in ("op_profit_yr1", "op_profit_yr2", "op_profit_yr3"):
            self.assertIn(col, result.columns, f"컬럼 누락: {col}")

    def test_yr1_is_most_recent(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930"}])
        result = _enrich_multiyear(df, self.conn)
        self.assertAlmostEqual(result.iloc[0]["op_profit_yr1"], 30e6)

    def test_yr3_is_oldest(self) -> None:
        df = pd.DataFrame([{"stock_code": "005930"}])
        result = _enrich_multiyear(df, self.conn)
        self.assertAlmostEqual(result.iloc[0]["op_profit_yr3"], 20e6)

    def test_empty_fundamentals_returns_original(self) -> None:
        empty_conn = sqlite3.connect(":memory:")
        empty_conn.execute("""
            CREATE TABLE fundamentals (
                stock_code TEXT, fiscal_year INTEGER, fiscal_quarter INTEGER,
                operating_profit REAL, free_cash_flow REAL, operating_margin REAL
            )
        """)
        df = pd.DataFrame([{"stock_code": "005930"}])
        result = _enrich_multiyear(df, empty_conn)
        self.assertEqual(list(result.columns), list(df.columns))
        empty_conn.close()


class RunPipelineTest(unittest.TestCase):
    def _apply_patches(self, mock_uploader):
        mock_uploader.return_value = MagicMock()

    def test_returns_stats_dict(self) -> None:
        patches = _patch_collectors()
        started = [p.start() for p in patches]
        mock_uploader = started[-1]
        mock_uploader.return_value = MagicMock()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "test.db"

                # Patch get_screening_dataset to return synthetic data
                with patch(
                    "src.pipeline.runner.Repository.get_screening_dataset",
                    return_value=_SCREENING_DATASET,
                ):
                    stats = run_pipeline(
                        _RUN_DATE,
                        db_path=db_path,
                        upload=False,
                    )

            self.assertIsInstance(stats, dict)
            self.assertIn("stocks_collected", stats)
            self.assertIn("final_candidates", stats)
        finally:
            for p in patches:
                p.stop()

    def test_no_upload_flag_skips_r2(self) -> None:
        patches = _patch_collectors()
        started = [p.start() for p in patches]
        mock_uploader_cls = started[-1]

        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "test.db"
                with patch(
                    "src.pipeline.runner.Repository.get_screening_dataset",
                    return_value=_SCREENING_DATASET,
                ):
                    run_pipeline(_RUN_DATE, db_path=db_path, upload=False)

            mock_uploader_cls.return_value.upload_backup.assert_not_called()
        finally:
            for p in patches:
                p.stop()

    def test_records_run_success_on_completion(self) -> None:
        patches = _patch_collectors()
        started = [p.start() for p in patches]
        started[-1].return_value = MagicMock()

        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "test.db"
                with patch(
                    "src.pipeline.runner.Repository.get_screening_dataset",
                    return_value=_SCREENING_DATASET,
                ):
                    run_pipeline(_RUN_DATE, db_path=db_path, upload=False)

                # DB는 tempdir 내에서 확인해야 함
                conn = sqlite3.connect(str(db_path))
                row = conn.execute(
                    "SELECT status FROM pipeline_runs WHERE run_date = ?",
                    (_RUN_DATE.isoformat(),),
                ).fetchone()
                conn.close()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "SUCCESS")
        finally:
            for p in patches:
                p.stop()

    def test_records_run_failure_on_exception(self) -> None:
        patches = _patch_collectors()
        started = [p.start() for p in patches]
        started[-1].return_value = MagicMock()
        # Stage1 filter 강제 실패
        started[0].side_effect = RuntimeError("collect failed")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "test.db"
                with self.assertRaises(RuntimeError):
                    run_pipeline(_RUN_DATE, db_path=db_path, upload=False)

                # DB는 tempdir 내에서 확인해야 함
                conn = sqlite3.connect(str(db_path))
                row = conn.execute(
                    "SELECT status FROM pipeline_runs WHERE run_date = ?",
                    (_RUN_DATE.isoformat(),),
                ).fetchone()
                conn.close()
                self.assertEqual(row[0], "FAILED")
        finally:
            for p in patches:
                p.stop()


if __name__ == "__main__":
    unittest.main()
