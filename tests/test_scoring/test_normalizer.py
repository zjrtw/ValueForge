import unittest

import pandas as pd

from src.scoring.normalizer import percentile_rank_score


class NormalizerTest(unittest.TestCase):
    def test_percentile_rank_score_when_higher_is_better(self) -> None:
        series = pd.Series([10, 20, 30], index=["a", "b", "c"])

        result = percentile_rank_score(series)

        self.assertAlmostEqual(result["a"], 100 / 3)
        self.assertAlmostEqual(result["b"], 200 / 3)
        self.assertEqual(result["c"], 100.0)

    def test_percentile_rank_score_when_lower_is_better(self) -> None:
        series = pd.Series([10, 20, 30], index=["a", "b", "c"])

        result = percentile_rank_score(series, higher_is_better=False)

        self.assertAlmostEqual(result["a"], 200 / 3)
        self.assertAlmostEqual(result["b"], 100 / 3)
        self.assertEqual(result["c"], 0.0)

    def test_percentile_rank_score_places_missing_values_at_bottom(self) -> None:
        series = pd.Series([10, None, 30], index=["valid_low", "missing", "valid_high"])

        higher_result = percentile_rank_score(series)
        lower_result = percentile_rank_score(series, higher_is_better=False)

        self.assertEqual(higher_result["missing"], 0.0)
        self.assertEqual(higher_result["valid_high"], 100.0)
        self.assertEqual(lower_result["missing"], 0.0)
        self.assertEqual(lower_result["valid_low"], 50.0)

    def test_percentile_rank_score_converts_non_numeric_values_to_missing(self) -> None:
        series = pd.Series(["10", "bad", "30"], index=["low", "bad", "high"])

        result = percentile_rank_score(series)

        self.assertEqual(result["bad"], 0.0)
        self.assertEqual(result["high"], 100.0)


if __name__ == "__main__":
    unittest.main()
