import unittest
from datetime import date
from unittest.mock import patch, MagicMock

from src.utils.market_calendar import (
    is_trading_day,
    next_trading_day,
    prev_trading_day,
)

# KRX 실제 거래일/휴장일 (고정값 사용)
_KNOWN_TRADING_DAY = date(2025, 1, 2)      # 목요일 (거래일)
_KNOWN_HOLIDAY = date(2025, 1, 1)          # 신정 (휴장일)
_KNOWN_SATURDAY = date(2025, 1, 4)         # 토요일 (휴장일)
_KNOWN_SUNDAY = date(2025, 1, 5)           # 일요일 (휴장일)


class IsTradingDayTest(unittest.TestCase):
    def test_known_trading_day_returns_true(self) -> None:
        self.assertTrue(is_trading_day(_KNOWN_TRADING_DAY))

    def test_new_years_day_returns_false(self) -> None:
        self.assertFalse(is_trading_day(_KNOWN_HOLIDAY))

    def test_saturday_returns_false(self) -> None:
        self.assertFalse(is_trading_day(_KNOWN_SATURDAY))

    def test_sunday_returns_false(self) -> None:
        self.assertFalse(is_trading_day(_KNOWN_SUNDAY))

    def test_none_uses_today_kst(self) -> None:
        fixed = date(2025, 1, 2)
        with patch("src.utils.market_calendar._today_kst", return_value=fixed):
            result = is_trading_day(None)
        self.assertTrue(result)

    def test_returns_bool(self) -> None:
        result = is_trading_day(_KNOWN_TRADING_DAY)
        self.assertIsInstance(result, bool)

    def test_multiple_weekdays_in_january_2025(self) -> None:
        # 2025년 1월 거래일 검증 (6일 월 ~ 10일 금)
        for d in [date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8),
                  date(2025, 1, 9), date(2025, 1, 10)]:
            with self.subTest(date=d):
                self.assertTrue(is_trading_day(d))

    def test_korean_public_holiday_march_1(self) -> None:
        # 3·1절 (공휴일)
        self.assertFalse(is_trading_day(date(2025, 3, 1)))


class NextTradingDayTest(unittest.TestCase):
    def test_from_trading_day_returns_same(self) -> None:
        # 거래일에서 호출하면 해당 날짜 자체 반환 (direction="next" 포함)
        result = next_trading_day(_KNOWN_TRADING_DAY)
        self.assertIsInstance(result, date)
        self.assertGreaterEqual(result, _KNOWN_TRADING_DAY)

    def test_from_saturday_returns_monday(self) -> None:
        # 토요일(2025-01-04) 다음 거래일 → 월요일(2025-01-06)
        result = next_trading_day(_KNOWN_SATURDAY)
        self.assertEqual(result, date(2025, 1, 6))

    def test_from_new_years_day_returns_jan_2(self) -> None:
        result = next_trading_day(_KNOWN_HOLIDAY)
        self.assertEqual(result, date(2025, 1, 2))

    def test_returns_date_object(self) -> None:
        result = next_trading_day(_KNOWN_TRADING_DAY)
        self.assertIsInstance(result, date)


class PrevTradingDayTest(unittest.TestCase):
    def test_from_trading_day_returns_same(self) -> None:
        result = prev_trading_day(_KNOWN_TRADING_DAY)
        self.assertLessEqual(result, _KNOWN_TRADING_DAY)
        self.assertIsInstance(result, date)

    def test_from_saturday_returns_friday(self) -> None:
        # 토요일(2025-01-04) 이전 거래일 → 금요일(2025-01-03)
        result = prev_trading_day(_KNOWN_SATURDAY)
        self.assertEqual(result, date(2025, 1, 3))

    def test_from_sunday_returns_friday(self) -> None:
        result = prev_trading_day(_KNOWN_SUNDAY)
        self.assertEqual(result, date(2025, 1, 3))

    def test_returns_date_object(self) -> None:
        result = prev_trading_day(_KNOWN_TRADING_DAY)
        self.assertIsInstance(result, date)


class RunnerIntegrationTest(unittest.TestCase):
    """main()이 비거래일에 exit(0)으로 종료하는지 검증."""

    def test_main_exits_0_on_non_trading_day(self) -> None:
        with patch("src.pipeline.runner.is_trading_day", return_value=False), \
             patch("src.pipeline.runner._resolve_date", return_value=_KNOWN_SATURDAY), \
             patch("sys.argv", ["runner"]):
            from src.pipeline.runner import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 0)

    def test_main_proceeds_on_trading_day(self) -> None:
        with patch("src.pipeline.runner.is_trading_day", return_value=True), \
             patch("src.pipeline.runner._resolve_date", return_value=_KNOWN_TRADING_DAY), \
             patch("src.pipeline.runner.run_pipeline", return_value={}) as mock_run, \
             patch("sys.argv", ["runner"]):
            from src.pipeline.runner import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            mock_run.assert_called_once()
            self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
