from __future__ import annotations

import time

import pytest

from src.collectors.gemini_client import GeminiClient, GeminiClientError


# ---------------------------------------------------------------------------
# 헬퍼: 모킹된 genai 모듈 + 모델 생성
# ---------------------------------------------------------------------------


def _make_client_with_mock(mocker, api_key: str = "test-key") -> tuple[GeminiClient, object]:
    """google.genai를 모킹하고 GeminiClient를 반환한다."""
    mock_genai = mocker.MagicMock()
    mock_client = mocker.MagicMock()
    mock_genai.Client.return_value = mock_client
    mocker.patch.dict("sys.modules", {"google.genai": mock_genai})
    # 'from google import genai' 대응을 위해 google 모듈도 패치해야 할 수 있음
    # 하지만 sys.modules["google.genai"]가 있으면 보통 해결됨

    client = GeminiClient(api_key=api_key)
    return client, mock_client


# ---------------------------------------------------------------------------
# is_available() 테스트
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_false_when_no_api_key(self, mocker):
        mocker.patch("src.collectors.gemini_client.settings")
        mocker.patch("src.collectors.gemini_client.settings.AI_API_KEY", "")

        client = GeminiClient(api_key="")
        assert client.is_available() is False

    def test_true_after_init_with_key(self, mocker):
        client, _ = _make_client_with_mock(mocker)
        assert client.is_available() is True

    def test_configure_called_with_api_key(self, mocker):
        mock_genai = mocker.MagicMock()
        mocker.patch.dict("sys.modules", {"google.genai": mock_genai})

        GeminiClient(api_key="my-key-123")
        mock_genai.Client.assert_called_once_with(api_key="my-key-123")

    def test_model_initialized_with_correct_name(self, mocker):
        # google-genai는 초기화 시점에 모델명을 받지 않고 호출 시점에 받음
        # 이 테스트는 Client 생성 확인으로 대체하거나 구조 변경 필요
        mock_genai = mocker.MagicMock()
        mocker.patch.dict("sys.modules", {"google.genai": mock_genai})

        GeminiClient(model="gemini-1.5-pro", api_key="key")
        mock_genai.Client.assert_called_once_with(api_key="key")


# ---------------------------------------------------------------------------
# generate() 테스트
# ---------------------------------------------------------------------------


class TestGenerate:
    def test_raises_when_not_available(self):
        client = GeminiClient(api_key="")
        with pytest.raises(GeminiClientError, match="AI_API_KEY"):
            client.generate("prompt")

    def test_returns_text_response(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        client, mock_client = _make_client_with_mock(mocker)
        mock_client.models.generate_content.return_value.text = "삼성전자 분석 결과입니다."

        result = client.generate("분석해줘")
        assert result == "삼성전자 분석 결과입니다."

    def test_calls_generate_content_with_prompt(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        client, mock_client = _make_client_with_mock(mocker)
        mock_client.models.generate_content.return_value.text = "응답"

        client.generate("테스트 프롬프트")
        mock_client.models.generate_content.assert_called_once_with(
            model=client._model_name, contents="테스트 프롬프트"
        )

    def test_raises_on_empty_response_text(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        client, mock_client = _make_client_with_mock(mocker)
        mock_client.models.generate_content.return_value.text = ""

        with pytest.raises(GeminiClientError, match="비어"):
            client.generate("prompt")

    def test_raises_on_none_response_text(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        client, mock_client = _make_client_with_mock(mocker)
        mock_client.models.generate_content.return_value.text = None

        with pytest.raises(GeminiClientError, match="비어"):
            client.generate("prompt")


# ---------------------------------------------------------------------------
# Rate limit 테스트
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_sleep_called_when_rate_limit_not_elapsed(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        client, mock_client = _make_client_with_mock(mocker, api_key="key")
        mock_client.models.generate_content.return_value.text = "응답"

        # 마지막 호출 시각을 방금으로 설정 → remaining ≈ rate_limit_sleep → sleep 호출됨
        client._last_call_time = time.time()
        sleep_mock = mocker.patch("src.collectors.gemini_client.time.sleep")

        client.generate("prompt")
        sleep_mock.assert_called_once()

    def test_no_sleep_if_enough_time_elapsed(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        client, mock_client = _make_client_with_mock(mocker, api_key="key")
        mock_client.models.generate_content.return_value.text = "응답"

        # 마지막 호출 시각을 충분히 과거로 설정
        client._last_call_time = time.time() - 100.0
        sleep_mock = mocker.patch("src.collectors.gemini_client.time.sleep")

        client.generate("prompt")
        sleep_mock.assert_not_called()

    def test_custom_rate_limit_sleep_applied(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        mock_genai = mocker.MagicMock()
        mock_client = mocker.MagicMock()
        mock_genai.Client.return_value = mock_client
        mocker.patch.dict("sys.modules", {"google.genai": mock_genai})

        client = GeminiClient(api_key="key", rate_limit_sleep=10.0)
        mock_client.models.generate_content.return_value.text = "응답"

        # 마지막 호출 시각을 5초 전으로 설정 → 10초 rate limit 중 5초 남음
        client._last_call_time = time.time() - 5.0
        sleep_mock = mocker.patch("src.collectors.gemini_client.time.sleep")

        client.generate("prompt")
        sleep_mock.assert_called_once()
        wait = sleep_mock.call_args[0][0]
        assert 4.0 < wait <= 5.5


# ---------------------------------------------------------------------------
# Retry 테스트
# ---------------------------------------------------------------------------


class TestRetry:
    def test_retries_on_exception_and_eventually_succeeds(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        mocker.patch("src.utils.retry.time.sleep")
        client, mock_client = _make_client_with_mock(mocker, api_key="key")

        call_count = 0
        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("일시적 오류")
            resp = mocker.MagicMock()
            resp.text = "성공 응답"
            return resp

        mock_client.models.generate_content.side_effect = side_effect
        result = client.generate("prompt")
        assert result == "성공 응답"
        assert call_count == 3

    def test_raises_after_max_attempts_exceeded(self, mocker):
        mocker.patch("src.collectors.gemini_client.time.sleep")
        mocker.patch("src.utils.retry.time.sleep")
        client, mock_client = _make_client_with_mock(mocker, api_key="key")
        mock_client.models.generate_content.side_effect = RuntimeError("영구 오류")

        with pytest.raises(RuntimeError, match="영구 오류"):
            client.generate("prompt")
        assert mock_client.models.generate_content.call_count == 3
