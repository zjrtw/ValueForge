"""병렬 처리 유틸리티."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def parallel_map(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    max_workers: int = 4,
    chunk_size: int = 1,
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
    results = [None] * len(items_list)
    future_to_idx = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 첫 배치 제출
        for idx in range(min(max_workers * chunk_size, len(items_list))):
            future = executor.submit(func, items_list[idx])
            future_to_idx[future] = idx

        # 완료된 것부터 처리하면서 새 작업 추가
        next_idx = min(max_workers * chunk_size, len(items_list))
        completed_count = 0
        for future in as_completed(future_to_idx.keys()):
            idx = future_to_idx.pop(future)
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = None
                raise exc

            completed_count += 1
            # 다음 작업 추가
            if next_idx < len(items_list):
                future = executor.submit(func, items_list[next_idx])
                future_to_idx[future] = next_idx
                next_idx += 1

    return iter(results)
