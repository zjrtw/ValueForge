"""종목 상세 페이지 단위 테스트.

build_radar_data / format_fundamentals / format_risk_flags 순수 함수를 검증한다.
Streamlit / Plotly 렌더링은 호출하지 않는다.
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

from src.ui.pages.detail import (  # noqa: E402
    build_radar_data,
    format_fundamentals,
    format_risk_flags,
)

# ── 샘플 데이터 ───────────────────────────────────────────────────────────────

def _scores_row() -> pd.Series:
    return pd.Series(
        {
            "stock_code": "005930",
            "run_date": "2025-01-20",
            "composite_score": 82.5,
            "value_score": 85.0,
            "quality_score": 80.0,
            "safety_score": 78.0,
            "growth_score": 75.0,
            "momentum_score": 70.0,
            "stage1_pass": 1,
            "is_value_trap": 0,
            "final_rank": 1,
        }
    )


def _flags_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stock_code": ["000660", "000660"],
            "run_date": ["2025-01-20", "2025-01-20"],
            "flag_type": ["DECLINING_REVENUE", "HIGH_DEBT"],
            "flag_description": ["매출 YoY 5% 이상 감소", "부채비율 300% 초과"],
            "severity": ["MEDIUM", "HIGH"],
            "metric_value": [0.92, 320.5],
            "threshold_value": [1.0, 300.0],
        }
    )


def _fundamentals_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stock_code": ["005930", "005930"],
            "fiscal_year": [2024, 2023],
            "fiscal_quarter": [0, 0],
            "revenue": [320_000_00_000_000, 258_000_00_000_000],  # 억 원 단위 데이터
            "operating_profit": [32_000_00_000_000, 6_000_00_000_000],
            "net_profit": [26_000_00_000_000, 15_000_00_000_000],
            "free_cash_flow": [20_000_00_000_000, 5_000_00_000_000],
            "roe": [18.0, 9.0],
            "debt_to_equity": [0.5, 0.4],
            "operating_margin": [10.0, 2.3],
            "current_ratio": [2.1, 1.9],
        }
    )


# ── build_radar_data 테스트 ───────────────────────────────────────────────────

class BuildRadarDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.row = _scores_row()

    def test_returns_dict(self) -> None:
        result = build_radar_data(self.row)
        self.assertIsInstance(result, dict)

    def test_has_five_dimensions(self) -> None:
        result = build_radar_data(self.row)
        self.assertEqual(len(result), 5)

    def test_dimension_labels_korean(self) -> None:
        result = build_radar_data(self.row)
        self.assertIn("가치", result)
        self.assertIn("품질", result)
        self.assertIn("안전", result)
        self.assertIn("성장", result)
        self.assertIn("모멘텀", result)

    def test_values_match_scores(self) -> None:
        result = build_radar_data(self.row)
        self.assertAlmostEqual(result["가치"], 85.0)
        self.assertAlmostEqual(result["품질"], 80.0)
        self.assertAlmostEqual(result["안전"], 78.0)
        self.assertAlmostEqual(result["성장"], 75.0)
        self.assertAlmostEqual(result["모멘텀"], 70.0)

    def test_missing_scores_default_zero(self) -> None:
        row = pd.Series({"stock_code": "999999"})
        result = build_radar_data(row)
        for v in result.values():
            self.assertEqual(v, 0.0)

    def test_none_values_default_zero(self) -> None:
        row = _scores_row().copy()
        row["value_score"] = None
        result = build_radar_data(row)
        self.assertEqual(result["가치"], 0.0)

    def test_all_values_float(self) -> None:
        result = build_radar_data(self.row)
        for v in result.values():
            self.assertIsInstance(v, float)


# ── format_risk_flags 테스트 ─────────────────────────────────────────────────

class FormatRiskFlagsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _flags_df()

    def test_empty_df_returns_empty(self) -> None:
        result = format_risk_flags(pd.DataFrame())
        self.assertTrue(result.empty)

    def test_returns_dataframe(self) -> None:
        result = format_risk_flags(self.df)
        self.assertIsInstance(result, pd.DataFrame)

    def test_expected_columns_present(self) -> None:
        result = format_risk_flags(self.df)
        for col in ["위험등급", "유형", "설명", "측정값", "임계값"]:
            self.assertIn(col, result.columns)

    def test_row_count_preserved(self) -> None:
        result = format_risk_flags(self.df)
        self.assertEqual(len(result), 2)

    def test_severity_badge_medium(self) -> None:
        result = format_risk_flags(self.df)
        self.assertIn("🟡", result.iloc[0]["위험등급"])
        self.assertIn("MEDIUM", result.iloc[0]["위험등급"])

    def test_severity_badge_high(self) -> None:
        result = format_risk_flags(self.df)
        self.assertIn("🟠", result.iloc[1]["위험등급"])
        self.assertIn("HIGH", result.iloc[1]["위험등급"])

    def test_flag_type_translated(self) -> None:
        result = format_risk_flags(self.df)
        self.assertEqual(result.iloc[0]["유형"], "매출감소")
        self.assertEqual(result.iloc[1]["유형"], "고부채")

    def test_description_preserved(self) -> None:
        result = format_risk_flags(self.df)
        self.assertEqual(result.iloc[0]["설명"], "매출 YoY 5% 이상 감소")

    def test_metric_value_formatted(self) -> None:
        result = format_risk_flags(self.df)
        self.assertEqual(result.iloc[1]["측정값"], "320.50")

    def test_unknown_flag_type_uses_raw(self) -> None:
        df = self.df.copy()
        df.loc[0, "flag_type"] = "UNKNOWN_TYPE"
        result = format_risk_flags(df)
        self.assertEqual(result.iloc[0]["유형"], "UNKNOWN_TYPE")

    def test_null_description_replaced_with_dash(self) -> None:
        df = self.df.copy()
        df.loc[0, "flag_description"] = None
        result = format_risk_flags(df)
        self.assertEqual(result.iloc[0]["설명"], "—")


# ── format_fundamentals 테스트 ───────────────────────────────────────────────

class FormatFundamentalsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _fundamentals_df()

    def test_empty_df_returns_empty(self) -> None:
        result = format_fundamentals(pd.DataFrame())
        self.assertTrue(result.empty)

    def test_returns_dataframe(self) -> None:
        result = format_fundamentals(self.df)
        self.assertIsInstance(result, pd.DataFrame)

    def test_column_renamed_to_korean(self) -> None:
        result = format_fundamentals(self.df)
        self.assertIn("회계연도", result.columns)
        self.assertIn("영업이익", result.columns)
        self.assertNotIn("fiscal_year", result.columns)
        self.assertNotIn("operating_profit", result.columns)

    def test_row_count_preserved(self) -> None:
        result = format_fundamentals(self.df)
        self.assertEqual(len(result), 2)

    def test_roe_formatted_one_decimal(self) -> None:
        result = format_fundamentals(self.df)
        self.assertEqual(result.iloc[0]["ROE(%)"], "18.0")

    def test_null_money_replaced_with_dash(self) -> None:
        df = self.df.copy()
        df.loc[0, "revenue"] = None
        result = format_fundamentals(df)
        self.assertEqual(result.iloc[0]["매출액"], "—")

    def test_null_ratio_replaced_with_dash(self) -> None:
        df = self.df.copy()
        df.loc[0, "roe"] = None
        result = format_fundamentals(df)
        self.assertEqual(result.iloc[0]["ROE(%)"], "—")

    def test_only_known_columns_selected(self) -> None:
        result = format_fundamentals(self.df)
        # 원본 컬럼 중 매핑에 없는 stock_code는 포함되지 않아야 함
        self.assertNotIn("stock_code", result.columns)


if __name__ == "__main__":
    unittest.main()
