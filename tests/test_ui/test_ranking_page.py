"""랭킹 페이지 단위 테스트.

apply_filters / build_score_metrics 순수 함수를 검증한다.
Streamlit 렌더링은 호출하지 않는다.
"""
from __future__ import annotations

import sys
import types
import unittest

import pandas as pd

# ── Streamlit 모킹 ────────────────────────────────────────────────────────────
_mock_st = types.ModuleType("streamlit")
_mock_st.cache_resource = lambda **kw: (lambda f: f)
_mock_st.cache_data = lambda **kw: (lambda f: f)
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.pages.ranking import apply_filters, build_score_metrics  # noqa: E402

# ── 샘플 DataFrame ────────────────────────────────────────────────────────────

def _make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rank": [1, 2, 3, 4],
            "stock_code": ["005930", "000660", "035420", "086520"],
            "stock_name": ["삼성전자", "SK하이닉스", "NAVER", "에코프로"],
            "market": ["KOSPI", "KOSPI", "KOSPI", "KOSDAQ"],
            "sector": ["IT", "IT", "IT", "소재"],
            "composite_score": [82.5, 76.3, 70.1, 65.8],
            "value_score": [85.0, 78.0, 72.0, 70.0],
            "quality_score": [80.0, 75.0, 68.0, 60.0],
            "safety_score": [78.0, 72.0, 71.0, 55.0],
            "growth_score": [75.0, 70.0, 65.0, 75.0],
            "momentum_score": [70.0, 65.0, 60.0, 80.0],
            "market_cap_b": [400.0, 50.0, 30.0, 5.0],
            "per": [9.0, 11.0, 25.0, 60.0],
            "pbr": [1.2, 1.5, 3.0, 8.0],
            "roe": [18.0, 15.0, 10.0, 25.0],
            "dividend_yield": [2.5, 1.5, 0.5, 0.0],
            "risk_flag_count": [0, 1, 0, 2],
            "highest_severity": [None, "MEDIUM", None, "HIGH"],
        }
    )


# ── apply_filters 테스트 ──────────────────────────────────────────────────────

class ApplyFiltersMarketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()

    def test_no_filter_returns_all(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 4)

    def test_kospi_filter(self) -> None:
        result = apply_filters(self.df, market="KOSPI", sector=None, min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 3)
        self.assertTrue((result["market"] == "KOSPI").all())

    def test_kosdaq_filter(self) -> None:
        result = apply_filters(self.df, market="KOSDAQ", sector=None, min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["stock_code"], "086520")

    def test_unknown_market_returns_empty(self) -> None:
        result = apply_filters(self.df, market="KONEX", sector=None, min_score=0.0, max_risk_flags=10)
        self.assertTrue(result.empty)


class ApplyFiltersSectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()

    def test_sector_filter_it(self) -> None:
        result = apply_filters(self.df, market=None, sector="IT", min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 3)
        self.assertTrue((result["sector"] == "IT").all())

    def test_sector_filter_materials(self) -> None:
        result = apply_filters(self.df, market=None, sector="소재", min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 1)

    def test_none_sector_passes_all(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 4)


class ApplyFiltersScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()

    def test_min_score_filters_correctly(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=75.0, max_risk_flags=10)
        self.assertTrue((result["composite_score"] >= 75.0).all())
        self.assertEqual(len(result), 2)

    def test_min_score_100_returns_empty(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=100.0, max_risk_flags=10)
        self.assertTrue(result.empty)

    def test_min_score_0_returns_all(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 4)

    def test_boundary_score_included(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=82.5, max_risk_flags=10)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.iloc[0]["composite_score"], 82.5)


class ApplyFiltersRiskFlagsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()

    def test_max_risk_0_returns_clean_stocks(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=0.0, max_risk_flags=0)
        self.assertEqual(len(result), 2)
        self.assertTrue((result["risk_flag_count"] == 0).all())

    def test_max_risk_1_includes_medium(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=0.0, max_risk_flags=1)
        self.assertEqual(len(result), 3)

    def test_max_risk_10_returns_all(self) -> None:
        result = apply_filters(self.df, market=None, sector=None, min_score=0.0, max_risk_flags=10)
        self.assertEqual(len(result), 4)


class ApplyFiltersCombinedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()

    def test_market_and_score(self) -> None:
        result = apply_filters(self.df, market="KOSPI", sector=None, min_score=75.0, max_risk_flags=10)
        self.assertEqual(len(result), 2)
        self.assertTrue((result["market"] == "KOSPI").all())

    def test_all_filters_combined(self) -> None:
        result = apply_filters(self.df, market="KOSPI", sector="IT", min_score=75.0, max_risk_flags=0)
        # 삼성전자만 통과 (KOSPI, IT, 82.5>=75, risk_flag_count=0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["stock_code"], "005930")


# ── build_score_metrics 테스트 ───────────────────────────────────────────────

class BuildScoreMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()

    def test_empty_df_returns_zeros(self) -> None:
        result = build_score_metrics(pd.DataFrame())
        self.assertEqual(result["count"], 0.0)
        self.assertEqual(result["avg_composite"], 0.0)

    def test_count_matches_rows(self) -> None:
        result = build_score_metrics(self.df)
        self.assertEqual(result["count"], 4.0)

    def test_avg_composite_correct(self) -> None:
        result = build_score_metrics(self.df)
        expected = (82.5 + 76.3 + 70.1 + 65.8) / 4
        self.assertAlmostEqual(result["avg_composite"], expected, places=4)

    def test_avg_value_score_present(self) -> None:
        result = build_score_metrics(self.df)
        self.assertIn("avg_value_score", result)

    def test_avg_scores_all_present(self) -> None:
        result = build_score_metrics(self.df)
        for col in ["value_score", "quality_score", "safety_score", "growth_score", "momentum_score"]:
            self.assertIn(f"avg_{col}", result)

    def test_single_row_df(self) -> None:
        df_single = self.df.head(1)
        result = build_score_metrics(df_single)
        self.assertEqual(result["count"], 1.0)
        self.assertAlmostEqual(result["avg_composite"], 82.5)

    def test_filtered_subset(self) -> None:
        df_filtered = apply_filters(self.df, market="KOSDAQ", sector=None, min_score=0.0, max_risk_flags=10)
        result = build_score_metrics(df_filtered)
        self.assertEqual(result["count"], 1.0)
        self.assertAlmostEqual(result["avg_composite"], 65.8)


if __name__ == "__main__":
    unittest.main()
