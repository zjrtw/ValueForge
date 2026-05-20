import unittest

import pandas as pd

from src.scoring.growth_scorer import add_yoy_growth_columns, compute_growth_score


class GrowthScorerTest(unittest.TestCase):
    def test_compute_growth_score_combines_four_growth_factors(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "revenue_growth_yoy": 0.30,
                    "op_profit_growth_yoy": 0.50,
                    "eps_growth_yoy": 0.40,
                    "fcf_growth_yoy": 0.20,
                },
                {
                    "revenue_growth_yoy": 0.10,
                    "op_profit_growth_yoy": 0.20,
                    "eps_growth_yoy": 0.10,
                    "fcf_growth_yoy": 0.10,
                },
                {
                    "revenue_growth_yoy": -0.10,
                    "op_profit_growth_yoy": -0.20,
                    "eps_growth_yoy": -0.10,
                    "fcf_growth_yoy": -0.30,
                },
            ]
        )

        result = compute_growth_score(df)

        self.assertEqual(result.index.tolist(), [0, 1, 2])
        self.assertAlmostEqual(result.iloc[0], 100.0)
        self.assertAlmostEqual(result.iloc[1], 200 / 3)
        self.assertAlmostEqual(result.iloc[2], 100 / 3)
        self.assertGreater(result.iloc[0], result.iloc[1])
        self.assertGreater(result.iloc[1], result.iloc[2])

    def test_compute_growth_score_handles_missing_and_invalid_values(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "revenue_growth_yoy": 0.30,
                    "op_profit_growth_yoy": 0.50,
                    "eps_growth_yoy": 0.40,
                    "fcf_growth_yoy": 0.20,
                },
                {
                    "revenue_growth_yoy": None,
                    "op_profit_growth_yoy": "bad",
                    "eps_growth_yoy": None,
                    "fcf_growth_yoy": None,
                },
            ]
        )

        result = compute_growth_score(df)

        self.assertEqual(result.iloc[0], 100.0)
        self.assertEqual(result.iloc[1], 0.0)

    def test_add_yoy_growth_columns_uses_previous_year_by_stock(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "stock_code": "5930",
                    "fiscal_year": 2023,
                    "revenue": 100,
                    "operating_profit": 20,
                    "eps": 10,
                    "free_cash_flow": 30,
                },
                {
                    "stock_code": "5930",
                    "fiscal_year": 2024,
                    "revenue": 130,
                    "operating_profit": 30,
                    "eps": 15,
                    "free_cash_flow": 45,
                },
                {
                    "stock_code": "000660",
                    "fiscal_year": 2024,
                    "revenue": 80,
                    "operating_profit": 5,
                    "eps": 3,
                    "free_cash_flow": 7,
                },
            ]
        )

        result = add_yoy_growth_columns(df)

        self.assertEqual(result.loc[0, "stock_code"], "005930")
        self.assertTrue(pd.isna(result.loc[0, "revenue_growth_yoy"]))
        self.assertAlmostEqual(result.loc[1, "revenue_growth_yoy"], 0.30)
        self.assertAlmostEqual(result.loc[1, "op_profit_growth_yoy"], 0.50)
        self.assertAlmostEqual(result.loc[1, "eps_growth_yoy"], 0.50)
        self.assertAlmostEqual(result.loc[1, "fcf_growth_yoy"], 0.50)
        self.assertTrue(pd.isna(result.loc[2, "revenue_growth_yoy"]))

    def test_compute_growth_score_can_derive_yoy_growth_from_history(self) -> None:
        df = pd.DataFrame(
            [
                {"stock_code": "005930", "fiscal_year": 2023, "revenue": 100},
                {"stock_code": "005930", "fiscal_year": 2024, "revenue": 130},
            ]
        )

        result = compute_growth_score(df)

        self.assertEqual(result.iloc[0], 0.0)
        self.assertEqual(result.iloc[1], 25.0)


if __name__ == "__main__":
    unittest.main()
