import unittest

import pandas as pd

from src.scoring.safety_scorer import compute_safety_score


class SafetyScorerTest(unittest.TestCase):
    def test_compute_safety_score_combines_three_safety_factors(self) -> None:
        df = pd.DataFrame(
            [
                {"debt_to_equity": 0.2, "current_ratio": 3.0, "interest_coverage": 10.0},
                {"debt_to_equity": 0.8, "current_ratio": 2.0, "interest_coverage": 5.0},
                {"debt_to_equity": 2.0, "current_ratio": 1.0, "interest_coverage": 1.0},
            ]
        )

        result = compute_safety_score(df)

        self.assertEqual(result.index.tolist(), [0, 1, 2])
        self.assertAlmostEqual(result.iloc[0], 265 / 3)
        self.assertAlmostEqual(result.iloc[1], 55.0)
        self.assertAlmostEqual(result.iloc[2], 65 / 3)
        self.assertGreater(result.iloc[0], result.iloc[1])
        self.assertGreater(result.iloc[1], result.iloc[2])

    def test_compute_safety_score_handles_missing_and_invalid_values(self) -> None:
        df = pd.DataFrame(
            [
                {"debt_to_equity": 0.2, "current_ratio": 3.0, "interest_coverage": 10.0},
                {"debt_to_equity": None, "current_ratio": "bad", "interest_coverage": None},
            ]
        )

        result = compute_safety_score(df)

        self.assertEqual(result.iloc[0], 65.0)
        self.assertEqual(result.iloc[1], 0.0)

    def test_compute_safety_score_returns_zero_for_missing_columns(self) -> None:
        df = pd.DataFrame(index=["a", "b"])

        result = compute_safety_score(df)

        self.assertEqual(result.to_dict(), {"a": 0.0, "b": 0.0})


if __name__ == "__main__":
    unittest.main()
