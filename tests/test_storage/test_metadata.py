import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import boto3
import pandas as pd
from freezegun import freeze_time
from moto import mock_aws

from src.storage.uploader import R2Uploader

_BUCKET = "test-valueforge"
_RUN_DATE = date(2025, 1, 20)


def _make_uploader(client) -> R2Uploader:
    return R2Uploader(client=client, bucket=_BUCKET)


def _get_metadata(client) -> dict:
    resp = client.get_object(Bucket=_BUCKET, Key="latest_metadata.json")
    return json.loads(resp["Body"].read())


def _make_ranked_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"final_rank": 1, "stock_code": "005930", "stock_name": "삼성전자", "composite_score": 82.5},
        {"final_rank": 2, "stock_code": "000660", "stock_name": "SK하이닉스", "composite_score": 79.3},
        {"final_rank": 3, "stock_code": "035420", "stock_name": "NAVER", "composite_score": 75.1},
    ])


@mock_aws
class UploadMetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = boto3.client("s3", region_name="us-east-1")
        self.client.create_bucket(Bucket=_BUCKET)
        self.uploader = _make_uploader(self.client)

    def test_uploads_to_correct_key(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE)
        resp = self.client.list_objects_v2(Bucket=_BUCKET)
        keys = [o["Key"] for o in resp.get("Contents", [])]
        self.assertIn("latest_metadata.json", keys)

    def test_content_type_is_json(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE)
        head = self.client.head_object(Bucket=_BUCKET, Key="latest_metadata.json")
        self.assertEqual(head["ContentType"], "application/json")

    def test_run_date_in_metadata(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE)
        meta = _get_metadata(self.client)
        self.assertEqual(meta["run_date"], "2025-01-20")

    @freeze_time("2025-01-20T08:47:23Z")
    def test_completed_at_is_utc_iso(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE)
        meta = _get_metadata(self.client)
        self.assertEqual(meta["completed_at"], "2025-01-20T08:47:23Z")

    def test_stats_fields_written(self) -> None:
        self.uploader.upload_metadata(
            _RUN_DATE,
            stocks_collected=2534,
            stage1_pass=487,
            stage3_trap_count=62,
            final_candidates=73,
        )
        meta = _get_metadata(self.client)
        self.assertEqual(meta["stocks_collected"], 2534)
        self.assertEqual(meta["stage1_pass"], 487)
        self.assertEqual(meta["stage3_trap_count"], 62)
        self.assertEqual(meta["final_candidates"], 73)

    def test_pipeline_version_included(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE, pipeline_version="2.0.0")
        meta = _get_metadata(self.client)
        self.assertEqual(meta["pipeline_version"], "2.0.0")

    def test_top_candidates_from_ranked_df(self) -> None:
        df = _make_ranked_df()
        self.uploader.upload_metadata(_RUN_DATE, ranked_df=df)
        meta = _get_metadata(self.client)
        self.assertEqual(len(meta["top_candidates"]), 3)
        self.assertEqual(meta["top_candidates"][0]["rank"], 1)
        self.assertEqual(meta["top_candidates"][0]["code"], "005930")
        self.assertEqual(meta["top_candidates"][0]["name"], "삼성전자")
        self.assertAlmostEqual(meta["top_candidates"][0]["score"], 82.5)

    def test_top_candidates_capped_at_five(self) -> None:
        df = pd.DataFrame([
            {"final_rank": i, "stock_code": str(i), "stock_name": f"종목{i}", "composite_score": 80.0 - i}
            for i in range(1, 10)
        ])
        self.uploader.upload_metadata(_RUN_DATE, ranked_df=df)
        meta = _get_metadata(self.client)
        self.assertEqual(len(meta["top_candidates"]), 5)

    def test_top_candidates_empty_when_no_df(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE)
        meta = _get_metadata(self.client)
        self.assertEqual(meta["top_candidates"], [])

    def test_db_size_bytes_from_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(b"x" * 1024)
            db_path = Path(f.name)
        try:
            self.uploader.upload_metadata(_RUN_DATE, db_path=db_path)
            meta = _get_metadata(self.client)
            self.assertEqual(meta["db_size_bytes"], 1024)
        finally:
            db_path.unlink(missing_ok=True)

    def test_db_size_zero_when_no_path(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE)
        meta = _get_metadata(self.client)
        self.assertEqual(meta["db_size_bytes"], 0)

    def test_overwrites_previous_metadata(self) -> None:
        self.uploader.upload_metadata(_RUN_DATE, final_candidates=50)
        self.uploader.upload_metadata(_RUN_DATE, final_candidates=73)
        meta = _get_metadata(self.client)
        self.assertEqual(meta["final_candidates"], 73)

    def test_korean_stock_names_preserved(self) -> None:
        df = pd.DataFrame([{
            "final_rank": 1, "stock_code": "005930",
            "stock_name": "삼성전자", "composite_score": 80.0,
        }])
        self.uploader.upload_metadata(_RUN_DATE, ranked_df=df)
        meta = _get_metadata(self.client)
        self.assertEqual(meta["top_candidates"][0]["name"], "삼성전자")


if __name__ == "__main__":
    unittest.main()
