import boto3
from botocore.config import Config

from src.utils.config import settings


def _get_secret(name: str) -> str:
    value = getattr(settings, name, "")
    if value:
        return value

    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])

        r2_secrets = st.secrets.get("r2", {})
        section_name = name.removeprefix("R2_").lower()
        if section_name in r2_secrets:
            return str(r2_secrets[section_name])
    except Exception:
        pass

    return ""


def get_r2_client():
    """Cloudflare R2용 boto3 S3 클라이언트를 생성해 반환한다.

    설정값은 환경 변수 또는 .env 파일에서 읽는다:
        R2_ENDPOINT_URL       — R2 엔드포인트 (예: https://<id>.r2.cloudflarestorage.com)
        R2_ACCESS_KEY_ID      — R2 액세스 키
        R2_SECRET_ACCESS_KEY  — R2 시크릿 키
    """
    endpoint_url = _get_secret("R2_ENDPOINT_URL")
    access_key_id = _get_secret("R2_ACCESS_KEY_ID")
    secret_access_key = _get_secret("R2_SECRET_ACCESS_KEY")

    if not endpoint_url.startswith("https://"):
        raise ValueError("R2_ENDPOINT_URL must start with https://")

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "adaptive"},
        ),
        region_name="auto",
    )
