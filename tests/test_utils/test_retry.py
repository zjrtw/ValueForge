import time
import unittest
from unittest.mock import MagicMock, patch

from src.utils.retry import with_retry


class WithRetryTest(unittest.TestCase):
    def test_returns_result_on_success(self) -> None:
        @with_retry(max_attempts=3, delay=0)
        def succeed():
            return 42

        self.assertEqual(succeed(), 42)

    def test_retries_on_failure_then_succeeds(self) -> None:
        call_count = 0

        @with_retry(max_attempts=3, delay=0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary")
            return "ok"

        result = flaky()
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 3)

    def test_raises_after_max_attempts(self) -> None:
        @with_retry(max_attempts=3, delay=0)
        def always_fail():
            raise RuntimeError("permanent")

        with self.assertRaises(RuntimeError):
            always_fail()

    def test_call_count_equals_max_attempts(self) -> None:
        call_count = 0

        @with_retry(max_attempts=4, delay=0)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with self.assertRaises(ValueError):
            always_fail()

        self.assertEqual(call_count, 4)

    def test_reraises_last_exception(self) -> None:
        @with_retry(max_attempts=2, delay=0)
        def fail_with_message():
            raise ValueError("specific error")

        with self.assertRaises(ValueError) as ctx:
            fail_with_message()
        self.assertIn("specific error", str(ctx.exception))

    def test_only_retries_specified_exceptions(self) -> None:
        call_count = 0

        @with_retry(max_attempts=3, delay=0, exceptions=(ValueError,))
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retried")

        with self.assertRaises(TypeError):
            raise_type_error()
        self.assertEqual(call_count, 1)  # 재시도 없이 즉시 전파

    def test_sleeps_between_attempts(self) -> None:
        sleeps: list[float] = []

        @with_retry(max_attempts=3, delay=1.0, backoff=1.0)
        def always_fail():
            raise ValueError()

        with patch("src.utils.retry.time.sleep", side_effect=sleeps.append):
            with self.assertRaises(ValueError):
                always_fail()

        self.assertEqual(len(sleeps), 2)  # 3회 중 마지막엔 sleep 없음
        self.assertAlmostEqual(sleeps[0], 1.0)
        self.assertAlmostEqual(sleeps[1], 1.0)  # backoff=1.0 → 고정 delay

    def test_exponential_backoff(self) -> None:
        sleeps: list[float] = []

        @with_retry(max_attempts=4, delay=1.0, backoff=2.0)
        def always_fail():
            raise ValueError()

        with patch("src.utils.retry.time.sleep", side_effect=sleeps.append):
            with self.assertRaises(ValueError):
                always_fail()

        self.assertEqual(len(sleeps), 3)
        self.assertAlmostEqual(sleeps[0], 1.0)   # delay * 2^0
        self.assertAlmostEqual(sleeps[1], 2.0)   # delay * 2^1
        self.assertAlmostEqual(sleeps[2], 4.0)   # delay * 2^2

    def test_no_sleep_on_first_attempt_success(self) -> None:
        with patch("src.utils.retry.time.sleep") as mock_sleep:
            @with_retry(max_attempts=3, delay=1.0)
            def succeed():
                return True

            succeed()
            mock_sleep.assert_not_called()

    def test_preserves_function_name(self) -> None:
        @with_retry()
        def my_function():
            pass

        self.assertEqual(my_function.__name__, "my_function")


class WithRetryDecoratorOnMethodTest(unittest.TestCase):
    def test_works_on_class_methods(self) -> None:
        class Service:
            def __init__(self):
                self.calls = 0

            @with_retry(max_attempts=2, delay=0)
            def fetch(self):
                self.calls += 1
                if self.calls < 2:
                    raise ConnectionError("timeout")
                return "data"

        svc = Service()
        result = svc.fetch()
        self.assertEqual(result, "data")
        self.assertEqual(svc.calls, 2)
