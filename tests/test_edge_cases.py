import pytest

from src.utils.error_handling import (
    PipelineAbortError,
    check_collection_threshold,
    collect_with_skip,
)


def test_check_collection_threshold_zero_total():
    """Edge Case: 수집 대상 종목이 0개일 때 PipelineAbortError가 발생하는지 검증"""
    with pytest.raises(PipelineAbortError, match="수집 대상 종목이 없습니다."):
        check_collection_threshold(n_success=0, n_total=0)


def test_check_collection_threshold_below_threshold():
    """Edge Case: 수집 성공률이 임계값(기본 0.5) 미만일 때 PipelineAbortError가 발생하는지 검증"""
    # 10개 시도 중 4개 성공 (40% < 50%)
    with pytest.raises(PipelineAbortError, match="임계값 50.0% 미만 — 파이프라인 중단"):
        check_collection_threshold(n_success=4, n_total=10, threshold=0.5)


def test_check_collection_threshold_success():
    """정상 Case: 수집 성공률이 임계값 이상일 때 예외가 발생하지 않는지 검증"""
    # 10개 시도 중 6개 성공 (60% > 50%) -> 예외 발생 안 함
    try:
        check_collection_threshold(n_success=6, n_total=10, threshold=0.5)
    except PipelineAbortError:
        pytest.fail("정상적인 성공률에도 PipelineAbortError가 발생했습니다.")


def test_collect_with_skip_exception():
    """Edge Case: 개별 종목 수집 중 예외 발생 시 파이프라인이 멈추지 않고 None을 반환하는지 검증"""
    errors_list = []

    def failing_collector():
        raise ValueError("DART API Rate Limit Exceeded")

    result = collect_with_skip(
        failing_collector, stock_code="005930", errors=errors_list
    )

    assert result is None
    assert len(errors_list) == 1
    assert "005930: DART API Rate Limit Exceeded" in errors_list[0]


def test_collect_with_skip_success():
    """정상 Case: 개별 종목 수집 성공 시 결과값을 올바르게 반환하는지 검증"""
    result = collect_with_skip(lambda: {"price": 50000}, stock_code="000660")
    assert result == {"price": 50000}