import json
import tempfile
from pathlib import Path

from src.storage.r2_client import get_r2_client
from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_LATEST_DB_KEY = "latest.db"
_METADATA_KEY = "latest_metadata.json"


def download_latest_db(
    client=None,
    bucket: str | None = None,
    dest: Path | None = None,
) -> Path:
    """R2에서 latest.db를 로컬 파일로 다운로드해 경로를 반환한다.

    dest가 없으면 시스템 임시 디렉터리에 저장한다.
    Streamlit의 st.cache_resource(ttl=1800)와 함께 사용한다.
    """
    _client = client or get_r2_client()
    _bucket = bucket or settings.R2_BUCKET_NAME
    _dest = dest or Path(tempfile.gettempdir()) / "valueforge_latest.db"

    log.info("r2_download_start", key=_LATEST_DB_KEY, dest=str(_dest))
    _client.download_file(_bucket, _LATEST_DB_KEY, str(_dest))
    size_mb = _dest.stat().st_size / 1024 / 1024
    log.info("r2_download_done", size_mb=round(size_mb, 1))
    return _dest


def get_metadata(client=None, bucket: str | None = None) -> dict:
    """latest.db 다운로드 없이 latest_metadata.json을 반환한다.

    Streamlit이 캐시 갱신 필요 여부를 판단할 때 사용한다 (약 1 KB).
    """
    _client = client or get_r2_client()
    _bucket = bucket or settings.R2_BUCKET_NAME

    resp = _client.get_object(Bucket=_bucket, Key=_METADATA_KEY)
    return json.loads(resp["Body"].read())
