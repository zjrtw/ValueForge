import unittest

import pandas as pd

from src.screening.stage1_filter import stage1_filter


TEST_PARAMS = {
    "min_market_cap_billion": 30,
    "min_avg_daily_volume_million": 500,
    "min_per": 0.0,
    "max_per": 50.0,
    "max_pbr": 10.0,
    "min_listed_days": 365,
}


class Stage1FilterTest(unittest.TestCase):
    def test_stage1_filter_keeps_rows_that_pass_all_conditions(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "stock_code": "005930",
                    "market_cap": 3_000_000_000,
                    "avg_trading_value_20d": 500_000_000,
                    "per": 10.0,
                    "pbr": 1.2,
                    "listing_days": 365,
                    "is_active": 1,
                }
            ]
        )

        result = stage1_filter(df, params=TEST_PARAMS)

        self.assertEqual(result["stock_code"].tolist(), ["005930"])

    def test_stage1_filter_removes_rows_that_fail_each_condition(self) -> None:
        valid = {
            "stock_code": "PASS",
            "market_cap": 3_000_000_000,
            "avg_trading_value_20d": 500_000_000,
            "per": 10.0,
            "pbr": 1.2,
            "listing_days": 365,
            "is_active": 1,
        }
        rows = [
            valid,
            {**valid, "stock_code": "LOW_CAP", "market_cap": 2_999_999_999},
            {**valid, "stock_code": "LOW_VOLUME", "avg_trading_value_20d": 499_999_999},
            {**valid, "stock_code": "LOW_PER", "per": 0.0},
            {**valid, "stock_code": "HIGH_PER", "per": 50.1},
            {**valid, "stock_code": "HIGH_PBR", "pbr": 10.1},
            {**valid, "stock_code": "NEW_LISTING", "listing_days": 364},
            {**valid, "stock_code": "INACTIVE", "is_active": 0},
            {**valid, "stock_code": "MISSING_PER", "per": None},
            {**valid, "stock_code": "MISSING_PBR", "pbr": None},
        ]

        result = stage1_filter(pd.DataFrame(rows), params=TEST_PARAMS)

        self.assertEqual(result["stock_code"].tolist(), ["PASS"])

    def test_stage1_filter_returns_copy_without_mutating_input(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "stock_code": "005930",
                    "market_cap": 3_000_000_000,
                    "avg_trading_value_20d": 500_000_000,
                    "per": 10.0,
                    "pbr": 1.2,
                    "listing_days": 365,
                    "is_active": 1,
                }
            ]
        )

        result = stage1_filter(df, params=TEST_PARAMS)
        result.loc[result.index[0], "stock_code"] = "CHANGED"

        self.assertEqual(df.loc[df.index[0], "stock_code"], "005930")


if __name__ == "__main__":
    unittest.main()
