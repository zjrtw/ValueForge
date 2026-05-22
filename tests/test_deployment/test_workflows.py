"""GitHub Actions workflow configuration checks."""
from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_DAILY = _ROOT / ".github" / "workflows" / "daily_pipeline.yml"
_TEST = _ROOT / ".github" / "workflows" / "test.yml"
_REQ = _ROOT / "requirements.txt"
_REQ_PIPELINE = _ROOT / "requirements-pipeline.txt"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class DailyPipelineWorkflowTest(unittest.TestCase):
    def test_workflow_exists(self) -> None:
        self.assertTrue(_DAILY.exists())

    def test_uses_project_python_version(self) -> None:
        self.assertIn('python-version: "3.11"', _text(_DAILY))
        self.assertNotIn('python-version: "3.13"', _text(_DAILY))

    def test_installs_pipeline_requirements(self) -> None:
        text = _text(_DAILY)
        self.assertIn("cache-dependency-path: requirements-pipeline.txt", text)
        self.assertIn("pip install -r requirements-pipeline.txt", text)

    def test_forwards_required_pipeline_secrets(self) -> None:
        text = _text(_DAILY)
        for name in [
            "DART_API_KEY",
            "R2_ENDPOINT_URL",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET_NAME",
            "KRX_ID",
            "KRX_PW",
        ]:
            self.assertIn(f"{name}:", text)
            self.assertIn(f"${{{{ secrets.{name} }}}}", text)


class TestWorkflowTest(unittest.TestCase):
    def test_workflow_exists(self) -> None:
        self.assertTrue(_TEST.exists())

    def test_uses_project_python_version(self) -> None:
        self.assertIn('python-version: "3.11"', _text(_TEST))
        self.assertNotIn('python-version: "3.13"', _text(_TEST))


class RequirementsSyncTest(unittest.TestCase):
    def test_dart_dependency_version_matches_pipeline(self) -> None:
        self.assertIn("opendartreader>=0.3.2", _text(_REQ))
        self.assertIn("opendartreader>=0.3.2", _text(_REQ_PIPELINE))
        self.assertNotIn("opendartreader>=0.2.3,<0.3.0", _text(_REQ))


if __name__ == "__main__":
    unittest.main()
