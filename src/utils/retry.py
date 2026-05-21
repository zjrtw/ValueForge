import functools
import time
from collections.abc import Callable
from typing import TypeVar

from src.utils.logger import get_logger

_F = TypeVar("_F", bound=Callable)
log = get_logger(__name__)


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[_F], _F]:
    """일시적 오류에 대해 지수 백오프로 재시도하는 데코레이터.

    Args:
        max_attempts: 최대 시도 횟수 (첫 시도 포함).
        delay:        첫 번째 재시도 전 대기 시간 (초).
        backoff:      재시도마다 delay에 곱할 배수 (기본 2.0 = 지수 백오프).
        exceptions:   재시도할 예외 타입 튜플.
    """
    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            current_delay = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        log.warning(
                            "retry_attempt",
                            func=func.__qualname__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=current_delay,
                            error=str(exc),
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator
