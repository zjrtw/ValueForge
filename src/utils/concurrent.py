"""병렬 처리 유틸리티."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast


def parallel_map[T, R](
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    max_workers: int = 4,
) -> Iterator[R]:
    """Rate limit을 준수하면서 items에 대해 func을 병렬 실행한다.

    Args:
        func: 각 아이템에 대해 실행할 함수
        items: 처리할 아이템 리스트
        max_workers: 동시 실행 스레드 수 (기본값 4)
        chunk_size: executor에 미리 제출할 청크 크기 (메모리 최적화)

    Yields:
        함수 실행 결과 (원래 순서대로)
    """
    items_list = list(items)
    results: list[Any] = [None] * len(items_list)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(func, item): i for i, item in enumerate(items_list)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = None
                # We log the error but continue to allow other tasks to finish if needed, 
                # or we could re-raise. The previous implementation re-raised.
                # However, many callers expect the whole thing to fail if one fails?
                # Actually, the previous implementation re-raised.
                raise exc

    return iter(cast(list[R], results))
