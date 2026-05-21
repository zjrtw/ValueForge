"""CSV 내보내기 단위 테스트.

to_csv_bytes 함수의 UTF-8 BOM 인코딩과 컬럼 변환을 검증한다.
"""
from __future__ import annotations

import csv
import io
import sys
import types
import unittest

import pandas as pd

# ── Streamlit 모킹 ────────────────────────────────────────────────────────────
_mock_st = types.ModuleType("streamlit")
_mock_st.cache_resource = lambda **kw: (lambda f: f)
_mock_st.cache_data = lambda **kw: (lambda f: f)
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.views.ranking import to_csv_bytes  # noqa: E402

_RUN_DATE = "2025-01-20"


def _make_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run_date": [_RUN_DATE, _RUN_DATE, _RUN_DATE],
            "rank": [1, 2, 3],
            "stock_code": ["005930", "000660", "086520"],
            "stock_name": ["삼성전자", "SK하이닉스", "에코프로"],
            "market": ["KOSPI", "KOSPI", "KOSDAQ"],
            "sector": ["IT", "IT", "소재"],
            "composite_score": [82.5, 76.3, 65.8],
            "value_score": [85.0, 78.0, 70.0],
            "quality_score": [80.0, 75.0, 60.0],
            "safety_score": [78.0, 72.0, 55.0],
            "growth_score": [75.0, 70.0, 75.0],
            "momentum_score": [70.0, 65.0, 80.0],
            "market_cap_b": [400.0, 50.0, 5.0],
            "per": [9.0, 11.0, 60.0],
            "pbr": [1.2, 1.5, 8.0],
            "roe": [18.0, 15.0, 25.0],
            "dividend_yield": [2.5, 1.5, 0.0],
            "debt_to_equity": [0.5, 0.8, 2.5],
            "risk_flag_count": [0, 1, 2],
            "highest_severity": [None, "MEDIUM", "HIGH"],
        }
    )


# ── BOM 및 인코딩 테스트 ──────────────────────────────────────────────────────

class CsvEncodingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()
        self.result = to_csv_bytes(self.df)

    def test_returns_bytes(self) -> None:
        self.assertIsInstance(self.result, bytes)

    def test_starts_with_utf8_bom(self) -> None:
        self.assertTrue(
            self.result.startswith(b"\xef\xbb\xbf"),
            "UTF-8 BOM(\\xef\\xbb\\xbf)으로 시작해야 합니다.",
        )

    def test_decodable_as_utf8(self) -> None:
        text = self.result.decode("utf-8-sig")
        self.assertIsInstance(text, str)

    def test_korean_chars_preserved(self) -> None:
        text = self.result.decode("utf-8-sig")
        self.assertIn("삼성전자", text)
        self.assertIn("에코프로", text)


# ── 컬럼명 변환 테스트 ────────────────────────────────────────────────────────

class CsvColumnTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()
        text = to_csv_bytes(self.df).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        self.rows = list(reader)
        self.headers = reader.fieldnames or []

    def test_headers_are_korean(self) -> None:
        self.assertIn("순위", self.headers)
        self.assertIn("종목코드", self.headers)
        self.assertIn("종목명", self.headers)
        self.assertIn("종합점수", self.headers)

    def test_no_english_score_columns(self) -> None:
        for h in self.headers:
            self.assertNotIn("score", h.lower())
            self.assertNotIn("_score", h.lower())

    def test_run_date_excluded(self) -> None:
        self.assertNotIn("run_date", self.headers)

    def test_listing_date_excluded(self) -> None:
        self.assertNotIn("listing_date", self.headers)


# ── 데이터 값 테스트 ──────────────────────────────────────────────────────────

class CsvDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = _make_df()
        text = to_csv_bytes(self.df).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        self.rows = list(reader)

    def test_row_count_matches(self) -> None:
        self.assertEqual(len(self.rows), 3)

    def test_rank_values_correct(self) -> None:
        ranks = [int(r["순위"]) for r in self.rows]
        self.assertEqual(ranks, [1, 2, 3])

    def test_composite_score_preserved(self) -> None:
        scores = [float(r["종합점수"]) for r in self.rows]
        self.assertAlmostEqual(scores[0], 82.5)
        self.assertAlmostEqual(scores[1], 76.3)

    def test_severity_raw_value_no_badge(self) -> None:
        # CSV에는 배지 이모지 없이 원본 값이 저장되어야 함
        severities = [r["최고위험"] for r in self.rows]
        for sev in severities:
            self.assertNotIn("🟠", sev)
            self.assertNotIn("🟡", sev)

    def test_null_severity_empty_or_none(self) -> None:
        # 첫 번째 종목 최고위험은 None → 빈 문자열 또는 "None"
        first_sev = self.rows[0]["최고위험"]
        self.assertIn(first_sev, ("", "None", "nan"))


# ── 엣지 케이스 테스트 ────────────────────────────────────────────────────────

class CsvEdgeCaseTest(unittest.TestCase):
    def test_empty_df_returns_header_only(self) -> None:
        df_empty = pd.DataFrame(columns=_make_df().columns)
        result = to_csv_bytes(df_empty)
        text = result.decode("utf-8-sig")
        lines = [line for line in text.splitlines() if line.strip()]
        # 헤더 1줄만 있어야 함
        self.assertEqual(len(lines), 1)

    def test_partial_columns_handled(self) -> None:
        # 일부 컬럼만 있는 DataFrame도 에러 없이 처리되어야 함
        df_minimal = pd.DataFrame(
            {"rank": [1], "stock_code": ["005930"], "stock_name": ["삼성전자"]}
        )
        result = to_csv_bytes(df_minimal)
        self.assertTrue(result.startswith(b"\xef\xbb\xbf"))
        text = result.decode("utf-8-sig")
        self.assertIn("삼성전자", text)

    def test_single_row(self) -> None:
        df_one = _make_df().head(1)
        result = to_csv_bytes(df_one)
        text = result.decode("utf-8-sig")
        rows = [line for line in text.splitlines() if line.strip()]
        self.assertEqual(len(rows), 2)  # 헤더 + 데이터 1줄


if __name__ == "__main__":
    unittest.main()
