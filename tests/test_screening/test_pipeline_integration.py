"""스크리닝 파이프라인 통합 테스트.

conftest.py의 합성 유니버스(30종목)를 Stage 1 → 2 → 3 → 4 순서로 통과시키며
각 Stage의 출력 형태, 데이터 흐름, 종목 탈락·유지 여부를 검증한다.
"""
import pytest

from tests.conftest import CLEAN_CODES, FAIL_CODES, TRAP_CODES


# ---------------------------------------------------------------------------
# Stage 1 — 빠른 필터
# ---------------------------------------------------------------------------


class TestStage1Integration:
    def test_reduces_universe_size(self, synthetic_universe, stage1_output):
        assert len(stage1_output) < len(synthetic_universe)

    def test_expected_pass_count(self, stage1_output):
        # 정상 16 + 함정 4 = 20 통과
        assert len(stage1_output) == 20

    def test_all_clean_stocks_pass(self, stage1_output):
        passed = set(stage1_output["stock_code"])
        for code in CLEAN_CODES:
            assert code in passed

    def test_all_trap_stocks_pass_stage1(self, stage1_output):
        # 함정은 Stage 1 기준상 유효한 종목 — Stage 3에서 걸러져야 함
        passed = set(stage1_output["stock_code"])
        for code in TRAP_CODES:
            assert code in passed

    def test_all_stage1_failures_removed(self, stage1_output):
        passed = set(stage1_output["stock_code"])
        for code in FAIL_CODES:
            assert code not in passed

    def test_output_has_required_columns(self, stage1_output):
        required = {"stock_code", "market_cap", "per", "pbr", "is_active"}
        assert required.issubset(set(stage1_output.columns))

    def test_all_passed_stocks_are_active(self, stage1_output):
        assert (stage1_output["is_active"] == 1).all()

    def test_all_passed_per_within_bounds(self, stage1_output):
        assert (stage1_output["per"] > 0).all()
        assert (stage1_output["per"] <= 50).all()


# ---------------------------------------------------------------------------
# Stage 2 — 심화 스코어링
# ---------------------------------------------------------------------------


class TestStage2Integration:
    def test_row_count_unchanged(self, stage1_output, stage2_output):
        assert len(stage2_output) == len(stage1_output)

    def test_adds_all_score_columns(self, stage2_output):
        for col in (
            "value_score", "quality_score", "safety_score",
            "growth_score", "momentum_score", "composite_score",
        ):
            assert col in stage2_output.columns, f"컬럼 누락: {col}"

    def test_all_scores_in_range(self, stage2_output):
        for col in (
            "value_score", "quality_score", "safety_score",
            "growth_score", "momentum_score", "composite_score",
        ):
            vals = stage2_output[col].dropna()
            assert (vals >= 0).all(), f"{col}에 음수 존재"
            assert (vals <= 100).all(), f"{col}이 100 초과"

    def test_score_spread_across_stocks(self, stage2_output):
        # 합성 데이터는 PER·ROE가 다르므로 composite_score 분포가 존재해야 함
        spread = stage2_output["composite_score"].max() - stage2_output["composite_score"].min()
        assert spread > 0, "composite_score가 모두 동일함"

    def test_composite_is_weighted_sum_of_dimensions(self, stage2_output):
        from tests.conftest import STAGE2_WEIGHTS as W

        expected = (
            stage2_output["value_score"] * W["value"]
            + stage2_output["quality_score"] * W["quality"]
            + stage2_output["safety_score"] * W["safety"]
            + stage2_output["growth_score"] * W["growth"]
            + stage2_output["momentum_score"] * W["momentum"]
        ).clip(0, 100)

        import pandas as pd
        pd.testing.assert_series_equal(
            stage2_output["composite_score"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
        )

    def test_does_not_drop_original_columns(self, stage1_output, stage2_output):
        for col in stage1_output.columns:
            assert col in stage2_output.columns


# ---------------------------------------------------------------------------
# Stage 3 — 가치 함정 감지
# ---------------------------------------------------------------------------


class TestStage3Integration:
    def test_row_count_unchanged(self, stage2_output, stage3_output):
        assert len(stage3_output) == len(stage2_output)

    def test_adds_all_flag_columns(self, stage3_output):
        for col in (
            "risk_flags", "critical_flag_count", "high_flag_count",
            "medium_flag_count", "low_flag_count", "is_value_trap",
        ):
            assert col in stage3_output.columns, f"컬럼 누락: {col}"

    def test_all_trap_stocks_flagged(self, stage3_output):
        traps = stage3_output[stage3_output["stock_code"].isin(TRAP_CODES)]
        assert traps["is_value_trap"].all(), "함정 종목 중 is_value_trap=False 존재"

    def test_clean_stocks_not_flagged(self, stage3_output):
        clean = stage3_output[stage3_output["stock_code"].isin(CLEAN_CODES)]
        assert not clean["is_value_trap"].any(), "정상 종목이 가치 함정으로 오분류됨"

    def test_critical_trap_has_critical_flag(self, stage3_output):
        # 900001: NEGATIVE_EQUITY (CRITICAL)
        row = stage3_output[stage3_output["stock_code"] == "900001"].iloc[0]
        assert row["critical_flag_count"] >= 1
        assert "NEGATIVE_EQUITY" in row["risk_flags"]

    def test_persistent_loss_trap_has_critical_flag(self, stage3_output):
        # 900002: PERSISTENT_OPERATING_LOSS (CRITICAL)
        row = stage3_output[stage3_output["stock_code"] == "900002"].iloc[0]
        assert "PERSISTENT_OPERATING_LOSS" in row["risk_flags"]

    def test_double_high_trap_roe_debt(self, stage3_output):
        # 900003: NEGATIVE_ROE + EXCESSIVE_DEBT → 2 HIGH
        row = stage3_output[stage3_output["stock_code"] == "900003"].iloc[0]
        assert row["high_flag_count"] >= 2
        assert row["is_value_trap"]

    def test_double_high_trap_revenue_fcf(self, stage3_output):
        # 900004: REVENUE_COLLAPSE + PERSISTENT_NEGATIVE_FCF → 2 HIGH
        row = stage3_output[stage3_output["stock_code"] == "900004"].iloc[0]
        assert row["high_flag_count"] >= 2
        assert row["is_value_trap"]

    def test_flag_counts_non_negative(self, stage3_output):
        for col in ("critical_flag_count", "high_flag_count",
                    "medium_flag_count", "low_flag_count"):
            assert (stage3_output[col] >= 0).all()


# ---------------------------------------------------------------------------
# Stage 4 — 최종 랭킹
# ---------------------------------------------------------------------------


class TestStage4Integration:
    def test_removes_all_value_traps(self, stage4_output):
        for code in TRAP_CODES:
            assert code not in stage4_output["stock_code"].tolist()

    def test_retains_all_clean_stocks(self, stage4_output):
        ranked_codes = set(stage4_output["stock_code"])
        for code in CLEAN_CODES:
            assert code in ranked_codes

    def test_final_rank_starts_at_one(self, stage4_output):
        assert stage4_output["final_rank"].min() == 1

    def test_final_rank_is_sequential(self, stage4_output):
        ranks = stage4_output["final_rank"].tolist()
        assert ranks == list(range(1, len(stage4_output) + 1))

    def test_sorted_by_adjusted_score_descending(self, stage4_output):
        scores = stage4_output["adjusted_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_no_value_traps_in_output(self, stage4_output):
        assert not stage4_output["is_value_trap"].any()

    def test_output_count(self, stage4_output):
        # 정상 종목 16개 — 함정 4개 제거 후
        assert len(stage4_output) == 16

    def test_adjusted_score_non_negative(self, stage4_output):
        assert (stage4_output["adjusted_score"] >= 0).all()


# ---------------------------------------------------------------------------
# 전체 파이프라인 종단간(End-to-End) 검증
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_universe_shrinks_through_pipeline(
        self, synthetic_universe, stage1_output, stage4_output
    ):
        assert len(stage4_output) < len(stage1_output) < len(synthetic_universe)

    def test_all_expected_columns_present(self, stage4_output):
        expected = {
            "stock_code", "per", "pbr",
            "composite_score", "value_score", "quality_score",
            "safety_score", "growth_score", "momentum_score",
            "risk_flags", "is_value_trap",
            "adjusted_score", "final_rank",
        }
        assert expected.issubset(set(stage4_output.columns))

    def test_rank_1_stock_has_highest_adjusted_score(self, stage4_output):
        rank1_score = stage4_output[stage4_output["final_rank"] == 1]["adjusted_score"].iloc[0]
        assert rank1_score == stage4_output["adjusted_score"].max()

    def test_pipeline_output_stable_across_repeated_runs(self, synthetic_universe):
        """동일 입력에 대해 두 번 실행해도 결과가 동일해야 한다."""
        from src.screening.stage1_filter import stage1_filter
        from src.screening.stage2_scorer import stage2_score
        from src.screening.stage3_trap_detector import stage3_detect_traps
        from src.screening.stage4_ranker import stage4_rank
        from tests.conftest import STAGE1_PARAMS, STAGE2_WEIGHTS, STAGE3_PARAMS, STAGE4_PARAMS

        def run_pipeline(df):
            s1 = stage1_filter(df, params=STAGE1_PARAMS)
            s2 = stage2_score(s1, weights=STAGE2_WEIGHTS)
            s3 = stage3_detect_traps(s2, params=STAGE3_PARAMS)
            return stage4_rank(s3, params=STAGE4_PARAMS)

        result_a = run_pipeline(synthetic_universe)
        result_b = run_pipeline(synthetic_universe)

        import pandas as pd
        pd.testing.assert_frame_equal(
            result_a[["stock_code", "final_rank", "adjusted_score"]].reset_index(drop=True),
            result_b[["stock_code", "final_rank", "adjusted_score"]].reset_index(drop=True),
        )

    def test_high_quality_stock_ranks_higher_than_low_quality(self, stage4_output):
        # stock_code "000001"(i=0): per=5, roe=20 → 가장 좋은 점수
        # stock_code "000016"(i=15): per=27.5, roe=12.5 → 상대적으로 낮은 점수
        rank_best = stage4_output[stage4_output["stock_code"] == "000001"]["final_rank"].iloc[0]
        rank_worst = stage4_output[stage4_output["stock_code"] == "000016"]["final_rank"].iloc[0]
        assert rank_best < rank_worst, "저PER·고ROE 종목이 더 높은 순위여야 함"
