import time

import pytest

from src.utils.rate_limiter import DailyQuotaTracker, RateLimiter


class TestRateLimiter:
    def test_wait_applies_minimum_delay(self):
        limiter = RateLimiter(min_delay_seconds=0.1)
        limiter._last_call_time = time.time() - 0.05

        start = time.time()
        limiter.wait()
        elapsed = time.time() - start

        assert elapsed >= 0.04, f"Expected at least 0.04s delay, got {elapsed}"

    def test_throttle_decorator_applies_delay(self):
        limiter = RateLimiter(min_delay_seconds=0.1)

        call_times = []

        @limiter.throttle
        def tracked_func():
            call_times.append(time.time())
            return "result"

        tracked_func()
        tracked_func()

        assert len(call_times) == 2
        assert call_times[1] - call_times[0] >= 0.09

    def test_no_delay_when_enough_time_has_passed(self):
        limiter = RateLimiter(min_delay_seconds=0.05)
        limiter._last_call_time = time.time() - 0.2

        start = time.time()
        limiter.wait()
        elapsed = time.time() - start

        assert elapsed < 0.02, f"Expected minimal delay, got {elapsed}"

    def test_throttle_returns_function_result(self):
        limiter = RateLimiter(min_delay_seconds=0.01)

        @limiter.throttle
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_throttle_preserves_function_kwargs(self):
        limiter = RateLimiter(min_delay_seconds=0.01)

        @limiter.throttle
        def func_with_kwargs(a, b=10):
            return a + b

        result = func_with_kwargs(5, b=20)
        assert result == 25


class TestDailyQuotaTracker:
    def test_add_calls_within_limit(self):
        tracker = DailyQuotaTracker(daily_limit=100)
        result = tracker.add_calls(50)

        assert result is True
        assert tracker.can_call(50) is True
        assert tracker.can_call(51) is False

    def test_add_calls_exceeds_limit(self):
        tracker = DailyQuotaTracker(daily_limit=100)
        tracker.add_calls(80)

        result = tracker.add_calls(30)
        assert result is False

    def test_can_call_checks_without_recording(self):
        tracker = DailyQuotaTracker(daily_limit=100)
        tracker.add_calls(80)

        assert tracker.can_call(20) is True
        assert tracker.can_call(21) is False
        tracker.add_calls(20)
        assert tracker.can_call(1) is False

    def test_reset_clears_counter(self):
        tracker = DailyQuotaTracker(daily_limit=100)
        tracker.add_calls(80)

        tracker.reset()
        result = tracker.add_calls(100)
        assert result is True
        assert tracker.can_call(1) is False

    def test_quota_resets_on_new_day(self):
        tracker = DailyQuotaTracker(daily_limit=100)
        tracker.add_calls(80)

        tracker._reset_date = None

        assert tracker.can_call(100) is True

    def test_multiple_calls_accumulate(self):
        tracker = DailyQuotaTracker(daily_limit=100)

        tracker.add_calls(30)
        tracker.add_calls(30)
        tracker.add_calls(30)

        assert tracker.can_call(11) is False
        assert tracker.can_call(10) is True

    def test_zero_calls_is_valid(self):
        tracker = DailyQuotaTracker(daily_limit=100)
        result = tracker.add_calls(0)

        assert result is True
        assert tracker.can_call(100) is True
