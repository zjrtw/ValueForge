from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # DART API
    DART_API_KEY: str = ""

    # KRX Open API
    KRX_AUTH_KEY: str = ""

    # Cloudflare R2
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "valueforge"

    # Google Gemini API (V2 AI 정성 분석 — 미설정 시 Stage 5 자동 건너뜀)
    AI_API_KEY: str = ""

    # 파이프라인 설정
    MAX_TICKERS: int = Field(default=0, ge=0)
    MARKETS: str = "KOSPI,KOSDAQ"
    LOG_LEVEL: str = "INFO"
    DB_PATH: str = "/tmp/valueforge.db"
    DART_MAX_WORKERS: int = Field(default=4, ge=1, le=16)
    PRESERVE_DB: bool = Field(default=False)  # True: DB 유지 (운영), False: 삭제 (테스트)


class ScreeningParams:
    def __init__(self, path: Path = _CONFIG_DIR / "screening_params.yaml") -> None:
        with open(path, encoding="utf-8") as f:
            data: dict = yaml.safe_load(f)

        self.stage1: dict = data.get("stage1", {})
        self.stage2_weights: dict = data.get("stage2_weights", {})
        self.stage3: dict = data.get("stage3", {})
        self.stage4: dict = data.get("stage4", {})
        self.ai_analysis: dict = data.get("ai_analysis", {})


settings = Settings()
screening_params = ScreeningParams()

