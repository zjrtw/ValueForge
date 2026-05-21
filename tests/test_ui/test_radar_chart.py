"""레이더 차트 컴포넌트 단위 테스트.

prepare_radar_coords / render_radar 함수의 동작을 검증한다.
실제 Plotly Figure를 생성하여 트레이스·레이아웃 속성을 확인한다.
"""
from __future__ import annotations

import unittest

from src.ui.components.radar_chart import prepare_radar_coords, render_radar

_SAMPLE = {
    "가치": 85.0,
    "품질": 70.0,
    "안전": 60.0,
    "성장": 75.0,
    "모멘텀": 50.0,
}


# ── prepare_radar_coords 테스트 ───────────────────────────────────────────────

class PrepareRadarCoordsTest(unittest.TestCase):
    def test_returns_two_lists(self) -> None:
        theta, r = prepare_radar_coords(_SAMPLE)
        self.assertIsInstance(theta, list)
        self.assertIsInstance(r, list)

    def test_closes_polygon(self) -> None:
        theta, r = prepare_radar_coords(_SAMPLE)
        self.assertEqual(theta[0], theta[-1])
        self.assertAlmostEqual(r[0], r[-1])

    def test_length_is_n_plus_1(self) -> None:
        theta, r = prepare_radar_coords(_SAMPLE)
        n = len(_SAMPLE)
        self.assertEqual(len(theta), n + 1)
        self.assertEqual(len(r), n + 1)

    def test_values_are_floats(self) -> None:
        _, r = prepare_radar_coords(_SAMPLE)
        for v in r:
            self.assertIsInstance(v, float)

    def test_category_order_preserved(self) -> None:
        theta, _ = prepare_radar_coords(_SAMPLE)
        expected = list(_SAMPLE.keys())
        self.assertEqual(theta[:-1], expected)

    def test_values_match_input(self) -> None:
        _, r = prepare_radar_coords(_SAMPLE)
        expected = list(_SAMPLE.values())
        for a, b in zip(r[:-1], expected, strict=False):
            self.assertAlmostEqual(a, b)

    def test_single_category(self) -> None:
        theta, r = prepare_radar_coords({"A": 50.0})
        self.assertEqual(len(theta), 2)
        self.assertEqual(theta, ["A", "A"])


# ── render_radar 단일 트레이스 테스트 ────────────────────────────────────────

class RenderRadarSingleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fig = render_radar(_SAMPLE)

    def test_returns_figure(self) -> None:
        import plotly.graph_objects as go
        self.assertIsInstance(self.fig, go.Figure)

    def test_has_one_trace(self) -> None:
        self.assertEqual(len(self.fig.data), 1)

    def test_trace_is_scatterpolar(self) -> None:
        import plotly.graph_objects as go
        self.assertIsInstance(self.fig.data[0], go.Scatterpolar)

    def test_trace_fills_toself(self) -> None:
        self.assertEqual(self.fig.data[0].fill, "toself")

    def test_trace_r_length(self) -> None:
        # 5개 차원 + 닫기 1개 = 6
        self.assertEqual(len(self.fig.data[0].r), len(_SAMPLE) + 1)

    def test_default_label(self) -> None:
        self.assertEqual(self.fig.data[0].name, "점수")

    def test_custom_label(self) -> None:
        fig = render_radar(_SAMPLE, label="삼성전자")
        self.assertEqual(fig.data[0].name, "삼성전자")

    def test_legend_hidden_without_overlay(self) -> None:
        self.assertFalse(self.fig.layout.showlegend)

    def test_default_height(self) -> None:
        self.assertEqual(self.fig.layout.height, 320)

    def test_custom_height(self) -> None:
        fig = render_radar(_SAMPLE, height=400)
        self.assertEqual(fig.layout.height, 400)

    def test_radial_axis_range(self) -> None:
        r_range = self.fig.layout.polar.radialaxis.range
        self.assertEqual(list(r_range), [0, 100.0])

    def test_custom_max_value(self) -> None:
        fig = render_radar(_SAMPLE, max_value=50.0)
        self.assertEqual(list(fig.layout.polar.radialaxis.range), [0, 50.0])


# ── render_radar 오버레이(비교) 테스트 ───────────────────────────────────────

class RenderRadarOverlayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.overlay = {k: v * 0.8 for k, v in _SAMPLE.items()}
        self.fig = render_radar(
            _SAMPLE,
            label="종목 A",
            overlay=self.overlay,
            overlay_label="종목 B",
        )

    def test_has_two_traces(self) -> None:
        self.assertEqual(len(self.fig.data), 2)

    def test_first_trace_label(self) -> None:
        self.assertEqual(self.fig.data[0].name, "종목 A")

    def test_second_trace_label(self) -> None:
        self.assertEqual(self.fig.data[1].name, "종목 B")

    def test_legend_shown_with_overlay(self) -> None:
        self.assertTrue(self.fig.layout.showlegend)

    def test_overlay_values_correct(self) -> None:
        expected_first = self.overlay[list(self.overlay.keys())[0]]
        self.assertAlmostEqual(self.fig.data[1].r[0], expected_first)

    def test_overlay_category_mismatch_raises(self) -> None:
        bad_overlay = {"A": 1.0, "B": 2.0}
        with self.assertRaises(ValueError):
            render_radar(_SAMPLE, overlay=bad_overlay)


# ── 예외 처리 테스트 ─────────────────────────────────────────────────────────

class RenderRadarErrorTest(unittest.TestCase):
    def test_empty_values_raises(self) -> None:
        with self.assertRaises(ValueError):
            render_radar({})


# ── detail.py 통합 확인: build_radar_fig 제거 후 render_radar 사용 ────────────

class DetailPageRadarIntegrationTest(unittest.TestCase):
    def test_detail_does_not_define_build_radar_fig(self) -> None:
        import sys
        import types

        _mock_st = types.ModuleType("streamlit")
        _mock_st.cache_resource = lambda **kw: (lambda f: f)
        _mock_st.cache_data = lambda **kw: (lambda f: f)
        sys.modules.setdefault("streamlit", _mock_st)

        import importlib

        import src.ui.views.detail as detail_mod

        importlib.reload(detail_mod)

        self.assertFalse(
            hasattr(detail_mod, "build_radar_fig"),
            "build_radar_fig should have been removed from detail.py",
        )

    def test_detail_imports_render_radar(self) -> None:
        import src.ui.views.detail as detail_mod

        self.assertTrue(hasattr(detail_mod, "render_radar"))


if __name__ == "__main__":
    unittest.main()
