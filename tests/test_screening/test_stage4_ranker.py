import unittest

import pandas as pd

from src.screening.stage4_ranker import stage4_rank

TEST_PARAMS = {
    "penalty_per_medium_flag": 2.0,
    "penalty_per_high_flag": 5.0,
    "top_n": 100,
}


def _row(
    stock_code: str,
    composite_score: float,
    *,
    is_value_trap: bool = False,
    medium_flag_count: int = 0,
    high_flag_count: int = 0,
) -> dict:
    return {
        "stock_code": stock_code,
        "composite_score": composite_score,
        "is_value_trap": is_value_trap,
        "medium_flag_count": medium_flag_count,
        "high_flag_count": high_flag_count,
    }


class Stage4RankBasicTest(unittest.TestCase):
    def test_adds_adjusted_score_and_final_rank(self) -> None:
        df = pd.DataFrame([_row("A", 80.0), _row("B", 60.0)])
        result = stage4_rank(df, params=TEST_PARAMS)

        self.assertIn("adjusted_score", result.columns)
        self.assertIn("final_rank", result.columns)

    def test_does_not_mutate_input(self) -> None:
        df = pd.DataFrame([_row("A", 80.0)])
        original_cols = set(df.columns)
        stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(set(df.columns), original_cols)

    def test_final_rank_starts_at_one(self) -> None:
        df = pd.DataFrame([_row("A", 80.0), _row("B", 60.0), _row("C", 40.0)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(result["final_rank"].tolist(), [1, 2, 3])

    def test_sorted_by_adjusted_score_descending(self) -> None:
        df = pd.DataFrame([_row("C", 40.0), _row("A", 80.0), _row("B", 60.0)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(result["stock_code"].tolist(), ["A", "B", "C"])

    def test_no_penalty_when_no_flags(self) -> None:
        df = pd.DataFrame([_row("A", 75.0)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 75.0)


class Stage4RankTrapRemovalTest(unittest.TestCase):
    def test_value_traps_are_removed(self) -> None:
        df = pd.DataFrame([
            _row("GOOD", 80.0, is_value_trap=False),
            _row("TRAP", 90.0, is_value_trap=True),
        ])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertNotIn("TRAP", result["stock_code"].tolist())
        self.assertIn("GOOD", result["stock_code"].tolist())

    def test_rank_1_assigned_after_trap_removal(self) -> None:
        df = pd.DataFrame([
            _row("TRAP", 90.0, is_value_trap=True),
            _row("GOOD", 70.0, is_value_trap=False),
        ])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["final_rank"], 1)
        self.assertEqual(result.iloc[0]["stock_code"], "GOOD")

    def test_returns_empty_when_all_traps(self) -> None:
        df = pd.DataFrame([
            _row("A", 80.0, is_value_trap=True),
            _row("B", 60.0, is_value_trap=True),
        ])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertTrue(result.empty)

    def test_works_without_is_value_trap_column(self) -> None:
        df = pd.DataFrame([
            {"stock_code": "A", "composite_score": 80.0},
            {"stock_code": "B", "composite_score": 60.0},
        ])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(len(result), 2)


class Stage4RankPenaltyTest(unittest.TestCase):
    def test_medium_flag_penalty_applied(self) -> None:
        df = pd.DataFrame([_row("A", 80.0, medium_flag_count=2)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 76.0)  # 80 - 2*2

    def test_high_flag_penalty_applied(self) -> None:
        df = pd.DataFrame([_row("A", 80.0, high_flag_count=1)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 75.0)  # 80 - 1*5

    def test_combined_penalty(self) -> None:
        df = pd.DataFrame([_row("A", 80.0, medium_flag_count=3, high_flag_count=1)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 69.0)  # 80 - 3*2 - 1*5

    def test_penalty_clipped_to_zero(self) -> None:
        df = pd.DataFrame([_row("A", 5.0, medium_flag_count=10)])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 0.0)

    def test_penalty_changes_ranking_order(self) -> None:
        df = pd.DataFrame([
            _row("HIGH_RAW", 85.0, medium_flag_count=5),  # adjusted = 75
            _row("LOW_RAW", 80.0),                         # adjusted = 80
        ])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(result.iloc[0]["stock_code"], "LOW_RAW")
        self.assertEqual(result.iloc[1]["stock_code"], "HIGH_RAW")

    def test_custom_penalty_values(self) -> None:
        custom = {**TEST_PARAMS, "penalty_per_medium_flag": 10.0, "penalty_per_high_flag": 0.0}
        df = pd.DataFrame([_row("A", 50.0, medium_flag_count=1)])
        result = stage4_rank(df, params=custom)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 40.0)


class Stage4RankTopNTest(unittest.TestCase):
    def test_returns_at_most_top_n(self) -> None:
        rows = [_row(str(i), float(i)) for i in range(150)]
        df = pd.DataFrame(rows)
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertEqual(len(result), 100)

    def test_top_n_returns_highest_scores(self) -> None:
        rows = [_row(str(i), float(i)) for i in range(150)]
        df = pd.DataFrame(rows)
        result = stage4_rank(df, params={**TEST_PARAMS, "top_n": 5})
        self.assertEqual(result["stock_code"].tolist(), ["149", "148", "147", "146", "145"])

    def test_top_n_of_zero_returns_empty(self) -> None:
        df = pd.DataFrame([_row("A", 80.0), _row("B", 60.0)])
        result = stage4_rank(df, params={**TEST_PARAMS, "top_n": 0})
        self.assertTrue(result.empty)

    def test_fewer_rows_than_top_n_returns_all(self) -> None:
        df = pd.DataFrame([_row("A", 80.0), _row("B", 60.0)])
        result = stage4_rank(df, params={**TEST_PARAMS, "top_n": 50})
        self.assertEqual(len(result), 2)


class Stage4RankMissingColumnsTest(unittest.TestCase):
    def test_missing_composite_score_treated_as_zero(self) -> None:
        df = pd.DataFrame([{"stock_code": "A"}, {"stock_code": "B"}])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertIn("adjusted_score", result.columns)
        self.assertTrue((result["adjusted_score"] == 0).all())

    def test_missing_flag_count_columns_treated_as_zero(self) -> None:
        df = pd.DataFrame([{"stock_code": "A", "composite_score": 70.0}])
        result = stage4_rank(df, params=TEST_PARAMS)
        self.assertAlmostEqual(result.iloc[0]["adjusted_score"], 70.0)


if __name__ == "__main__":
    unittest.main()
