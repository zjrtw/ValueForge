"""About 페이지 단위 테스트.

상수 데이터 구조의 정합성과 모듈 로딩을 검증한다.
Streamlit 렌더링은 호출하지 않는다.
"""
from __future__ import annotations

import sys
import types
import unittest

# ── Streamlit 모킹 ────────────────────────────────────────────────────────────
_mock_st = types.ModuleType("streamlit")
_mock_st.cache_resource = lambda **kw: (lambda f: f)
_mock_st.cache_data = lambda **kw: (lambda f: f)
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.pages.about import (  # noqa: E402
    DATA_SOURCES,
    DISCLAIMER,
    PIPELINE_STAGES,
)


class PipelineStagesStructureTest(unittest.TestCase):
    """PIPELINE_STAGES 상수의 구조를 검증한다."""

    def test_has_four_stages(self) -> None:
        self.assertEqual(len(PIPELINE_STAGES), 4)

    def test_all_stages_have_required_keys(self) -> None:
        required = {"id", "name", "icon", "desc", "output"}
        for stage in PIPELINE_STAGES:
            missing = required - stage.keys()
            self.assertFalse(missing, f"{stage['id']} missing keys: {missing}")

    def test_stage_ids_are_unique(self) -> None:
        ids = [s["id"] for s in PIPELINE_STAGES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_stage1_has_criteria(self) -> None:
        stage1 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 1")
        self.assertIn("criteria", stage1)
        self.assertGreater(len(stage1["criteria"]), 0)

    def test_stage1_criteria_are_triples(self) -> None:
        stage1 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 1")
        for item in stage1["criteria"]:
            self.assertEqual(len(item), 3, f"criteria item should be 3-tuple: {item}")

    def test_stage2_has_scores(self) -> None:
        stage2 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 2")
        self.assertIn("scores", stage2)
        self.assertEqual(len(stage2["scores"]), 5)

    def test_stage2_weights_sum_to_100(self) -> None:
        stage2 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 2")
        total = sum(int(s[1].rstrip("%")) for s in stage2["scores"])
        self.assertEqual(total, 100)

    def test_stage3_has_flags(self) -> None:
        stage3 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 3")
        self.assertIn("flags", stage3)
        self.assertGreater(len(stage3["flags"]), 0)

    def test_stage3_flags_have_critical_and_high(self) -> None:
        stage3 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 3")
        badges = [f[0] for f in stage3["flags"]]
        self.assertTrue(any("CRITICAL" in b for b in badges))
        self.assertTrue(any("HIGH" in b for b in badges))

    def test_stage4_has_penalty(self) -> None:
        stage4 = next(s for s in PIPELINE_STAGES if s["id"] == "Stage 4")
        self.assertIn("penalty", stage4)
        self.assertEqual(len(stage4["penalty"]), 2)

    def test_all_icons_nonempty(self) -> None:
        for stage in PIPELINE_STAGES:
            self.assertTrue(stage["icon"], f"{stage['id']} icon is empty")

    def test_all_outputs_nonempty(self) -> None:
        for stage in PIPELINE_STAGES:
            self.assertTrue(stage["output"], f"{stage['id']} output is empty")


class DataSourcesStructureTest(unittest.TestCase):
    """DATA_SOURCES 상수의 구조를 검증한다."""

    def test_has_three_sources(self) -> None:
        self.assertEqual(len(DATA_SOURCES), 3)

    def test_all_sources_have_required_keys(self) -> None:
        required = {"name", "icon", "desc", "provides", "limit"}
        for src in DATA_SOURCES:
            missing = required - src.keys()
            self.assertFalse(missing, f"{src['name']} missing keys: {missing}")

    def test_source_names_include_pykrx_and_dart(self) -> None:
        names = [s["name"] for s in DATA_SOURCES]
        self.assertIn("pykrx", names)
        self.assertIn("DART OpenAPI", names)

    def test_all_provides_nonempty(self) -> None:
        for src in DATA_SOURCES:
            self.assertGreater(len(src["provides"]), 0, f"{src['name']} provides is empty")

    def test_provides_are_lists(self) -> None:
        for src in DATA_SOURCES:
            self.assertIsInstance(src["provides"], list)


class DisclaimerTest(unittest.TestCase):
    """DISCLAIMER 상수를 검증한다."""

    def test_disclaimer_is_nonempty_string(self) -> None:
        self.assertIsInstance(DISCLAIMER, str)
        self.assertGreater(len(DISCLAIMER), 50)

    def test_disclaimer_contains_investment_warning(self) -> None:
        self.assertIn("투자", DISCLAIMER)


class ModuleImportTest(unittest.TestCase):
    """about 모듈이 정상적으로 임포트되고 render 함수가 존재하는지 확인한다."""

    def test_render_function_exists(self) -> None:
        from src.ui.pages import about
        self.assertTrue(callable(about.render))

    def test_constants_exported(self) -> None:
        from src.ui.pages import about
        self.assertIsNotNone(about.PIPELINE_STAGES)
        self.assertIsNotNone(about.DATA_SOURCES)
        self.assertIsNotNone(about.DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
