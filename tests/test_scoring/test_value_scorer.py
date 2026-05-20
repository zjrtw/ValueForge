import unittest

import pandas as pd

from src.scoring.value_scorer import compute_value_score


class ValueScorerTest(unittest.TestCase):
    def test_compute_value_score_combines_four_value_factors(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "per": 5,
                    "pbr": 0.5,
                    "market_cap": 1_000,
                    "total_debt": 100,
                    "cash_and_equiv": 100,
                    "ebitda": 100,
                    "dividend_yield": 4.0,
                },
                {
                    "per": 10,
                    "pbr": 1.0,
                    "market_cap": 2_000,
                    "total_debt": 100,
                    "cash_and_equiv": 100,
                    "ebitda": 100,
                    "dividend_yield": 2.0,
                },
                {
                    "per": 20,
                    "pbr": 2.0,
                    "market_cap": 3_000,
                    "total_debt": 100,
                    "cash_and_equiv": 100,
                    "ebitda": 100,
                    "dividend_yield": 0.0,
                },
            ]
        )

        result = compute_value_score(df)

        self.assertEqual(result.index.tolist(), [0, 1, 2])
        self.assertAlmostEqual(result.iloc[0], 220 / 3)
        self.assertAlmostEqual(result.iloc[1], 40.0)
        self.assertAlmostEqual(result.iloc[2], 20 / 3)
        self.assertGreater(result.iloc[0], result.iloc[1])
        self.assertGreater(result.iloc[1], result.iloc[2])

    def test_compute_value_score_handles_missing_and_invalid_values(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "per": 5,
                    "pbr": 0.5,
                    "market_cap": 1_000,
                    "total_debt": 100,
                    "cash_and_equiv": 100,
                    "ebitda": 100,
                    "dividend_yield": 4.0,
                },
                {
                    "per": -1,
                    "pbr": None,
                    "market_cap": 1_000,
                    "total_debt": 100,
                    "cash_and_equiv": 100,
                    "ebitda": 0,
                    "dividend_yield": None,
                },
            ]
        )

        result = compute_value_score(df)

        self.assertEqual(result.iloc[0], 20.0)
        self.assertEqual(result.iloc[1], 0.0)

    def test_compute_value_score_returns_zero_for_missing_columns(self) -> None:
        df = pd.DataFrame(index=["a", "b"])

        result = compute_value_score(df)

        self.assertEqual(result.to_dict(), {"a": 0.0, "b": 0.0})


if __name__ == "__main__":
    unittest.main()
