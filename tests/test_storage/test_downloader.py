import json
import tempfile
import unittest
from pathlib import Path

import boto3
from moto import mock_aws

from src.storage.downloader import download_latest_db, get_metadata

_BUCKET = "test-valueforge"
_DB_CONTENT = b"SQLite format 3\x00" + b"\x00" * 84
_METADATA = {
    "run_date": "2025-01-20",
    "completed_at": "2025-01-20T08:47:23Z",
    "pipeline_version": "1.0.0",
    "stocks_collected": 2534,
    "final_candidates": 73,
}


def _make_client():
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=_BUCKET)
    return client


@mock_aws
class DownloadLatestDbTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()
        self.client.put_object(Bucket=_BUCKET, Key="latest.db", Body=_DB_CONTENT)

    def test_returns_path_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.db"
            result = download_latest_db(client=self.client, bucket=_BUCKET, dest=dest)
            self.assertIsInstance(result, Path)

    def test_file_exists_after_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.db"
            download_latest_db(client=self.client, bucket=_BUCKET, dest=dest)
            self.assertTrue(dest.exists())

    def test_downloaded_content_matches_r2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.db"
            download_latest_db(client=self.client, bucket=_BUCKET, dest=dest)
            self.assertEqual(dest.read_bytes(), _DB_CONTENT)

    def test_returns_dest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "custom.db"
            result = download_latest_db(client=self.client, bucket=_BUCKET, dest=dest)
            self.assertEqual(result, dest)

    def test_overwrites_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.db"
            dest.write_bytes(b"old content")
            download_latest_db(client=self.client, bucket=_BUCKET, dest=dest)
            self.assertEqual(dest.read_bytes(), _DB_CONTENT)

    def test_uses_default_dest_when_not_specified(self) -> None:
        result = download_latest_db(client=self.client, bucket=_BUCKET)
        try:
            self.assertIn("valueforge_latest.db", result.name)
            self.assertTrue(result.exists())
        finally:
            result.unlink(missing_ok=True)


@mock_aws
class GetMetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _make_client()
        self.client.put_object(
            Bucket=_BUCKET,
            Key="latest_metadata.json",
            Body=json.dumps(_METADATA).encode(),
            ContentType="application/json",
        )

    def test_returns_dict(self) -> None:
        result = get_metadata(client=self.client, bucket=_BUCKET)
        self.assertIsInstance(result, dict)

    def test_contains_expected_fields(self) -> None:
        result = get_metadata(client=self.client, bucket=_BUCKET)
        self.assertEqual(result["run_date"], "2025-01-20")
        self.assertEqual(result["stocks_collected"], 2534)
        self.assertEqual(result["final_candidates"], 73)

    def test_parses_all_metadata_fields(self) -> None:
        result = get_metadata(client=self.client, bucket=_BUCKET)
        self.assertEqual(result, _METADATA)

    def test_does_not_download_db(self) -> None:
        # latest.db가 없어도 메타데이터는 정상 반환돼야 함
        result = get_metadata(client=self.client, bucket=_BUCKET)
        self.assertIn("run_date", result)

    def test_unicode_content_preserved(self) -> None:
        meta_with_korean = {**_METADATA, "note": "한국어 테스트"}
        self.client.put_object(
            Bucket=_BUCKET,
            Key="latest_metadata.json",
            Body=json.dumps(meta_with_korean, ensure_ascii=False).encode("utf-8"),
        )
        result = get_metadata(client=self.client, bucket=_BUCKET)
        self.assertEqual(result["note"], "한국어 테스트")


if __name__ == "__main__":
    unittest.main()
