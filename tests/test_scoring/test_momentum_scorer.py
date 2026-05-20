import unittest

import pandas as pd

from src.scoring.momentum_scorer import (
    add_momentum_return_columns,
    compute_momentum_score,
    latest_momentum_returns,
)


class MomentumScorerTest(unittest.TestCase):
    def test_compute_momentum_score_combines_market_relative_returns(self) -> None:
        df = pd.DataFrame(
            [
                {"return_6m": 0.30, "return_3m": 0.20, "return_1m": 0.10},
                {"return_6m": 0.10, "return_3m": 0.05, "return_1m": 0.02},
                {"return_6m": -0.10, "return_3m": -0.05, "return_1m": -0.01},
            ]
        )

        result = compute_momentum_score(df, kospi_6m=0.05, kospi_3m=0.02)

        self.assertEqual(result.index.tolist(), [0, 1, 2])
        self.assertAlmostEqual(result.iloc[0], 100.0)
        self.assertAlmostEqual(result.iloc[1], 200 / 3)
        self.assertAlmostEqual(result.iloc[2], 100 / 3)
        self.assertGreater(result.iloc[0], result.iloc[1])
        self.assertGreater(result.iloc[1], result.iloc[2])

    def test_compute_momentum_score_handles_missing_and_invalid_values(self) -> None:
        df = pd.DataFrame(
            [
                {"return_6m": 0.30, "return_3m": 0.20, "return_1m": 0.10},
                {"return_6m": None, "return_3m": "bad", "return_1m": None},
            ]
        )

        result = compute_momentum_score(df)

        self.assertEqual(result.iloc[0], 100.0)
        self.assertEqual(result.iloc[1], 0.0)

    def test_add_momentum_return_columns_uses_trading_day_offsets(self) -> None:
        history = pd.DataFrame(
            {
                "stock_code": ["5930"] * 127,
                "date": pd.date_range("2024-01-01", periods=127, freq="D"),
                "close": list(range(100, 227)),
            }
        )

        result = add_momentum_return_columns(history)
        latest = result.iloc[-1]

        self.assertEqual(latest["stock_code"], "005930")
        self.assertAlmostEqual(latest["return_6m"], (226 - 100) / 100)
        self.assertAlmostEqual(latest["return_3m"], (226 - 163) / 163)
        self.assertAlmostEqual(latest["return_1m"], (226 - 205) / 205)
        self.assertTrue(pd.isna(result.iloc[125]["return_6m"]))

    def test_latest_momentum_returns_keeps_latest_row_per_stock(self) -> None:
        history = pd.DataFrame(
            [
                {"stock_code": "005930", "date": "2024-01-01", "close": 100},
                {"stock_code": "005930", "date": "2024-01-02", "close": 110},
                {"stock_code": "000660", "date": "2024-01-01", "close": 200},
            ]
        )

        result = latest_momentum_returns(history)

        self.assertEqual(result["stock_code"].tolist(), ["000660", "005930"])
        self.assertEqual(result["date"].dt.strftime("%Y-%m-%d").tolist(), ["2024-01-01", "2024-01-02"])

    def test_compute_momentum_score_can_derive_returns_from_history(self) -> None:
        high = pd.DataFrame(
            {
                "stock_code": ["005930"] * 127,
                "date": pd.date_range("2024-01-01", periods=127, freq="D"),
                "close": list(range(100, 227)),
            }
        )
        low = pd.DataFrame(
            {
                "stock_code": ["000660"] * 127,
                "date": pd.date_range("2024-01-01", periods=127, freq="D"),
                "close": list(range(200, 327)),
            }
        )

        result = compute_momentum_score(pd.concat([high, low], ignore_index=True))

        self.assertLess(result.iloc[0], result.iloc[1])


if __name__ == "__main__":
    unittest.main()
