import unittest

import pandas as pd

from src.screening.stage2_scorer import stage2_score

_WEIGHTS = {
    "value": 0.30,
    "quality": 0.25,
    "safety": 0.20,
    "growth": 0.15,
    "momentum": 0.10,
}

_BASE_ROW = {
    "stock_code": "005930",
    "per": 10.0,
    "pbr": 1.2,
    "dividend_yield": 2.0,
    "ebitda": 1_000_000,
    "market_cap": 10_000_000,
    "total_debt": 500_000,
    "cash_and_equiv": 200_000,
    "roe": 15.0,
    "roa": 8.0,
    "operating_margin": 0.20,
    "debt_to_equity": 0.5,
    "current_ratio": 2.0,
    "interest_coverage": 10.0,
    "revenue": 5_000_000,
    "operating_profit": 1_000_000,
    "eps": 500.0,
    "free_cash_flow": 800_000,
    "return_6m": 0.10,
    "return_3m": 0.05,
    "return_1m": 0.02,
    "fiscal_year": 2024,
}


def _make_df(n: int = 5) -> pd.DataFrame:
    rows = []
    for i in range(n):
        row = {**_BASE_ROW, "stock_code": str(i).zfill(6)}
        row["per"] = 5.0 + i * 2
        row["roe"] = 10.0 + i * 3
        rows.append(row)
    return pd.DataFrame(rows)


class Stage2ScorerTest(unittest.TestCase):
    def test_stage2_score_adds_expected_columns(self) -> None:
        df = _make_df()
        result = stage2_score(df, weights=_WEIGHTS)

        for col in ("value_score", "quality_score", "safety_score", "growth_score", "momentum_score", "composite_score"):
            self.assertIn(col, result.columns, f"컬럼 누락: {col}")

    def test_stage2_score_values_in_range(self) -> None:
        df = _make_df()
        result = stage2_score(df, weights=_WEIGHTS)

        for col in ("value_score", "quality_score", "safety_score", "growth_score", "momentum_score", "composite_score"):
            self.assertTrue((result[col].dropna() >= 0).all(), f"{col} 음수 값 존재")
            self.assertTrue((result[col].dropna() <= 100).all(), f"{col} 100 초과 값 존재")

    def test_stage2_score_composite_is_weighted_sum(self) -> None:
        df = _make_df()
        result = stage2_score(df, weights=_WEIGHTS)

        expected = (
            result["value_score"] * _WEIGHTS["value"]
            + result["quality_score"] * _WEIGHTS["quality"]
            + result["safety_score"] * _WEIGHTS["safety"]
            + result["growth_score"] * _WEIGHTS["growth"]
            + result["momentum_score"] * _WEIGHTS["momentum"]
        ).clip(0, 100)

        pd.testing.assert_series_equal(result["composite_score"], expected, check_names=False)

    def test_stage2_score_does_not_mutate_input(self) -> None:
        df = _make_df()
        original_columns = set(df.columns)
        stage2_score(df, weights=_WEIGHTS)

        self.assertEqual(set(df.columns), original_columns)

    def test_stage2_score_preserves_row_count(self) -> None:
        df = _make_df(10)
        result = stage2_score(df, weights=_WEIGHTS)

        self.assertEqual(len(result), len(df))

    def test_stage2_score_custom_weights(self) -> None:
        df = _make_df()
        all_value_weights = {"value": 1.0, "quality": 0.0, "safety": 0.0, "growth": 0.0, "momentum": 0.0}
        result = stage2_score(df, weights=all_value_weights)

        pd.testing.assert_series_equal(result["composite_score"], result["value_score"], check_names=False)

    def test_stage2_score_handles_missing_columns_gracefully(self) -> None:
        df = pd.DataFrame([{"stock_code": "000001"}, {"stock_code": "000002"}])
        result = stage2_score(df, weights=_WEIGHTS)

        self.assertIn("composite_score", result.columns)

    def test_stage2_score_accepts_kospi_benchmark_params(self) -> None:
        df = _make_df()
        # kospi_6m, kospi_3m 파라미터가 오류 없이 전달되는지 확인
        result = stage2_score(df, weights=_WEIGHTS, kospi_6m=0.05, kospi_3m=0.02)

        self.assertIn("momentum_score", result.columns)
        self.assertFalse(result["momentum_score"].isna().all())


if __name__ == "__main__":
    unittest.main()
