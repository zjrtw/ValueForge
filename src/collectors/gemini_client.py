from __future__ import annotations

import time
from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.retry import with_retry

log = get_logger(__name__)

_DEFAULT_MODEL = "gemini-1.5-flash"
_RATE_LIMIT_SLEEP = 4.0  # Flash 15 RPM → 4초 간격이면 안전
_RETRY_DELAY = 10.0       # 일시적 오류 첫 재시도 전 대기 (429/503 회복 여유)


class GeminiClientError(Exception):
    """Gemini API 호출 실패 (설정 오류 또는 최대 재시도 초과)."""


class GeminiClient:
    """Google Gemini API 래퍼.

    - AI_API_KEY 미설정 시 is_available() == False → 파이프라인 graceful skip용
    - 요청 간 rate_limit_sleep 초 대기 (Flash 기본 4초 → 15 RPM 한도 내)
    - 일시적 오류에 대해 지수 백오프 재시도 (최대 3회: 10초 → 20초 → 40초)
    - google-genai 지연 임포트 → API 키 없는 환경에서 패키지 없어도 동작
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        rate_limit_sleep: float = _RATE_LIMIT_SLEEP,
        api_key: str | None = None,
    ) -> None:
        self._model_name = model
        self._rate_limit_sleep = rate_limit_sleep
        self._last_call_time: float = 0.0
        self._client: Any = None

        key = api_key if api_key is not None else settings.AI_API_KEY
        if key:
            self._init_model(key, model)

    def _init_model(self, api_key: str, model: str) -> None:
        from google import genai  # 지연 임포트

        self._client = genai.Client(api_key=api_key)
        log.info("gemini_client_initialized", model=model)

    def is_available(self) -> bool:
        """API 키가 설정되어 모델이 초기화된 경우 True."""
        return self._client is not None

    def generate(self, prompt: str) -> str:
        """프롬프트를 Gemini 모델에 전달하고 텍스트 응답을 반환합니다.

        Args:
            prompt: 전달할 프롬프트 텍스트

        Returns:
            생성된 텍스트 응답

        Raises:
            GeminiClientError: API 키 미설정 또는 최대 재시도 초과
        """
        if not self.is_available():
            raise GeminiClientError("AI_API_KEY가 설정되지 않았습니다.")

        self._wait_for_rate_limit()
        return self._call_api_with_retry(prompt)

    def _wait_for_rate_limit(self) -> None:
        """마지막 호출 이후 rate_limit_sleep 초가 경과하지 않았으면 대기합니다."""
        elapsed = time.time() - self._last_call_time
        remaining = self._rate_limit_sleep - elapsed
        if remaining > 0:
            time.sleep(remaining)

    @with_retry(max_attempts=3, delay=_RETRY_DELAY, backoff=2.0, exceptions=(Exception,))
    def _call_api_with_retry(self, prompt: str) -> str:
        """실제 Gemini API를 호출합니다. with_retry가 일시적 오류 시 재시도합니다."""
        response = self._client.models.generate_content(model=self._model_name, contents=prompt)
        self._last_call_time = time.time()

        if not response.text:
            log.warning("gemini_empty_response", model=self._model_name)
            raise GeminiClientError("Gemini 응답 텍스트가 비어 있습니다. (차단되었을 수 있음)")

        log.debug("gemini_response_received", model=self._model_name, chars=len(response.text))
        return response.text
