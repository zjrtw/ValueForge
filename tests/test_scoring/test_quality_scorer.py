import unittest

import pandas as pd

from src.scoring.quality_scorer import add_roe_stability, compute_quality_score


class QualityScorerTest(unittest.TestCase):
    def test_compute_quality_score_combines_four_quality_factors(self) -> None:
        df = pd.DataFrame(
            [
                {"roe": 0.30, "roa": 0.15, "operating_margin": 0.20, "roe_3yr_std": 0.01},
                {"roe": 0.20, "roa": 0.10, "operating_margin": 0.15, "roe_3yr_std": 0.03},
                {"roe": 0.10, "roa": 0.05, "operating_margin": 0.10, "roe_3yr_std": 0.06},
            ]
        )

        result = compute_quality_score(df)

        self.assertEqual(result.index.tolist(), [0, 1, 2])
        self.assertAlmostEqual(result.iloc[0], 280 / 3)
        self.assertAlmostEqual(result.iloc[1], 60.0)
        self.assertAlmostEqual(result.iloc[2], 80 / 3)

    def test_compute_quality_score_handles_missing_and_invalid_values(self) -> None:
        df = pd.DataFrame(
            [
                {"roe": 0.30, "roa": 0.15, "operating_margin": 0.20, "roe_3yr_std": 0.01},
                {"roe": None, "roa": "bad", "operating_margin": None, "roe_3yr_std": None},
            ]
        )

        result = compute_quality_score(df)

        self.assertEqual(result.iloc[0], 80.0)
        self.assertEqual(result.iloc[1], 0.0)

    def test_add_roe_stability_uses_recent_three_year_rolling_std(self) -> None:
        df = pd.DataFrame(
            [
                {"stock_code": "5930", "fiscal_year": 2022, "roe": 0.10},
                {"stock_code": "5930", "fiscal_year": 2023, "roe": 0.20},
                {"stock_code": "5930", "fiscal_year": 2024, "roe": 0.30},
                {"stock_code": "000660", "fiscal_year": 2023, "roe": 0.05},
                {"stock_code": "000660", "fiscal_year": 2024, "roe": 0.10},
            ]
        )

        result = add_roe_stability(df)

        self.assertEqual(result.loc[0, "stock_code"], "005930")
        self.assertTrue(pd.isna(result.loc[0, "roe_3yr_std"]))
        self.assertTrue(pd.isna(result.loc[1, "roe_3yr_std"]))
        self.assertAlmostEqual(result.loc[2, "roe_3yr_std"], 0.10)
        self.assertTrue(pd.isna(result.loc[3, "roe_3yr_std"]))
        self.assertTrue(pd.isna(result.loc[4, "roe_3yr_std"]))

    def test_compute_quality_score_can_derive_roe_stability_from_history(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "stock_code": "005930",
                    "fiscal_year": 2022,
                    "roe": 0.10,
                    "roa": 0.05,
                    "operating_margin": 0.10,
                },
                {
                    "stock_code": "005930",
                    "fiscal_year": 2023,
                    "roe": 0.20,
                    "roa": 0.10,
                    "operating_margin": 0.15,
                },
                {
                    "stock_code": "005930",
                    "fiscal_year": 2024,
                    "roe": 0.30,
                    "roa": 0.15,
                    "operating_margin": 0.20,
                },
            ]
        )

        result = compute_quality_score(df)

        self.assertAlmostEqual(result.iloc[0], 80 / 3)
        self.assertAlmostEqual(result.iloc[1], 160 / 3)
        self.assertGreater(result.iloc[2], result.iloc[1])


if __name__ == "__main__":
    unittest.main()
