import unittest

import pandas as pd

from src.screening.stage3_trap_detector import (
    Severity,
    is_value_trap,
    stage3_detect_traps,
)

TEST_PARAMS = {
    "max_debt_ratio": 300.0,
    "min_interest_coverage": 1.5,
    "max_revenue_decline_pct": -0.30,
}

_SAFE_ROW = {
    "stock_code": "000001",
    "total_equity": 1_000_000,
    "op_profit_yr1": 100_000,
    "op_profit_yr2": 90_000,
    "roe": 15.0,
    "debt_to_equity": 1.0,
    "fcf_yr1": 50_000,
    "fcf_yr2": 40_000,
    "fcf_yr3": 30_000,
    "revenue_growth_yoy": 0.05,
    "op_margin_yr1": 0.20,
    "op_margin_yr2": 0.18,
    "op_margin_yr3": 0.15,
    "interest_coverage": 10.0,
    "industry": "제조업",
    "capex": 100_000,
    "revenue": 1_000_000,
}


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


class IsValueTrapTest(unittest.TestCase):
    def test_no_flags_is_not_trap(self) -> None:
        self.assertFalse(is_value_trap([]))

    def test_one_critical_is_trap(self) -> None:
        self.assertTrue(is_value_trap([{"severity": "CRITICAL"}]))

    def test_one_high_is_not_trap(self) -> None:
        self.assertFalse(is_value_trap([{"severity": "HIGH"}]))

    def test_two_high_is_trap(self) -> None:
        self.assertTrue(is_value_trap([{"severity": "HIGH"}, {"severity": "HIGH"}]))

    def test_medium_flags_alone_are_not_trap(self) -> None:
        flags = [{"severity": "MEDIUM"}] * 5
        self.assertFalse(is_value_trap(flags))

    def test_severity_enum_and_string_both_work(self) -> None:
        self.assertTrue(is_value_trap([{"severity": Severity.CRITICAL}]))
        self.assertTrue(
            is_value_trap([{"severity": Severity.HIGH}, {"severity": Severity.HIGH}])
        )


class Stage3DetectTrapsColumnsTest(unittest.TestCase):
    def test_adds_expected_columns(self) -> None:
        result = stage3_detect_traps(_df(_SAFE_ROW), params=TEST_PARAMS)
        for col in (
            "risk_flags",
            "critical_flag_count",
            "high_flag_count",
            "medium_flag_count",
            "low_flag_count",
            "is_value_trap",
        ):
            self.assertIn(col, result.columns, f"컬럼 누락: {col}")

    def test_does_not_mutate_input(self) -> None:
        df = _df(_SAFE_ROW)
        original_cols = set(df.columns)
        stage3_detect_traps(df, params=TEST_PARAMS)
        self.assertEqual(set(df.columns), original_cols)

    def test_preserves_row_count(self) -> None:
        df = _df(_SAFE_ROW, {**_SAFE_ROW, "stock_code": "000002"})
        result = stage3_detect_traps(df, params=TEST_PARAMS)
        self.assertEqual(len(result), 2)

    def test_safe_row_has_no_flags(self) -> None:
        result = stage3_detect_traps(_df(_SAFE_ROW), params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["critical_flag_count"], 0)
        self.assertEqual(result.iloc[0]["high_flag_count"], 0)
        self.assertFalse(result.iloc[0]["is_value_trap"])
        self.assertEqual(result.iloc[0]["risk_flags"], "")


class CriticalFlagsTest(unittest.TestCase):
    def test_negative_equity_triggers_is_value_trap(self) -> None:
        row = {**_SAFE_ROW, "total_equity": -1}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["critical_flag_count"], 1)
        self.assertTrue(result.iloc[0]["is_value_trap"])
        self.assertIn("NEGATIVE_EQUITY", result.iloc[0]["risk_flags"])

    def test_zero_equity_triggers_negative_equity_flag(self) -> None:
        row = {**_SAFE_ROW, "total_equity": 0}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("NEGATIVE_EQUITY", result.iloc[0]["risk_flags"])

    def test_persistent_operating_loss_triggers_is_value_trap(self) -> None:
        row = {**_SAFE_ROW, "op_profit_yr1": -100, "op_profit_yr2": -200}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["critical_flag_count"], 1)
        self.assertTrue(result.iloc[0]["is_value_trap"])
        self.assertIn("PERSISTENT_OPERATING_LOSS", result.iloc[0]["risk_flags"])

    def test_one_year_loss_does_not_trigger_persistent_loss(self) -> None:
        row = {**_SAFE_ROW, "op_profit_yr1": -100, "op_profit_yr2": 200}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertNotIn("PERSISTENT_OPERATING_LOSS", result.iloc[0]["risk_flags"])


class HighFlagsTest(unittest.TestCase):
    def test_negative_roe_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "roe": -6.0}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("NEGATIVE_ROE", result.iloc[0]["risk_flags"])

    def test_roe_at_threshold_does_not_trigger(self) -> None:
        row = {**_SAFE_ROW, "roe": -5.0}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertNotIn("NEGATIVE_ROE", result.iloc[0]["risk_flags"])

    def test_excessive_debt_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "debt_to_equity": 3.1}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("EXCESSIVE_DEBT", result.iloc[0]["risk_flags"])

    def test_debt_at_threshold_does_not_trigger(self) -> None:
        row = {**_SAFE_ROW, "debt_to_equity": 3.0}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertNotIn("EXCESSIVE_DEBT", result.iloc[0]["risk_flags"])

    def test_persistent_negative_fcf_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "fcf_yr1": -10, "fcf_yr2": -20, "fcf_yr3": -30}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("PERSISTENT_NEGATIVE_FCF", result.iloc[0]["risk_flags"])

    def test_two_years_negative_fcf_does_not_trigger(self) -> None:
        row = {**_SAFE_ROW, "fcf_yr1": -10, "fcf_yr2": -20, "fcf_yr3": 30}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertNotIn("PERSISTENT_NEGATIVE_FCF", result.iloc[0]["risk_flags"])

    def test_revenue_collapse_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "revenue_growth_yoy": -0.35}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("REVENUE_COLLAPSE", result.iloc[0]["risk_flags"])

    def test_two_high_flags_trigger_is_value_trap(self) -> None:
        row = {**_SAFE_ROW, "roe": -10.0, "debt_to_equity": 3.5}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["high_flag_count"], 2)
        self.assertTrue(result.iloc[0]["is_value_trap"])

    def test_one_high_flag_alone_is_not_trap(self) -> None:
        row = {**_SAFE_ROW, "roe": -10.0}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["high_flag_count"], 1)
        self.assertFalse(result.iloc[0]["is_value_trap"])


class MediumFlagsTest(unittest.TestCase):
    def test_declining_margins_triggers_flag(self) -> None:
        # yr1 < yr2 < yr3 → 최근이 가장 낮음 (하락 추세)
        row = {**_SAFE_ROW, "op_margin_yr1": 0.10, "op_margin_yr2": 0.15, "op_margin_yr3": 0.20}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("DECLINING_MARGINS", result.iloc[0]["risk_flags"])

    def test_non_declining_margins_no_flag(self) -> None:
        row = {**_SAFE_ROW, "op_margin_yr1": 0.20, "op_margin_yr2": 0.15, "op_margin_yr3": 0.10}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertNotIn("DECLINING_MARGINS", result.iloc[0]["risk_flags"])

    def test_declining_revenue_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "revenue_growth_yoy": -0.10}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("DECLINING_REVENUE", result.iloc[0]["risk_flags"])

    def test_low_interest_coverage_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "interest_coverage": 1.0}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("LOW_INTEREST_COVERAGE", result.iloc[0]["risk_flags"])

    def test_medium_flags_never_trigger_is_value_trap(self) -> None:
        row = {
            **_SAFE_ROW,
            "op_margin_yr1": 0.10,
            "op_margin_yr2": 0.15,
            "op_margin_yr3": 0.20,
            "revenue_growth_yoy": -0.10,
            "interest_coverage": 1.0,
        }
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["medium_flag_count"], 3)
        self.assertFalse(result.iloc[0]["is_value_trap"])


class LowFlagsTest(unittest.TestCase):
    def test_holding_company_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "industry": "지주회사"}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("HOLDING_COMPANY", result.iloc[0]["risk_flags"])
        self.assertEqual(result.iloc[0]["low_flag_count"], 1)

    def test_non_holding_company_no_flag(self) -> None:
        result = stage3_detect_traps(_df(_SAFE_ROW), params=TEST_PARAMS)
        self.assertNotIn("HOLDING_COMPANY", result.iloc[0]["risk_flags"])

    def test_high_capex_triggers_flag(self) -> None:
        row = {**_SAFE_ROW, "capex": 200_000, "revenue": 1_000_000}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertIn("HIGH_CAPEX", result.iloc[0]["risk_flags"])

    def test_normal_capex_no_flag(self) -> None:
        result = stage3_detect_traps(_df(_SAFE_ROW), params=TEST_PARAMS)
        self.assertNotIn("HIGH_CAPEX", result.iloc[0]["risk_flags"])


class MissingColumnsTest(unittest.TestCase):
    def test_handles_completely_empty_dataframe(self) -> None:
        df = pd.DataFrame([{"stock_code": "000001"}, {"stock_code": "000002"}])
        result = stage3_detect_traps(df, params=TEST_PARAMS)
        self.assertIn("is_value_trap", result.columns)
        self.assertFalse(result["is_value_trap"].any(), "컬럼 부재 시 거짓 양성 발생")

    def test_handles_missing_yr_columns(self) -> None:
        row = {k: v for k, v in _SAFE_ROW.items() if "yr" not in k}
        result = stage3_detect_traps(_df(row), params=TEST_PARAMS)
        self.assertNotIn("PERSISTENT_OPERATING_LOSS", result.iloc[0]["risk_flags"])
        self.assertNotIn("PERSISTENT_NEGATIVE_FCF", result.iloc[0]["risk_flags"])
        self.assertNotIn("DECLINING_MARGINS", result.iloc[0]["risk_flags"])

    def test_custom_params_override_defaults(self) -> None:
        strict_params = {**TEST_PARAMS, "max_debt_ratio": 100.0}
        row = {**_SAFE_ROW, "debt_to_equity": 1.5}
        result = stage3_detect_traps(_df(row), params=strict_params)
        self.assertIn("EXCESSIVE_DEBT", result.iloc[0]["risk_flags"])


if __name__ == "__main__":
    unittest.main()
