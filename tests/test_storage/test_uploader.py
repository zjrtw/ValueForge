import tempfile
import unittest
from datetime import date
from pathlib import Path

import boto3
from freezegun import freeze_time
from moto import mock_aws

from src.storage.uploader import R2Uploader

_BUCKET = "test-valueforge"
_RUN_DATE = date(2025, 1, 20)


def _make_uploader(client) -> R2Uploader:
    return R2Uploader(client=client, bucket=_BUCKET)


def _make_db_file() -> Path:
    """임시 SQLite-유사 파일 생성."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.write(b"SQLite format 3\x00" + b"\x00" * 84)
    f.close()
    return Path(f.name)


def _list_keys(client, prefix: str = "") -> list[str]:
    resp = client.list_objects_v2(Bucket=_BUCKET, Prefix=prefix)
    return [o["Key"] for o in resp.get("Contents", [])]


@mock_aws
class UploadBackupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = boto3.client("s3", region_name="us-east-1")
        self.client.create_bucket(Bucket=_BUCKET)
        self.uploader = _make_uploader(self.client)
        self.db_path = _make_db_file()

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)

    def test_uploads_to_correct_key(self) -> None:
        self.uploader.upload_backup(self.db_path, _RUN_DATE)
        keys = _list_keys(self.client, "history/")
        self.assertIn("history/2025-01-20.db", keys)

    def test_uploaded_content_matches_file(self) -> None:
        self.uploader.upload_backup(self.db_path, _RUN_DATE)
        obj = self.client.get_object(Bucket=_BUCKET, Key="history/2025-01-20.db")
        self.assertEqual(obj["Body"].read(), self.db_path.read_bytes())

    def test_different_dates_produce_different_keys(self) -> None:
        date_a = date(2025, 1, 18)
        date_b = date(2025, 1, 19)
        self.uploader.upload_backup(self.db_path, date_a)
        self.uploader.upload_backup(self.db_path, date_b)
        keys = _list_keys(self.client, "history/")
        self.assertIn("history/2025-01-18.db", keys)
        self.assertIn("history/2025-01-19.db", keys)


@mock_aws
class UploadLatestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = boto3.client("s3", region_name="us-east-1")
        self.client.create_bucket(Bucket=_BUCKET)
        self.uploader = _make_uploader(self.client)
        self.db_path = _make_db_file()

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)

    def test_uploads_to_latest_db_key(self) -> None:
        self.uploader.upload_latest(self.db_path)
        keys = _list_keys(self.client)
        self.assertIn("latest.db", keys)

    def test_uploaded_content_matches_file(self) -> None:
        self.uploader.upload_latest(self.db_path)
        obj = self.client.get_object(Bucket=_BUCKET, Key="latest.db")
        self.assertEqual(obj["Body"].read(), self.db_path.read_bytes())

    def test_content_type_is_sqlite3(self) -> None:
        self.uploader.upload_latest(self.db_path)
        head = self.client.head_object(Bucket=_BUCKET, Key="latest.db")
        self.assertEqual(head["ContentType"], "application/x-sqlite3")

    def test_overwrites_previous_latest(self) -> None:
        self.uploader.upload_latest(self.db_path)

        new_file = _make_db_file()
        new_file.write_bytes(b"new content")
        try:
            self.uploader.upload_latest(new_file)
            obj = self.client.get_object(Bucket=_BUCKET, Key="latest.db")
            self.assertEqual(obj["Body"].read(), b"new content")
        finally:
            new_file.unlink(missing_ok=True)


@mock_aws
class CleanupOldBackupsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = boto3.client("s3", region_name="us-east-1")
        self.client.create_bucket(Bucket=_BUCKET)
        self.uploader = _make_uploader(self.client)

    def _put(self, key: str) -> None:
        self.client.put_object(Bucket=_BUCKET, Key=key, Body=b"data")

    @freeze_time("2025-01-20")
    def test_deletes_files_older_than_keep_days(self) -> None:
        self._put("history/2025-01-10.db")  # 10일 전 → 삭제 대상
        self._put("history/2025-01-12.db")  # 8일 전 → 삭제 대상
        self.uploader.cleanup_old_backups(keep_days=7)
        keys = _list_keys(self.client, "history/")
        self.assertNotIn("history/2025-01-10.db", keys)
        self.assertNotIn("history/2025-01-12.db", keys)

    @freeze_time("2025-01-20")
    def test_keeps_files_within_keep_days(self) -> None:
        self._put("history/2025-01-14.db")  # 6일 전 → 보존
        self._put("history/2025-01-19.db")  # 1일 전 → 보존
        self.uploader.cleanup_old_backups(keep_days=7)
        keys = _list_keys(self.client, "history/")
        self.assertIn("history/2025-01-14.db", keys)
        self.assertIn("history/2025-01-19.db", keys)

    @freeze_time("2025-01-20")
    def test_keeps_and_deletes_mixed(self) -> None:
        self._put("history/2025-01-10.db")  # 삭제
        self._put("history/2025-01-16.db")  # 보존 (4일 전)
        self.uploader.cleanup_old_backups(keep_days=7)
        keys = _list_keys(self.client, "history/")
        self.assertNotIn("history/2025-01-10.db", keys)
        self.assertIn("history/2025-01-16.db", keys)

    @freeze_time("2025-01-20")
    def test_cutoff_boundary_excluded(self) -> None:
        # 정확히 7일 전(2025-01-13)은 cutoff보다 크지 않으므로 삭제
        self._put("history/2025-01-13.db")
        self.uploader.cleanup_old_backups(keep_days=7)
        keys = _list_keys(self.client, "history/")
        self.assertNotIn("history/2025-01-13.db", keys)

    def test_handles_empty_bucket_gracefully(self) -> None:
        self.uploader.cleanup_old_backups(keep_days=7)  # 예외 없이 완료

    @freeze_time("2025-01-20")
    def test_skips_non_date_format_keys(self) -> None:
        self._put("history/invalid-name.db")
        self._put("history/2025-01-10.db")
        self.uploader.cleanup_old_backups(keep_days=7)
        keys = _list_keys(self.client, "history/")
        self.assertIn("history/invalid-name.db", keys)  # 파싱 실패 → 보존

    @freeze_time("2025-01-20")
    def test_does_not_touch_latest_db(self) -> None:
        self._put("latest.db")
        self._put("history/2025-01-10.db")
        self.uploader.cleanup_old_backups(keep_days=7)
        keys = _list_keys(self.client)
        self.assertIn("latest.db", keys)


if __name__ == "__main__":
    unittest.main()
