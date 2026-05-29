"""환경 변수 문서화 유효성 검사 테스트.

.env.example과 docs/ENV_VARS.md의 내용이
Settings 클래스에 정의된 변수와 일치하는지 확인한다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_ENV_EXAMPLE = _ROOT / ".env.example"
_ENV_VARS_MD = _ROOT / "docs" / "ENV_VARS.md"

# Settings에 정의된 모든 환경 변수 (config.py 기준)
_REQUIRED_VARS = {
    "DART_API_KEY",
    "KRX_AUTH_KEY",
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "MAX_TICKERS",
    "MARKETS",
    "LOG_LEVEL",
    "DB_PATH",
    "DART_MAX_WORKERS",
    "PRESERVE_DB",
}

# 실제 값이 없어야 하는 민감 변수
_SENSITIVE_VARS = {"DART_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}


# ── 파일 존재 확인 ────────────────────────────────────────────────────────────

class EnvFilesExistTest(unittest.TestCase):
    def test_env_example_exists(self) -> None:
        self.assertTrue(_ENV_EXAMPLE.exists())

    def test_env_vars_md_exists(self) -> None:
        self.assertTrue(_ENV_VARS_MD.exists())


# ── .env.example 내용 검증 ───────────────────────────────────────────────────

class EnvExampleTest(unittest.TestCase):
    def _text(self) -> str:
        return _ENV_EXAMPLE.read_text(encoding="utf-8")

    def _defined_vars(self) -> set[str]:
        """KEY=value 패턴으로 정의된 변수명 집합을 반환한다."""
        return {
            m.group(1)
            for m in re.finditer(r"^([A-Z_][A-Z0-9_]*)=", self._text(), re.MULTILINE)
        }

    def test_all_required_vars_present(self) -> None:
        defined = self._defined_vars()
        missing = _REQUIRED_VARS - defined
        self.assertFalse(missing, f".env.example에 누락된 변수: {missing}")

    def test_no_extra_undefined_vars(self) -> None:
        defined = self._defined_vars()
        extra = defined - _REQUIRED_VARS
        self.assertFalse(extra, f".env.example에 config.py에 없는 변수: {extra}")

    def test_sensitive_vars_have_placeholder_values(self) -> None:
        text = self._text()
        for var in _SENSITIVE_VARS:
            pattern = rf"^{var}=(.+)$"
            match = re.search(pattern, text, re.MULTILINE)
            self.assertIsNotNone(match, f"{var}가 .env.example에 없습니다.")
            value = match.group(1).strip()
            # 실제 키처럼 보이는 값(긴 알파벳+숫자 문자열)이 없어야 함
            self.assertFalse(
                re.match(r"^[A-Za-z0-9]{20,}$", value),
                f"{var}에 실제 키처럼 보이는 값이 있습니다: {value}",
            )

    def test_r2_bucket_has_default_value(self) -> None:
        text = self._text()
        self.assertIn("R2_BUCKET_NAME=valueforge", text)

    def test_max_tickers_default_is_zero(self) -> None:
        text = self._text()
        self.assertIn("MAX_TICKERS=0", text)

    def test_log_level_default_is_info(self) -> None:
        text = self._text()
        self.assertIn("LOG_LEVEL=INFO", text)

    def test_has_comments_for_each_var(self) -> None:
        text = self._text()
        # 각 민감 변수 근처에 설명 주석이 있어야 함
        self.assertIn("DART", text)
        self.assertIn("R2", text)
        self.assertIn("opendart", text.lower())

    def test_no_real_secrets_in_file(self) -> None:
        text = self._text()
        # 실제 API 키 패턴(40자 이상 무작위 문자열)이 없어야 함
        suspicious = re.findall(r"=([A-Za-z0-9+/]{40,})", text)
        self.assertFalse(suspicious, f"실제 시크릿처럼 보이는 값이 있습니다: {suspicious}")


# ── docs/ENV_VARS.md 내용 검증 ───────────────────────────────────────────────

class EnvVarsMdTest(unittest.TestCase):
    def _text(self) -> str:
        return _ENV_VARS_MD.read_text(encoding="utf-8")

    def test_all_required_vars_documented(self) -> None:
        text = self._text()
        for var in _REQUIRED_VARS:
            self.assertIn(var, text, f"{var}가 ENV_VARS.md에 문서화되지 않았습니다.")

    def test_has_environment_comparison_table(self) -> None:
        text = self._text()
        # 파이프라인/Streamlit/로컬 환경 비교 섹션
        self.assertTrue(
            "파이프라인" in text and "Streamlit" in text,
            "환경별 설정 비교 표가 있어야 합니다.",
        )

    def test_has_secret_storage_guidance(self) -> None:
        text = self._text()
        self.assertTrue(
            "GitHub" in text and "Streamlit" in text,
            "시크릿 저장 위치 안내가 있어야 합니다.",
        )

    def test_r2_read_write_separation_mentioned(self) -> None:
        text = self._text()
        self.assertTrue(
            "읽기 전용" in text or "읽기+쓰기" in text,
            "R2 토큰 권한 분리 안내가 있어야 합니다.",
        )

    def test_dart_api_link_present(self) -> None:
        self.assertIn("opendart", self._text().lower())

    def test_has_quick_setup_section(self) -> None:
        text = self._text()
        self.assertTrue(
            "cp .env.example" in text or "빠른 설정" in text,
            "빠른 설정 안내가 있어야 합니다.",
        )


# ── config.py Settings 클래스와 동기화 확인 ──────────────────────────────────

class ConfigSyncTest(unittest.TestCase):
    def test_settings_vars_match_required_set(self) -> None:
        # Settings 클래스에서 환경변수 필드명 추출
        # pydantic_settings 없이도 필드명을 파싱으로 확인
        config_text = (_ROOT / "src" / "utils" / "config.py").read_text(encoding="utf-8")
        found = set(re.findall(r"^\s+([A-Z_][A-Z0-9_]*):\s+\w+", config_text, re.MULTILINE))
        self.assertEqual(
            found, _REQUIRED_VARS,
            f"config.py 필드와 _REQUIRED_VARS가 불일치.\n"
            f"  config.py만 있는 변수: {found - _REQUIRED_VARS}\n"
            f"  테스트만 있는 변수: {_REQUIRED_VARS - found}",
        )


if __name__ == "__main__":
    unittest.main()
