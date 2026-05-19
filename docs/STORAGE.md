# Cloudflare R2 스토리지 설계

> **ValueForge** | SQLite 업로드·다운로드·백업 관리

## 목차

1. [버킷 구조](#1-버킷-구조)
2. [R2 클라이언트](#2-r2-클라이언트)
3. [업로드 전략](#3-업로드-전략)
4. [백업 보존 및 자동 정리](#4-백업-보존-및-자동-정리)
5. [메타데이터 관리](#5-메타데이터-관리)
6. [Streamlit 다운로드 전략](#6-streamlit-다운로드-전략)
7. [자격증명 분리 전략](#7-자격증명-분리-전략)

---

## 1. 버킷 구조

```
valueforge-bucket/
├── latest.db                    ← 항상 최신 성공 실행 결과
├── latest_metadata.json         ← 경량 실행 요약 (DB 다운로드 없이 상태 확인용)
└── history/
    ├── 2025-01-20.db
    ├── 2025-01-19.db
    ├── 2025-01-18.db
    ├── 2025-01-17.db
    ├── 2025-01-16.db
    ├── 2025-01-15.db
    └── 2025-01-14.db            ← 7일 롤링 보존
```

### 명명 규칙

| 키 | 설명 |
|---|---|
| `latest.db` | 항상 최신. 파이프라인 성공 시마다 덮어씀 |
| `history/YYYY-MM-DD.db` | 날짜별 백업 (ISO 8601 형식) |
| `latest_metadata.json` | 최신 실행 요약 JSON |

### `latest_metadata.json` 스키마

```json
{
  "run_date": "2025-01-20",
  "completed_at": "2025-01-20T08:47:23Z",
  "pipeline_version": "1.0.0",
  "stocks_collected": 2534,
  "stage1_pass": 487,
  "stage3_trap_count": 62,
  "final_candidates": 73,
  "top_candidates": [
    {"rank": 1, "code": "012750", "name": "에스원", "score": 78.4},
    {"rank": 2, "code": "034310", "name": "NICE", "score": 76.1},
    {"rank": 3, "code": "000810", "name": "삼성화재", "score": 74.8}
  ],
  "db_size_bytes": 8234567
}
```

---

## 2. R2 클라이언트

R2는 S3 호환 API를 제공한다. `boto3`가 `endpoint_url`만 변경하면 동일하게 동작한다.

```python
# src/storage/r2_client.py

import boto3
from botocore.config import Config
from src.utils.config import settings

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=f'https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(
            signature_version='s3v4',
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        ),
        region_name='auto'
    )
```

---

## 3. 업로드 전략

### 업로드 순서 (중요)

파이프라인이 실패하더라도 `latest.db`에 부분 결과가 저장되지 않도록 순서를 엄격히 지킨다:

```
1. 파이프라인 완전 성공 확인
2. history/YYYY-MM-DD.db 업로드 (백업 먼저)
3. latest.db 덮어쓰기 (마지막에 실행)
4. latest_metadata.json 업데이트
```

```python
# src/storage/uploader.py

import json
from datetime import date, datetime, timedelta
from pathlib import Path
import logging

from src.storage.r2_client import get_r2_client
from src.utils.config import settings
from src.utils.retry import with_retry

log = logging.getLogger(__name__)
BUCKET = settings.R2_BUCKET_NAME


class R2Uploader:
    def __init__(self):
        self.client = get_r2_client()

    @with_retry(max_attempts=3, delay=5.0)
    def upload_backup(self, db_path: Path, run_date: date) -> None:
        """백업 업로드 (latest.db보다 먼저 실행)"""
        key = f"history/{run_date.isoformat()}.db"
        log.info(f"백업 업로드: {db_path} → {key}")
        self.client.upload_file(str(db_path), BUCKET, key)

    @with_retry(max_attempts=3, delay=5.0)
    def upload_latest(self, db_path: Path) -> None:
        """latest.db 덮어쓰기 (백업 완료 후 실행)"""
        log.info(f"latest.db 업로드: {db_path}")
        self.client.upload_file(
            str(db_path),
            BUCKET,
            'latest.db',
            ExtraArgs={'ContentType': 'application/x-sqlite3'}
        )
        log.info("latest.db 업로드 완료")

    def cleanup_old_backups(self, keep_days: int = 7) -> None:
        """7일 이상된 history/*.db 삭제"""
        cutoff = date.today() - timedelta(days=keep_days)
        paginator = self.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET, Prefix='history/')

        to_delete = []
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']  # 예: "history/2025-01-10.db"
                try:
                    file_date = date.fromisoformat(
                        key.replace('history/', '').replace('.db', '')
                    )
                    if file_date < cutoff:
                        to_delete.append({'Key': key})
                except ValueError:
                    continue

        if to_delete:
            self.client.delete_objects(
                Bucket=BUCKET,
                Delete={'Objects': to_delete}
            )
            log.info(f"오래된 백업 {len(to_delete)}개 삭제 완료")

    @with_retry(max_attempts=3, delay=2.0)
    def update_metadata(self, run_date: date, ranked_df) -> None:
        top5 = ranked_df.head(5)[
            ['rank', 'stock_code', 'stock_name', 'composite_score']
        ]
        meta = {
            "run_date": run_date.isoformat(),
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "pipeline_version": "1.0.0",
            "top_candidates": top5.to_dict('records'),
        }
        self.client.put_object(
            Bucket=BUCKET,
            Key='latest_metadata.json',
            Body=json.dumps(meta, ensure_ascii=False).encode('utf-8'),
            ContentType='application/json'
        )
```

---

## 4. 백업 보존 및 자동 정리

| 항목 | 정책 |
|---|---|
| 보존 기간 | 최근 7일 |
| 정리 시점 | 매 파이프라인 실행 완료 후 |
| 정리 기준 | 키 이름의 날짜(`YYYY-MM-DD`) 기준으로 7일 이전 삭제 |
| latest.db | 정리 대상 아님, 항상 유지 |
| 수동 복구 | R2 콘솔에서 `history/YYYY-MM-DD.db` 직접 다운로드 가능 |

---

## 5. 메타데이터 관리

`latest_metadata.json`은 Streamlit이 전체 DB를 다운로드하지 않고도 데이터 신선도를 확인할 수 있도록 설계되었다.

**사용 패턴**:
1. Streamlit 앱 시작 시 `latest_metadata.json` 먼저 요청 (약 1KB)
2. `run_date`가 캐시된 DB와 동일하면 → 다운로드 불필요
3. `run_date`가 다르면 → `latest.db` 다운로드 (10-50MB)

```python
# src/storage/downloader.py

import json
from src.storage.r2_client import get_r2_client
from src.utils.config import settings

def get_metadata() -> dict:
    """latest.db 다운로드 없이 실행 상태 확인"""
    client = get_r2_client()
    resp = client.get_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key='latest_metadata.json'
    )
    return json.loads(resp['Body'].read())
```

---

## 6. Streamlit 다운로드 전략

```python
# src/storage/downloader.py

import tempfile
from pathlib import Path
import logging

from src.storage.r2_client import get_r2_client
from src.utils.config import settings

log = logging.getLogger(__name__)


def download_latest_db() -> Path:
    """
    R2에서 latest.db를 임시 파일로 다운로드.
    st.cache_resource(ttl=1800)와 함께 사용하여 30분마다 갱신.
    """
    client = get_r2_client()
    tmp_path = Path(tempfile.gettempdir()) / 'valueforge_latest.db'
    log.info(f"R2에서 latest.db 다운로드 → {tmp_path}")
    client.download_file(
        settings.R2_BUCKET_NAME,
        'latest.db',
        str(tmp_path)
    )
    size_mb = tmp_path.stat().st_size / 1024 / 1024
    log.info(f"다운로드 완료 ({size_mb:.1f} MB)")
    return tmp_path
```

**Streamlit 캐싱 연동**:

```python
# src/ui/data_loader.py

@st.cache_resource(ttl=1800)   # 30분마다 최신 DB로 갱신
def get_db_connection() -> sqlite3.Connection:
    db_path = download_latest_db()
    # 읽기 전용 URI 모드 — 쓰기 접근 차단
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
```

---

## 7. 자격증명 분리 전략

**R2 API 토큰을 두 개 생성한다**:

| 토큰 | 권한 | 사용처 |
|---|---|---|
| 파이프라인 토큰 | 읽기 + 쓰기 | GitHub Actions Secrets / Hetzner VPS `.env` |
| Streamlit 토큰 | 읽기 전용 | Streamlit Cloud Secrets |

Streamlit Cloud가 침해되더라도 `latest.db`를 덮어쓸 수 없다.

**환경 변수 설정**:

```bash
# 파이프라인 서버 (쓰기 권한)
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=rw_access_key
R2_SECRET_ACCESS_KEY=rw_secret_key
R2_BUCKET_NAME=valueforge-bucket

# Streamlit Cloud (읽기 전용)
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=ro_access_key
R2_SECRET_ACCESS_KEY=ro_secret_key
R2_BUCKET_NAME=valueforge-bucket
```

→ 배포 상세: [DEPLOYMENT.md](DEPLOYMENT.md)
