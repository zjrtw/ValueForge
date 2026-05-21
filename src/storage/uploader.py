import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.storage.r2_client import get_r2_client
from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.retry import with_retry

if TYPE_CHECKING:
    import pandas as pd

_PIPELINE_VERSION = "1.0.0"

log = get_logger(__name__)


class R2Uploader:
    """Cloudflare R2에 SQLite 파일을 업로드·관리한다.

    업로드 순서 (파티셜 업로드 방지):
        1. upload_backup  — history/YYYY-MM-DD.db 먼저
        2. upload_latest  — latest.db 덮어쓰기
        3. cleanup_old_backups — 오래된 백업 정리
    """

    def __init__(self, client=None, bucket: str | None = None) -> None:
        self.client = client or get_r2_client()
        self.bucket = bucket or settings.R2_BUCKET_NAME

    @with_retry(max_attempts=3, delay=5.0)
    def upload_backup(self, db_path: Path, run_date: date) -> None:
        """백업 업로드: history/YYYY-MM-DD.db (latest보다 먼저 실행)."""
        key = f"history/{run_date.isoformat()}.db"
        log.info("r2_backup_upload_start", path=str(db_path), key=key)
        self.client.upload_file(str(db_path), self.bucket, key)
        log.info("r2_backup_upload_done", key=key)

    @with_retry(max_attempts=3, delay=5.0)
    def upload_latest(self, db_path: Path) -> None:
        """latest.db 덮어쓰기 (백업 완료 후 실행)."""
        log.info("r2_latest_upload_start", path=str(db_path))
        self.client.upload_file(
            str(db_path),
            self.bucket,
            "latest.db",
            ExtraArgs={"ContentType": "application/x-sqlite3"},
        )
        log.info("r2_latest_upload_done")

    def cleanup_old_backups(self, keep_days: int = 7) -> None:
        """history/ 아래 keep_days일을 초과한 .db 파일을 삭제한다."""
        cutoff = date.today() - timedelta(days=keep_days)
        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix="history/")

        to_delete: list[dict] = []
        for page in pages:
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                try:
                    file_date = date.fromisoformat(
                        key.removeprefix("history/").removesuffix(".db")
                    )
                    if file_date <= cutoff:
                        to_delete.append({"Key": key})
                except ValueError:
                    continue

        if to_delete:
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": to_delete},
            )
            log.info("r2_old_backups_deleted", count=len(to_delete))
        else:
            log.info("r2_no_old_backups_to_delete")

    @with_retry(max_attempts=3, delay=2.0)
    def upload_metadata(
        self,
        run_date: date,
        *,
        db_path: Path | None = None,
        stocks_collected: int = 0,
        stage1_pass: int = 0,
        stage3_trap_count: int = 0,
        final_candidates: int = 0,
        ranked_df: "pd.DataFrame | None" = None,
        pipeline_version: str = _PIPELINE_VERSION,
    ) -> None:
        """latest_metadata.json을 생성해 R2에 업로드한다."""
        top_candidates: list[dict] = []
        if ranked_df is not None and not ranked_df.empty:
            top_candidates = _build_top_candidates(ranked_df)

        metadata: dict = {
            "run_date": run_date.isoformat(),
            "completed_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pipeline_version": pipeline_version,
            "stocks_collected": stocks_collected,
            "stage1_pass": stage1_pass,
            "stage3_trap_count": stage3_trap_count,
            "final_candidates": final_candidates,
            "top_candidates": top_candidates,
            "db_size_bytes": db_path.stat().st_size if db_path and db_path.exists() else 0,
        }

        body = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
        self.client.put_object(
            Bucket=self.bucket,
            Key="latest_metadata.json",
            Body=body,
            ContentType="application/json",
        )
        log.info("r2_metadata_uploaded", run_date=run_date.isoformat())


def _build_top_candidates(ranked_df: "pd.DataFrame") -> list[dict]:
    """ranked_df 상위 5개를 top_candidates 형태로 변환한다."""
    top5 = ranked_df.head(5)
    result = []
    for _, row in top5.iterrows():
        result.append({
            "rank": int(row.get("final_rank", 0)),
            "code": str(row.get("stock_code", "")),
            "name": str(row.get("stock_name", "")),
            "score": round(float(row.get("composite_score", 0.0)), 1),
        })
    return result
