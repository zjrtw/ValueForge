"""README.md 구조 및 내용 유효성 검사 테스트."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_README = _ROOT / "README.md"

# 문서 색인에 포함되어야 할 docs/ 파일
_REQUIRED_DOC_LINKS = [
    "docs/ARCHITECTURE.md",
    "docs/SCREENING.md",
    "docs/DATABASE.md",
    "docs/DEPLOYMENT.md",
    "docs/ENV_VARS.md",
    "docs/TASKS.md",
]

# 필수 섹션 헤더
_REQUIRED_SECTIONS = [
    "아키텍처",
    "빠른 시작",
    "Docker",
    "배포",
    "프로젝트 구조",
    "문서 색인",
]

# 필수 코드 블록 명령어
_REQUIRED_COMMANDS = [
    "git clone",
    "pip install",
    "cp .env.example",
    "pytest tests/",
    "streamlit run",
    "docker compose",
]


def _text() -> str:
    return _README.read_text(encoding="utf-8")


class ReadmeExistsTest(unittest.TestCase):
    def test_readme_exists(self) -> None:
        self.assertTrue(_README.exists())

    def test_readme_nonempty(self) -> None:
        self.assertGreater(len(_text()), 500)


class ReadmeStructureTest(unittest.TestCase):
    def test_has_title(self) -> None:
        self.assertTrue(_text().startswith("# ValueForge"))

    def test_has_required_sections(self) -> None:
        text = _text()
        for section in _REQUIRED_SECTIONS:
            self.assertIn(section, text, f"섹션 없음: {section}")

    def test_has_ci_badge(self) -> None:
        self.assertIn("badge.svg", _text())

    def test_has_python_version_badge(self) -> None:
        self.assertIn("python-3.11", _text())


class ReadmeDocLinksTest(unittest.TestCase):
    def test_all_required_docs_linked(self) -> None:
        text = _text()
        for doc in _REQUIRED_DOC_LINKS:
            self.assertIn(doc, text, f"문서 링크 없음: {doc}")

    def test_linked_docs_exist(self) -> None:
        text = _text()
        links = re.findall(r"\[.*?\]\((docs/[^)]+)\)", text)
        for link in links:
            path = _ROOT / link
            self.assertTrue(path.exists(), f"링크된 파일 없음: {link}")


class ReadmeSetupGuideTest(unittest.TestCase):
    def test_has_required_commands(self) -> None:
        text = _text()
        for cmd in _REQUIRED_COMMANDS:
            self.assertIn(cmd, text, f"명령어 없음: {cmd}")

    def test_env_var_section_uses_correct_var_names(self) -> None:
        text = _text()
        # 구버전 R2_ACCOUNT_ID 대신 R2_ENDPOINT_URL 사용
        self.assertIn("R2_ENDPOINT_URL", text)
        self.assertNotIn("R2_ACCOUNT_ID", text)

    def test_env_vars_md_linked(self) -> None:
        self.assertIn("ENV_VARS.md", _text())

    def test_dart_api_link_present(self) -> None:
        self.assertIn("opendart.fss.or.kr", _text())


class ReadmeArchitectureTest(unittest.TestCase):
    def test_pipeline_stages_mentioned(self) -> None:
        text = _text()
        for stage in ["Stage 1", "Stage 2", "Stage 3", "Stage 4"]:
            self.assertIn(stage, text)

    def test_screening_dimensions_mentioned(self) -> None:
        text = _text()
        for dim in ["가치", "품질", "안전", "성장", "모멘텀"]:
            self.assertIn(dim, text)

    def test_architecture_diagram_present(self) -> None:
        # ASCII 다이어그램 또는 코드블록
        self.assertIn("pykrx", _text())
        self.assertIn("DART", _text())
        self.assertIn("Streamlit", _text())

    def test_key_design_decisions_present(self) -> None:
        text = _text()
        self.assertIn("SQLite", text)
        self.assertIn("읽기 전용", text)


class ReadmeDeploymentTest(unittest.TestCase):
    def test_github_actions_mentioned(self) -> None:
        self.assertIn("GitHub Actions", _text())

    def test_streamlit_cloud_mentioned(self) -> None:
        self.assertIn("Streamlit Cloud", _text())

    def test_hetzner_mentioned(self) -> None:
        self.assertIn("Hetzner", _text())

    def test_secrets_setup_guidance(self) -> None:
        text = _text()
        self.assertIn("Secrets", text)

    def test_docker_compose_usage_shown(self) -> None:
        self.assertIn("docker compose run", _text())


class ReadmeProjectStructureTest(unittest.TestCase):
    def test_src_directories_listed(self) -> None:
        text = _text()
        for d in ["collectors", "pipeline", "screening", "ui", "storage"]:
            self.assertIn(d, text)

    def test_key_files_listed(self) -> None:
        text = _text()
        for f in ["app.py", "screening_params.yaml", "docker-compose.yml"]:
            self.assertIn(f, text)


if __name__ == "__main__":
    unittest.main()
