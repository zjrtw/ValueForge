"""파이프라인 오류 처리 유틸리티."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from src.utils.logger import get_logger

log = get_logger(__name__)

_T = TypeVar("_T")


class PipelineAbortError(RuntimeError):
    """수집 성공률이 임계값 미만일 때 파이프라인을 중단시킨다."""


def collect_with_skip(
    fn: Callable[[], _T],
    *,
    stock_code: str,
    errors: list[str] | None = None,
) -> _T | None:
    """단일 종목 수집을 시도하고 실패 시 None을 반환한다.

    파이프라인 전체를 중단하지 않고 해당 종목만 건너뛴다.

    Args:
        fn:         인수 없는 callable (종목 수집 람다).
        stock_code: 로그용 종목 코드.
        errors:     오류 메시지를 누적할 리스트 (선택).

    Returns:
        수집 성공 시 fn()의 반환값, 실패 시 None.
    """
    try:
        return fn()
    except Exception as exc:
        msg = str(exc)
        log.warning("stock_collection_skipped", stock_code=stock_code, error=msg)
        if errors is not None:
            errors.append(f"{stock_code}: {msg}")
        return None


def check_collection_threshold(
    n_success: int,
    n_total: int,
    threshold: float = 0.5,
) -> None:
    """수집 성공률이 임계값 미만이면 PipelineAbortError를 발생시킨다.

    Args:
        n_success:  성공적으로 수집된 종목 수.
        n_total:    시도한 종목 수.
        threshold:  최소 성공률 (기본 0.5 = 50%).

    Raises:
        PipelineAbortError: 성공률 < threshold 이거나 n_total == 0.
    """
    if n_total == 0:
        raise PipelineAbortError("수집 대상 종목이 없습니다.")
    rate = n_success / n_total
    if rate < threshold:
        raise PipelineAbortError(
            f"수집 성공률 {rate:.1%}이 임계값 {threshold:.1%} 미만 — 파이프라인 중단. "
            f"(성공 {n_success}/{n_total})"
        )
    log.info(
        "collection_threshold_ok",
        n_success=n_success,
        n_total=n_total,
        rate=f"{rate:.1%}",
    )
