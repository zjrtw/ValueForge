"""Dockerfile 구조 유효성 검사 테스트.

Docker 빌드 없이 Dockerfile 내용을 파싱하여 보안·최적화 요건을 확인한다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_DOCKERFILE = _ROOT / "Dockerfile"
_DOCKERIGNORE = _ROOT / ".dockerignore"
_REQ_PIPELINE = _ROOT / "requirements-pipeline.txt"


def _lines() -> list[str]:
    return _DOCKERFILE.read_text(encoding="utf-8").splitlines()


def _text() -> str:
    return _DOCKERFILE.read_text(encoding="utf-8")


# ── 파일 존재 확인 ────────────────────────────────────────────────────────────

class DockerfileExistsTest(unittest.TestCase):
    def test_dockerfile_exists(self) -> None:
        self.assertTrue(_DOCKERFILE.exists(), "Dockerfile이 프로젝트 루트에 없습니다.")

    def test_dockerignore_exists(self) -> None:
        self.assertTrue(_DOCKERIGNORE.exists(), ".dockerignore가 없습니다.")

    def test_requirements_pipeline_exists(self) -> None:
        self.assertTrue(_REQ_PIPELINE.exists(), "requirements-pipeline.txt가 없습니다.")


# ── 멀티스테이지 빌드 ─────────────────────────────────────────────────────────

class MultiStageBuildTest(unittest.TestCase):
    def test_has_two_from_instructions(self) -> None:
        from_lines = [l for l in _lines() if re.match(r"^FROM\s", l, re.IGNORECASE)]
        self.assertGreaterEqual(len(from_lines), 2, "멀티스테이지 빌드(FROM 2개 이상)여야 합니다.")

    def test_builder_stage_named(self) -> None:
        self.assertIn("AS builder", _text())

    def test_runtime_stage_named(self) -> None:
        self.assertIn("AS runtime", _text())

    def test_uses_python_311(self) -> None:
        from_lines = [l for l in _lines() if re.match(r"^FROM\s", l, re.IGNORECASE)]
        self.assertTrue(
            any("3.11" in l for l in from_lines),
            "Python 3.11 기반 이미지를 사용해야 합니다.",
        )

    def test_uses_slim_image(self) -> None:
        from_lines = [l for l in _lines() if re.match(r"^FROM\s", l, re.IGNORECASE)]
        self.assertTrue(
            any("slim" in l for l in from_lines),
            "경량 slim 이미지를 사용해야 합니다.",
        )

    def test_copies_venv_from_builder(self) -> None:
        self.assertIn("--from=builder", _text())


# ── 보안 설정 ─────────────────────────────────────────────────────────────────

class SecurityTest(unittest.TestCase):
    def test_non_root_user_created(self) -> None:
        self.assertIn("useradd", _text(), "비루트 사용자를 생성해야 합니다.")

    def test_user_instruction_present(self) -> None:
        user_lines = [l.strip() for l in _lines() if re.match(r"^USER\s", l.strip(), re.IGNORECASE)]
        self.assertTrue(user_lines, "USER 지시문으로 비루트 사용자를 지정해야 합니다.")

    def test_user_is_not_root(self) -> None:
        user_lines = [l.strip() for l in _lines() if re.match(r"^USER\s", l.strip(), re.IGNORECASE)]
        for line in user_lines:
            self.assertNotIn("root", line.lower(), f"USER가 root면 안 됩니다: {line}")


# ── 환경변수 설정 ─────────────────────────────────────────────────────────────

class EnvVarTest(unittest.TestCase):
    def test_pythonunbuffered_set(self) -> None:
        self.assertIn("PYTHONUNBUFFERED=1", _text())

    def test_pythondontwritebytecode_set(self) -> None:
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", _text())

    def test_pythonpath_set(self) -> None:
        self.assertIn("PYTHONPATH", _text())


# ── 진입점 설정 ───────────────────────────────────────────────────────────────

class EntrypointTest(unittest.TestCase):
    def test_entrypoint_uses_pipeline_runner(self) -> None:
        self.assertIn("src.pipeline.runner", _text())

    def test_entrypoint_instruction_present(self) -> None:
        ep_lines = [l for l in _lines() if re.match(r"^ENTRYPOINT\s", l.strip(), re.IGNORECASE)]
        self.assertTrue(ep_lines, "ENTRYPOINT 지시문이 있어야 합니다.")

    def test_workdir_set(self) -> None:
        wd_lines = [l for l in _lines() if re.match(r"^WORKDIR\s", l.strip(), re.IGNORECASE)]
        self.assertTrue(wd_lines, "WORKDIR 지시문이 있어야 합니다.")


# ── 소스코드 복사 ─────────────────────────────────────────────────────────────

class CopyTest(unittest.TestCase):
    def test_src_directory_copied(self) -> None:
        copy_lines = [l for l in _lines() if re.match(r"^COPY\s", l.strip(), re.IGNORECASE)]
        self.assertTrue(
            any("src/" in l or "src " in l for l in copy_lines),
            "src/ 디렉터리를 COPY해야 합니다.",
        )

    def test_config_directory_copied(self) -> None:
        copy_lines = [l for l in _lines() if re.match(r"^COPY\s", l.strip(), re.IGNORECASE)]
        self.assertTrue(
            any("config/" in l or "config " in l for l in copy_lines),
            "config/ 디렉터리를 COPY해야 합니다.",
        )

    def test_requirements_pipeline_used(self) -> None:
        self.assertIn("requirements-pipeline.txt", _text())


# ── .dockerignore 내용 ────────────────────────────────────────────────────────

class DockerignoreTest(unittest.TestCase):
    def _content(self) -> str:
        return _DOCKERIGNORE.read_text(encoding="utf-8")

    def test_git_excluded(self) -> None:
        self.assertIn(".git/", self._content())

    def test_venv_excluded(self) -> None:
        self.assertIn(".venv/", self._content())

    def test_tests_excluded(self) -> None:
        self.assertIn("tests/", self._content())

    def test_env_file_excluded(self) -> None:
        self.assertIn(".env", self._content())

    def test_streamlit_excluded(self) -> None:
        self.assertIn(".streamlit/", self._content())

    def test_db_files_excluded(self) -> None:
        self.assertIn("*.db", self._content())


# ── requirements-pipeline.txt 내용 ───────────────────────────────────────────

class RequirementsPipelineTest(unittest.TestCase):
    def _content(self) -> str:
        return _REQ_PIPELINE.read_text(encoding="utf-8")

    def test_has_pykrx(self) -> None:
        self.assertIn("pykrx", self._content())

    def test_has_boto3(self) -> None:
        self.assertIn("boto3", self._content())

    def test_has_pandas(self) -> None:
        self.assertIn("pandas", self._content())

    def test_no_streamlit(self) -> None:
        self.assertNotIn("streamlit", self._content())

    def test_no_plotly(self) -> None:
        self.assertNotIn("plotly", self._content())


if __name__ == "__main__":
    unittest.main()
