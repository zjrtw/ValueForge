import unittest

from src.utils.error_handling import (
    PipelineAbortError,
    check_collection_threshold,
    collect_with_skip,
)


class CollectWithSkipTest(unittest.TestCase):
    def test_returns_result_on_success(self) -> None:
        result = collect_with_skip(lambda: 42, stock_code="005930")
        self.assertEqual(result, 42)

    def test_returns_none_on_exception(self) -> None:
        def fail():
            raise RuntimeError("timeout")

        result = collect_with_skip(fail, stock_code="005930")
        self.assertIsNone(result)

    def test_accumulates_error_message(self) -> None:
        errors: list[str] = []

        def fail():
            raise ValueError("bad data")

        collect_with_skip(fail, stock_code="005930", errors=errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("005930", errors[0])
        self.assertIn("bad data", errors[0])

    def test_multiple_stocks_accumulate_errors(self) -> None:
        errors: list[str] = []

        for code in ["000001", "000002", "000003"]:
            collect_with_skip(
                lambda: (_ for _ in ()).throw(RuntimeError("fail")),
                stock_code=code,
                errors=errors,
            )

        self.assertEqual(len(errors), 3)

    def test_no_errors_list_still_works(self) -> None:
        def fail():
            raise RuntimeError("oops")

        result = collect_with_skip(fail, stock_code="005930")
        self.assertIsNone(result)

    def test_successful_call_does_not_add_to_errors(self) -> None:
        errors: list[str] = []
        collect_with_skip(lambda: "ok", stock_code="005930", errors=errors)
        self.assertEqual(errors, [])

    def test_catches_any_exception_type(self) -> None:
        for exc_type in (ValueError, RuntimeError, ConnectionError, KeyError):
            def fail(et=exc_type):
                raise et("msg")
            result = collect_with_skip(fail, stock_code="000001")
            self.assertIsNone(result)


class CheckCollectionThresholdTest(unittest.TestCase):
    def test_passes_when_above_threshold(self) -> None:
        check_collection_threshold(90, 100, threshold=0.5)  # 90% > 50%

    def test_passes_at_exact_threshold(self) -> None:
        check_collection_threshold(50, 100, threshold=0.5)  # 50% == 50%

    def test_raises_below_threshold(self) -> None:
        with self.assertRaises(PipelineAbortError):
            check_collection_threshold(49, 100, threshold=0.5)

    def test_raises_when_zero_total(self) -> None:
        with self.assertRaises(PipelineAbortError):
            check_collection_threshold(0, 0, threshold=0.5)

    def test_raises_when_all_failed(self) -> None:
        with self.assertRaises(PipelineAbortError):
            check_collection_threshold(0, 100, threshold=0.5)

    def test_passes_when_all_succeeded(self) -> None:
        check_collection_threshold(100, 100, threshold=0.5)

    def test_custom_threshold(self) -> None:
        check_collection_threshold(80, 100, threshold=0.75)
        with self.assertRaises(PipelineAbortError):
            check_collection_threshold(74, 100, threshold=0.75)

    def test_error_message_contains_rate(self) -> None:
        with self.assertRaises(PipelineAbortError) as ctx:
            check_collection_threshold(30, 100, threshold=0.5)
        self.assertIn("30.0%", str(ctx.exception))

    def test_pipeline_abort_error_is_runtime_error(self) -> None:
        self.assertTrue(issubclass(PipelineAbortError, RuntimeError))


class RunnerThresholdIntegrationTest(unittest.TestCase):
    """runner._collect 이후 임계값 체크가 정상 동작하는지 검증."""

    def test_abort_error_propagated_from_runner(self) -> None:
        import os
        from datetime import date
        from pathlib import Path
        from unittest.mock import patch

        import pandas as pd

        tickers = pd.DataFrame([{"stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI"}])
        prices = pd.DataFrame()  # 빈 DataFrame → n_errors = n_collected

        env_patch = patch.dict(
            os.environ,
            {
                "KRX_AUTH_KEY": "",
                "HTTP_PROXY": "",
                "HTTPS_PROXY": "",
                "http_proxy": "",
                "https_proxy": "",
                "ALL_PROXY": "",
                "all_proxy": "",
            },
        )
        env_patch.start()

        try:
            from src.pipeline import runner

            patches = [
                patch.object(runner, "fetch_ticker_list", return_value=tickers),
                patch.object(runner, "fetch_daily_price_data", return_value=prices),
                patch.object(runner, "fetch_financial_statements", return_value=pd.DataFrame()),
                patch.object(runner, "fetch_company_metadata", return_value=pd.DataFrame()),
                patch.object(runner, "R2Uploader"),
            ]
            for p in patches:
                p.start()

            from src.pipeline.runner import run_pipeline

            db_path = Path("test_threshold_abort.db")
            try:
                with self.assertRaises(PipelineAbortError):
                    run_pipeline(date(2025, 1, 20), db_path=db_path, upload=False)
            finally:
                if db_path.exists():
                    db_path.unlink()
        finally:
            for p in patches:
                p.stop()
            env_patch.stop()
