import time
from datetime import date, datetime
from functools import wraps
from typing import Any, Callable, TypeVar

from src.utils.logger import get_logger

log = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class RateLimiter:
    """API 호출 간 지연 관리 및 일별 쿼터 추적."""

    def __init__(self, min_delay_seconds: float = 0.5):
        """min_delay_seconds: 연속 호출 간 최소 지연(초)."""
        self.min_delay_seconds = min_delay_seconds
        self._last_call_time: float = 0.0

    def wait(self) -> None:
        """마지막 호출 이후 필요한 지연 시간만큼 대기."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self.min_delay_seconds:
            sleep_time = self.min_delay_seconds - elapsed
            time.sleep(sleep_time)
        self._last_call_time = time.time()

    def throttle(self, func: F) -> F:
        """데코레이터: 함수 호출 전에 지연을 적용."""
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.wait()
            return func(*args, **kwargs)

        return wrapper  # type: ignore


class DailyQuotaTracker:
    """일별 API 호출 쿼터 추적 (DART 10,000건/일)."""

    def __init__(self, daily_limit: int = 10000):
        self.daily_limit = daily_limit
        self._call_count = 0
        self._reset_date: date | None = None

    def add_calls(self, count: int) -> bool:
        """
        count개의 API 호출을 기록한다. 일일 한도를 초과하면 False 반환.
        """
        today = datetime.now().date()
        if self._reset_date is None or self._reset_date != today:
            self._call_count = 0
            self._reset_date = today

        if self._call_count + count > self.daily_limit:
            log.warning(
                "daily quota limit exceeded",
                current=self._call_count,
                requested=count,
                limit=self.daily_limit,
                date=str(today),
            )
            return False

        self._call_count += count
        log.debug(
            "api calls recorded",
            total_today=self._call_count,
            limit=self.daily_limit,
            remaining=self.daily_limit - self._call_count,
        )
        return True

    def reset(self) -> None:
        """쿼터 카운트를 리셋한다 (주로 테스트용)."""
        self._call_count = 0
        self._reset_date = None

    def can_call(self, count: int = 1) -> bool:
        """count개의 호출이 가능한지 확인한다 (추가 기록 없음)."""
        today = datetime.now().date()
        if self._reset_date is None or self._reset_date != today:
            return True
        return self._call_count + count <= self.daily_limit
