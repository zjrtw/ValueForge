"""End-to-End 파이프라인 테스트.

외부 API(pykrx, DART)는 모킹하고 SQLite 쓰기·스크리닝·R2 업로드를
실제로 실행해 전체 파이프라인이 올바르게 동작하는지 검증한다.

검증 항목:
- 모든 DB 테이블 데이터 존재 (stocks, prices, fundamentals, scores, rankings, risk_flags, pipeline_runs)
- Stage 1 통과/실패 분류 정확성
- Stage 3 가치 함정 3종 감지
- Stage 4 랭킹 및 최종 후보 수
- R2 업로드 후 3개 파일 생성 (latest.db, latest_metadata.json, history/YYYY-MM-DD.db)
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
import pandas as pd
from freezegun import freeze_time
from moto import mock_aws

from src.pipeline.runner import run_pipeline

# ── 합성 유니버스 설계 ────────────────────────────────────────────────────────
_RUN_DATE = date(2025, 1, 20)

_N_GOOD = 25          # Stage 1 통과 + Stage 3 통과
_N_TRAPS = 3          # Stage 1 통과 + Stage 3 탈락
_N_STAGE1_FAIL = 2    # Stage 1 실패

_GOOD_CODES = [str(i + 1).zfill(6) for i in range(_N_GOOD)]
_TRAP_CODES = ["900001", "900002", "900003"]
_FAIL_CODES = ["800001", "800002"]
_ALL_CODES = _GOOD_CODES + _TRAP_CODES + _FAIL_CODES

_LISTING_DATE = "2020-01-01"   # 5년 전 → listing_days ≈ 1826 > 365
_BUCKET = "valueforge"


# ── 합성 데이터 팩토리 ────────────────────────────────────────────────────────

def _tickers() -> pd.DataFrame:
    return pd.DataFrame([
        {"stock_code": c, "stock_name": f"종목{c}", "market": "KOSPI",
         "listing_date": _LISTING_DATE, "sector": "제조", "industry": "반도체"}
        for c in _ALL_CODES
    ])


def _prices() -> pd.DataFrame:
    rows = []
    for c in _GOOD_CODES + _TRAP_CODES:
        rows.append({
            "stock_code": c, "date": "2025-01-20",
            "close": 50_000.0, "open": 49_000.0, "high": 51_000.0, "low": 48_000.0,
            "volume": 100_000, "trading_value": 5_000_000_000,
            "market_cap": 5_000_000_000,   # 50억 → Stage1 통과 (≥30억)
            "per": 12.0, "pbr": 1.5, "dividend_yield": 2.0,
            "market": "KOSPI",
        })
    for c in _FAIL_CODES:
        rows.append({
            "stock_code": c, "date": "2025-01-20",
            "close": 5_000.0, "open": 4_800.0, "high": 5_100.0, "low": 4_700.0,
            "volume": 1_000, "trading_value": 5_000_000,
            "market_cap": 1_000_000_000,   # 10억 → Stage1 실패 (<30억)
            "per": 12.0, "pbr": 1.5, "dividend_yield": 1.0,
            "market": "KOSPI",
        })
    return pd.DataFrame(rows)


def _base_fundamental(code: str, year: int, **overrides) -> dict:
    base = {
        "stock_code": code, "fiscal_year": year, "fiscal_quarter": 0,
        "revenue": 300_000, "gross_profit": 90_000,
        "operating_profit": 50_000, "ebitda": 70_000, "net_profit": 40_000,
        "total_assets": 500_000, "current_assets": 200_000, "cash_and_equiv": 50_000,
        "total_liabilities": 250_000, "current_liabilities": 100_000, "total_equity": 250_000,
        "total_debt": 150_000, "operating_cf": 60_000,
        "capex": 20_000, "free_cash_flow": 40_000,
        "eps": 2_000.0, "bps": 15_000.0, "dps": 500.0,
        "roe": 15.0, "roa": 8.0, "gross_margin": 0.30,
        "operating_margin": 0.17, "net_margin": 0.13,
        "debt_to_equity": 1.0, "current_ratio": 2.0, "interest_coverage": 8.0,
        "data_source": "dart",
    }
    base.update(overrides)
    return base


def _fundamentals() -> pd.DataFrame:
    rows = []

    # 정상 종목: 3년치 (Stage 3 함정 없음)
    for code in _GOOD_CODES:
        for year in [2022, 2023, 2024]:
            rows.append(_base_fundamental(code, year))

    # 함정 ①: 자기자본 음수 (CRITICAL — NEGATIVE_EQUITY)
    rows.append(_base_fundamental("900001", 2024, total_equity=-100_000))

    # 함정 ②: 2년 연속 영업손실 (CRITICAL — PERSISTENT_OPERATING_LOSS)
    rows.append(_base_fundamental("900002", 2023, operating_profit=-30_000))
    rows.append(_base_fundamental("900002", 2024, operating_profit=-50_000))

    # 함정 ③: ROE 음수 + 부채비율 초과 (HIGH×2 — NEGATIVE_ROE + EXCESSIVE_DEBT)
    rows.append(_base_fundamental("900003", 2024, roe=-8.0, debt_to_equity=3.5))

    # Stage 1 실패 종목도 수집된 것으로 처리
    for code in _FAIL_CODES:
        rows.append(_base_fundamental(code, 2024))

    return pd.DataFrame(rows)


# ── 파이프라인 실행 픽스처 ─────────────────────────────────────────────────────

def _run_pipeline_no_upload(db_path: Path) -> dict:
    """외부 API를 모킹하고 upload=False로 파이프라인을 실행한다."""
    with (
        patch("src.pipeline.runner.fetch_ticker_list", return_value=_tickers()),
        patch("src.pipeline.runner.fetch_stock_listing_info", return_value=pd.DataFrame()),
        patch("src.pipeline.runner.fetch_daily_price_data", return_value=_prices()),
        patch("src.pipeline.runner.fetch_financial_statements", return_value=_fundamentals()),
    ):
        return run_pipeline(_RUN_DATE, db_path=db_path, upload=False)


# ── DB 검증 헬퍼 ───────────────────────────────────────────────────────────────

def _query(db_path: Path, sql: str, params=()) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


# ── 테스트 클래스 ──────────────────────────────────────────────────────────────

class E2ENoUploadTest(unittest.TestCase):
    """upload=False E2E: DB 테이블과 파이프라인 통계를 검증."""

    _db_path: Path
    _tmp_dir: tempfile.TemporaryDirectory
    _stats: dict

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "e2e_test.db"
        cls._stats = _run_pipeline_no_upload(cls._db_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp_dir.cleanup()

    # ── pipeline_runs ───────────────────────────────────────────────────────

    def test_pipeline_run_recorded_as_success(self) -> None:
        rows = _query(self._db_path, "SELECT status FROM pipeline_runs WHERE run_date = ?",
                      (_RUN_DATE.isoformat(),))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "SUCCESS")

    def test_pipeline_stats_stocks_collected(self) -> None:
        self.assertEqual(self._stats["stocks_collected"], len(_ALL_CODES))

    def test_pipeline_stats_stage1_pass(self) -> None:
        # 25 good + 3 traps = 28 pass Stage 1
        self.assertEqual(self._stats["stage1_pass_count"], _N_GOOD + _N_TRAPS)

    def test_pipeline_stats_trap_count(self) -> None:
        self.assertEqual(self._stats["stage3_trap_count"], _N_TRAPS)

    def test_pipeline_stats_final_candidates(self) -> None:
        self.assertEqual(self._stats["final_candidates"], _N_GOOD)

    # ── stocks 테이블 ────────────────────────────────────────────────────────

    def test_stocks_table_has_all_tickers(self) -> None:
        count = _query(self._db_path, "SELECT COUNT(*) FROM stocks")[0][0]
        self.assertEqual(count, len(_ALL_CODES))

    # ── prices 테이블 ────────────────────────────────────────────────────────

    def test_prices_table_populated(self) -> None:
        count = _query(self._db_path, "SELECT COUNT(*) FROM prices")[0][0]
        self.assertGreater(count, 0)

    def test_prices_stage1_pass_stocks_stored(self) -> None:
        rows = _query(
            self._db_path,
            f"SELECT stock_code FROM prices WHERE stock_code IN ({','.join('?'*len(_GOOD_CODES))})",
            _GOOD_CODES,
        )
        self.assertEqual(len(rows), _N_GOOD)

    # ── fundamentals 테이블 ──────────────────────────────────────────────────

    def test_fundamentals_table_populated(self) -> None:
        count = _query(self._db_path, "SELECT COUNT(*) FROM fundamentals")[0][0]
        self.assertGreater(count, 0)

    def test_good_stocks_have_3_years_of_fundamentals(self) -> None:
        code = _GOOD_CODES[0]
        count = _query(
            self._db_path,
            "SELECT COUNT(*) FROM fundamentals WHERE stock_code = ? AND fiscal_quarter = 0",
            (code,),
        )[0][0]
        self.assertEqual(count, 3)

    # ── scores 테이블 ────────────────────────────────────────────────────────

    def test_scores_table_has_stage1_pass_rows(self) -> None:
        count = _query(
            self._db_path,
            "SELECT COUNT(*) FROM scores WHERE run_date = ? AND stage1_pass = 1",
            (_RUN_DATE.isoformat(),),
        )[0][0]
        self.assertEqual(count, _N_GOOD + _N_TRAPS)

    def test_trap_stocks_marked_in_scores(self) -> None:
        for code in _TRAP_CODES:
            rows = _query(
                self._db_path,
                "SELECT is_value_trap FROM scores WHERE stock_code = ? AND run_date = ?",
                (code, _RUN_DATE.isoformat()),
            )
            self.assertEqual(len(rows), 1, f"scores row missing for {code}")
            self.assertEqual(rows[0][0], 1, f"{code} not marked as trap")

    def test_good_stocks_not_marked_as_traps(self) -> None:
        code = _GOOD_CODES[0]
        rows = _query(
            self._db_path,
            "SELECT is_value_trap FROM scores WHERE stock_code = ? AND run_date = ?",
            (code, _RUN_DATE.isoformat()),
        )
        self.assertEqual(rows[0][0], 0)

    def test_good_stocks_have_final_rank(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT COUNT(*) FROM scores WHERE run_date = ? AND final_rank IS NOT NULL",
            (_RUN_DATE.isoformat(),),
        )
        self.assertEqual(rows[0][0], _N_GOOD)

    def test_trap_stocks_have_null_final_rank(self) -> None:
        for code in _TRAP_CODES:
            rows = _query(
                self._db_path,
                "SELECT final_rank FROM scores WHERE stock_code = ? AND run_date = ?",
                (code, _RUN_DATE.isoformat()),
            )
            self.assertIsNone(rows[0][0], f"{code} should have null final_rank")

    def test_scores_have_composite_score(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT MIN(composite_score), MAX(composite_score) FROM scores "
            "WHERE run_date = ? AND stage1_pass = 1",
            (_RUN_DATE.isoformat(),),
        )
        min_score, max_score = rows[0]
        self.assertIsNotNone(min_score)
        self.assertGreaterEqual(min_score, 0)
        self.assertLessEqual(max_score, 100)

    # ── risk_flags 테이블 ────────────────────────────────────────────────────

    def test_risk_flags_table_populated(self) -> None:
        count = _query(
            self._db_path,
            "SELECT COUNT(*) FROM risk_flags WHERE run_date = ?",
            (_RUN_DATE.isoformat(),),
        )[0][0]
        self.assertGreater(count, 0)

    def test_trap1_has_negative_equity_flag(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT flag_type FROM risk_flags WHERE stock_code = ? AND run_date = ?",
            ("900001", _RUN_DATE.isoformat()),
        )
        flag_types = {r[0] for r in rows}
        self.assertIn("NEGATIVE_EQUITY", flag_types)

    def test_trap2_has_persistent_loss_flag(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT flag_type FROM risk_flags WHERE stock_code = ? AND run_date = ?",
            ("900002", _RUN_DATE.isoformat()),
        )
        flag_types = {r[0] for r in rows}
        self.assertIn("PERSISTENT_OPERATING_LOSS", flag_types)

    def test_trap3_has_two_high_flags(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT flag_type, severity FROM risk_flags WHERE stock_code = ? AND run_date = ?",
            ("900003", _RUN_DATE.isoformat()),
        )
        high_flags = [r for r in rows if r[1] == "HIGH"]
        self.assertGreaterEqual(len(high_flags), 2)

    def test_good_stocks_have_no_critical_flags(self) -> None:
        placeholders = ",".join("?" * _N_GOOD)
        rows = _query(
            self._db_path,
            f"SELECT COUNT(*) FROM risk_flags WHERE stock_code IN ({placeholders}) "
            f"AND run_date = ? AND severity = 'CRITICAL'",
            _GOOD_CODES + [_RUN_DATE.isoformat()],
        )
        self.assertEqual(rows[0][0], 0)

    # ── rankings 테이블 ──────────────────────────────────────────────────────

    def test_rankings_table_has_final_candidates(self) -> None:
        count = _query(
            self._db_path,
            "SELECT COUNT(*) FROM rankings WHERE run_date = ?",
            (_RUN_DATE.isoformat(),),
        )[0][0]
        self.assertEqual(count, _N_GOOD)

    def test_rankings_rank_starts_at_1(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT MIN(rank) FROM rankings WHERE run_date = ?",
            (_RUN_DATE.isoformat(),),
        )
        self.assertEqual(rows[0][0], 1)

    def test_rankings_sorted_by_score(self) -> None:
        rows = _query(
            self._db_path,
            "SELECT rank, composite_score FROM rankings WHERE run_date = ? ORDER BY rank ASC",
            (_RUN_DATE.isoformat(),),
        )
        scores = [r[1] for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_trap_stocks_not_in_rankings(self) -> None:
        placeholders = ",".join("?" * _N_TRAPS)
        rows = _query(
            self._db_path,
            f"SELECT COUNT(*) FROM rankings WHERE stock_code IN ({placeholders}) AND run_date = ?",
            _TRAP_CODES + [_RUN_DATE.isoformat()],
        )
        self.assertEqual(rows[0][0], 0)


@mock_aws
class E2EWithUploadTest(unittest.TestCase):
    """upload=True E2E: R2에 3개 파일 생성 검증."""

    def setUp(self) -> None:
        self._s3_client = boto3.client("s3", region_name="us-east-1")
        self._s3_client.create_bucket(Bucket=_BUCKET)
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "e2e_upload.db"

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    @freeze_time("2025-01-20")
    def _run_with_mocked_r2(self) -> dict:
        mocked_client = self._s3_client

        def _get_mocked_uploader(*args, **kwargs):
            from src.storage.uploader import R2Uploader
            return R2Uploader(client=mocked_client, bucket=_BUCKET)

        with (
            patch("src.pipeline.runner.fetch_ticker_list", return_value=_tickers()),
            patch("src.pipeline.runner.fetch_stock_listing_info", return_value=pd.DataFrame()),
            patch("src.pipeline.runner.fetch_daily_price_data", return_value=_prices()),
            patch("src.pipeline.runner.fetch_financial_statements", return_value=_fundamentals()),
            patch("src.pipeline.runner.R2Uploader", side_effect=_get_mocked_uploader),
        ):
            return run_pipeline(_RUN_DATE, db_path=self._db_path, upload=True)

    def _list_keys(self) -> list[str]:
        resp = self._s3_client.list_objects_v2(Bucket=_BUCKET)
        return [o["Key"] for o in resp.get("Contents", [])]

    def test_latest_db_uploaded(self) -> None:
        self._run_with_mocked_r2()
        self.assertIn("latest.db", self._list_keys())

    def test_history_backup_uploaded(self) -> None:
        self._run_with_mocked_r2()
        expected_key = f"history/{_RUN_DATE.isoformat()}.db"
        self.assertIn(expected_key, self._list_keys())

    def test_metadata_json_uploaded(self) -> None:
        self._run_with_mocked_r2()
        self.assertIn("latest_metadata.json", self._list_keys())

    def test_all_three_files_present(self) -> None:
        self._run_with_mocked_r2()
        keys = self._list_keys()
        self.assertIn("latest.db", keys)
        self.assertIn(f"history/{_RUN_DATE.isoformat()}.db", keys)
        self.assertIn("latest_metadata.json", keys)

    def test_metadata_json_is_valid(self) -> None:
        self._run_with_mocked_r2()
        resp = self._s3_client.get_object(Bucket=_BUCKET, Key="latest_metadata.json")
        meta = json.loads(resp["Body"].read())
        self.assertEqual(meta["run_date"], _RUN_DATE.isoformat())
        self.assertIn("final_candidates", meta)
        self.assertIn("top_candidates", meta)
        self.assertEqual(meta["final_candidates"], _N_GOOD)

    def test_latest_db_is_non_empty(self) -> None:
        self._run_with_mocked_r2()
        resp = self._s3_client.get_object(Bucket=_BUCKET, Key="latest.db")
        content = resp["Body"].read()
        self.assertGreater(len(content), 0)
        self.assertTrue(content[:16].startswith(b"SQLite format 3"))


if __name__ == "__main__":
    unittest.main()
