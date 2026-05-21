import logging
import requests
import boto3
from botocore.config import Config

# src/utils/config.py에서 설정 객체를 가져온다고 가정합니다.
# 만약 pydantic-settings 구조에 따라 속성명이 다를 경우 맞춰서 수정해주세요.
from src.utils.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_dart_api():
    logger.info("=== DART API 연결 테스트 시작 ===")
    api_key = getattr(settings, "DART_API_KEY", None)
    if not api_key:
        logger.error("DART_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        return
    
    # DART 고유번호 파일(ZIP) 다운로드 API를 호출하여 권한 테스트
    url = f"https://opendart.fss.or.kr/api/corpCode 
    
    
    
    .xml?crtfc_key={api_key}"
    response = requests.get(url)
    
    if response.status_code == 200 and b"result" not in response.content[:100]:
        # 에러 발생 시 {"status":"010","message":"등록되지 않은 인증키입니다."} 등의 json이나 xml 에러 반환됨
        logger.info("✅ DART API 연결 및 인증 성공!")
    else:
        logger.error(f"❌ DART API 연결 실패 (응답 코드: {response.status_code})")
        logger.error(f"응답 내용: {response.text[:200]}")

def test_r2_connection():
    logger.info("\n=== Cloudflare R2 연결 테스트 시작 ===")
    required_keys = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME']
    for key in required_keys:
        if not getattr(settings, key, None):
            logger.error(f"{key}가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            return

    try:
        client = boto3.client(
            's3',
            endpoint_url=f'https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        # 버킷에 있는 객체 목록 1개를 시범 조회
        client.list_objects_v2(Bucket=settings.R2_BUCKET_NAME, MaxKeys=1)
        logger.info("✅ Cloudflare R2 연결 및 접근 권한 확인 성공!")
    except Exception as e:
        logger.error(f"❌ R2 연결 실패: {e}")

if __name__ == "__main__":
    test_dart_api()
    test_r2_connection()
