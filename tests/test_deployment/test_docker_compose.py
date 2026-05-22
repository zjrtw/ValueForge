"""docker-compose.yml 구조 유효성 검사 테스트.

Docker 실행 없이 YAML 파싱으로 서비스 구성을 확인한다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent.parent
_COMPOSE = _ROOT / "docker-compose.yml"
_DOCKERFILE_DASHBOARD = _ROOT / "Dockerfile.dashboard"


def _compose() -> dict:
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


# ── 파일 존재 확인 ────────────────────────────────────────────────────────────

class ComposeExistsTest(unittest.TestCase):
    def test_compose_file_exists(self) -> None:
        self.assertTrue(_COMPOSE.exists())

    def test_dockerfile_dashboard_exists(self) -> None:
        self.assertTrue(_DOCKERFILE_DASHBOARD.exists())

    def test_compose_is_valid_yaml(self) -> None:
        data = _compose()
        self.assertIsInstance(data, dict)


# ── 서비스 정의 확인 ──────────────────────────────────────────────────────────

class ServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.services: dict = _compose().get("services", {})

    def test_services_key_exists(self) -> None:
        self.assertIn("services", _compose())

    def test_pipeline_service_defined(self) -> None:
        self.assertIn("pipeline", self.services)

    def test_pipeline_test_service_defined(self) -> None:
        self.assertIn("pipeline-test", self.services)

    def test_dashboard_service_defined(self) -> None:
        self.assertIn("dashboard", self.services)

    def test_has_exactly_three_services(self) -> None:
        self.assertEqual(len(self.services), 3)


# ── pipeline 서비스 ───────────────────────────────────────────────────────────

class PipelineServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.svc: dict = _compose()["services"]["pipeline"]

    def test_uses_dockerfile(self) -> None:
        build = self.svc.get("build", {})
        self.assertIn("dockerfile", build)
        self.assertEqual(build["dockerfile"], "Dockerfile")

    def test_env_file_set(self) -> None:
        self.assertIn("env_file", self.svc)

    def test_logs_volume_mounted(self) -> None:
        volumes = self.svc.get("volumes", [])
        self.assertTrue(any("logs" in v for v in volumes))

    def test_restart_no(self) -> None:
        self.assertEqual(self.svc.get("restart"), "no")


# ── pipeline-test 서비스 ──────────────────────────────────────────────────────

class PipelineTestServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.svc: dict = _compose()["services"]["pipeline-test"]

    def test_max_tickers_limited(self) -> None:
        env = self.svc.get("environment", [])
        self.assertTrue(
            any("MAX_TICKERS=50" in str(e) for e in env),
            "pipeline-test는 MAX_TICKERS=50이어야 합니다.",
        )

    def test_no_upload_flag(self) -> None:
        cmd = self.svc.get("command", [])
        self.assertIn("--no-upload", cmd)

    def test_debug_log_level(self) -> None:
        env = self.svc.get("environment", [])
        self.assertTrue(any("DEBUG" in str(e) for e in env))


# ── dashboard 서비스 ──────────────────────────────────────────────────────────

class DashboardServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.svc: dict = _compose()["services"]["dashboard"]

    def test_uses_dashboard_dockerfile(self) -> None:
        build = self.svc.get("build", {})
        self.assertIn("Dockerfile.dashboard", build.get("dockerfile", ""))

    def test_port_8501_exposed(self) -> None:
        ports = self.svc.get("ports", [])
        self.assertTrue(
            any("8501" in str(p) for p in ports),
            "대시보드는 8501 포트를 노출해야 합니다.",
        )

    def test_restart_unless_stopped(self) -> None:
        self.assertEqual(self.svc.get("restart"), "unless-stopped")

    def test_healthcheck_defined(self) -> None:
        self.assertIn("healthcheck", self.svc)

    def test_healthcheck_uses_streamlit_health_endpoint(self) -> None:
        hc = self.svc.get("healthcheck", {})
        test_cmd = str(hc.get("test", ""))
        self.assertIn("health", test_cmd)


# ── Dockerfile.dashboard 내용 확인 ───────────────────────────────────────────

class DashboardDockerfileTest(unittest.TestCase):
    def _text(self) -> str:
        return _DOCKERFILE_DASHBOARD.read_text(encoding="utf-8")

    def test_uses_python_313(self) -> None:
        self.assertIn("3.13", self._text())

    def test_exposes_8501(self) -> None:
        self.assertIn("8501", self._text())

    def test_runs_streamlit(self) -> None:
        self.assertIn("streamlit", self._text())

    def test_installs_full_requirements(self) -> None:
        self.assertIn("requirements.txt", self._text())

    def test_non_root_user(self) -> None:
        self.assertIn("useradd", self._text())

    def test_copies_streamlit_config(self) -> None:
        self.assertIn(".streamlit", self._text())


if __name__ == "__main__":
    unittest.main()
