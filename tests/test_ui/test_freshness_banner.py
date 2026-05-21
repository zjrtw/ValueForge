"""데이터 최신성 배너 단위 테스트.

get_data_age_days / get_freshness_level 순수 함수를 검증한다.
Streamlit 렌더링은 호출하지 않는다.
"""
from __future__ import annotations

import sys
import types
import unittest
from datetime import date

# ── Streamlit 모킹 ────────────────────────────────────────────────────────────
_mock_st = types.ModuleType("streamlit")
_mock_st.cache_resource = lambda **kw: (lambda f: f)
_mock_st.cache_data = lambda **kw: (lambda f: f)
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.components.freshness_banner import (  # noqa: E402
    get_data_age_days,
    get_freshness_level,
)

_TODAY = date(2025, 1, 22)


# ── get_data_age_days 테스트 ─────────────────────────────────────────────────

class GetDataAgeDaysTest(unittest.TestCase):
    def test_same_day_is_zero(self) -> None:
        self.assertEqual(get_data_age_days("2025-01-22", _TODAY), 0)

    def test_one_day_ago(self) -> None:
        self.assertEqual(get_data_age_days("2025-01-21", _TODAY), 1)

    def test_two_days_ago(self) -> None:
        self.assertEqual(get_data_age_days("2025-01-20", _TODAY), 2)

    def test_five_days_ago(self) -> None:
        self.assertEqual(get_data_age_days("2025-01-17", _TODAY), 5)

    def test_week_ago(self) -> None:
        self.assertEqual(get_data_age_days("2025-01-15", _TODAY), 7)

    def test_returns_int(self) -> None:
        result = get_data_age_days("2025-01-20", _TODAY)
        self.assertIsInstance(result, int)

    def test_invalid_date_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_data_age_days("not-a-date", _TODAY)

    def test_future_date_negative(self) -> None:
        result = get_data_age_days("2025-01-23", _TODAY)
        self.assertLess(result, 0)

    def test_uses_today_when_no_reference(self) -> None:
        # today 파라미터 생략 시 오류 없이 호출 가능한지 확인
        result = get_data_age_days(date.today().isoformat())
        self.assertIsInstance(result, int)


# ── get_freshness_level 테스트 ───────────────────────────────────────────────

class GetFreshnessLevelTest(unittest.TestCase):
    def test_zero_days_is_fresh(self) -> None:
        self.assertEqual(get_freshness_level(0), "fresh")

    def test_one_day_is_fresh(self) -> None:
        self.assertEqual(get_freshness_level(1), "fresh")

    def test_two_days_is_stale(self) -> None:
        self.assertEqual(get_freshness_level(2), "stale")

    def test_three_days_is_stale(self) -> None:
        self.assertEqual(get_freshness_level(3), "stale")

    def test_four_days_is_stale(self) -> None:
        self.assertEqual(get_freshness_level(4), "stale")

    def test_five_days_is_very_stale(self) -> None:
        self.assertEqual(get_freshness_level(5), "very_stale")

    def test_ten_days_is_very_stale(self) -> None:
        self.assertEqual(get_freshness_level(10), "very_stale")

    def test_negative_is_fresh(self) -> None:
        # 미래 run_date (edge case)
        self.assertEqual(get_freshness_level(-1), "fresh")

    def test_boundary_stale_to_very_stale(self) -> None:
        self.assertEqual(get_freshness_level(4), "stale")
        self.assertEqual(get_freshness_level(5), "very_stale")


# ── 통합: age→level 연계 테스트 ──────────────────────────────────────────────

class FreshnessIntegrationTest(unittest.TestCase):
    def test_today_run_is_fresh(self) -> None:
        age = get_data_age_days("2025-01-22", _TODAY)
        level = get_freshness_level(age)
        self.assertEqual(level, "fresh")

    def test_yesterday_run_is_fresh(self) -> None:
        age = get_data_age_days("2025-01-21", _TODAY)
        level = get_freshness_level(age)
        self.assertEqual(level, "fresh")

    def test_two_days_ago_is_stale(self) -> None:
        age = get_data_age_days("2025-01-20", _TODAY)
        level = get_freshness_level(age)
        self.assertEqual(level, "stale")

    def test_week_ago_is_very_stale(self) -> None:
        age = get_data_age_days("2025-01-15", _TODAY)
        level = get_freshness_level(age)
        self.assertEqual(level, "very_stale")


if __name__ == "__main__":
    unittest.main()
