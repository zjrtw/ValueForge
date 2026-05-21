import boto3
from botocore.config import Config

from src.utils.config import settings


def get_r2_client():
    """Cloudflare R2용 boto3 S3 클라이언트를 생성해 반환한다.

    설정값은 환경 변수 또는 .env 파일에서 읽는다:
        R2_ENDPOINT_URL       — R2 엔드포인트 (예: https://<id>.r2.cloudflarestorage.com)
        R2_ACCESS_KEY_ID      — R2 액세스 키
        R2_SECRET_ACCESS_KEY  — R2 시크릿 키
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
        region_name="auto",
    )
