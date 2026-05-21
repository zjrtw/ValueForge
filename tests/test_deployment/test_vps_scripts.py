"""VPS 설정 스크립트 유효성 검사 테스트.

실제 셸 실행 없이 스크립트 내용을 파싱하여 필수 명령·설정을 확인한다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_DEPLOY = _ROOT / "deployment"

_SETUP      = _DEPLOY / "setup.sh"
_CRON       = _DEPLOY / "cron_install.sh"
_LOGROTATE  = _DEPLOY / "logrotate.conf"


# ── 파일 존재 확인 ────────────────────────────────────────────────────────────

class DeploymentFilesExistTest(unittest.TestCase):
    def test_setup_sh_exists(self) -> None:
        self.assertTrue(_SETUP.exists())

    def test_cron_install_sh_exists(self) -> None:
        self.assertTrue(_CRON.exists())

    def test_logrotate_conf_exists(self) -> None:
        self.assertTrue(_LOGROTATE.exists())


# ── setup.sh 검증 ─────────────────────────────────────────────────────────────

class SetupShTest(unittest.TestCase):
    def _text(self) -> str:
        return _SETUP.read_text(encoding="utf-8")

    def test_has_bash_shebang(self) -> None:
        self.assertTrue(self._text().startswith("#!/"))

    def test_set_euo_pipefail(self) -> None:
        self.assertIn("set -euo pipefail", self._text())

    def test_root_check(self) -> None:
        self.assertIn("EUID", self._text())

    def test_installs_docker(self) -> None:
        self.assertIn("docker", self._text())

    def test_creates_app_user(self) -> None:
        self.assertIn("useradd", self._text())

    def test_app_user_is_valueforge(self) -> None:
        self.assertIn("valueforge", self._text())

    def test_clones_repository(self) -> None:
        self.assertIn("git clone", self._text())

    def test_references_env_file(self) -> None:
        self.assertIn(".env", self._text())

    def test_calls_cron_install(self) -> None:
        self.assertIn("cron_install.sh", self._text())

    def test_calls_logrotate_setup(self) -> None:
        self.assertIn("logrotate", self._text())

    def test_docker_image_build(self) -> None:
        self.assertIn("docker compose", self._text())
        self.assertIn("build", self._text())

    def test_idempotent_comments_or_checks(self) -> None:
        # 멱등성을 위한 존재 확인 패턴이 있어야 함
        text = self._text()
        has_check = (
            "if [[ -d" in text
            or "if [[ -f" in text
            or "if command -v" in text
            or "if id " in text
        )
        self.assertTrue(has_check, "멱등성 확인 조건문이 있어야 합니다.")

    def test_env_file_permissions(self) -> None:
        self.assertIn("chmod 600", self._text())

    def test_next_steps_instructions(self) -> None:
        # 설정 후 안내 메시지가 있어야 함
        text = self._text()
        self.assertTrue(
            "다음 단계" in text or "Next step" in text.lower(),
            "설정 완료 후 안내 메시지가 있어야 합니다.",
        )


# ── cron_install.sh 검증 ──────────────────────────────────────────────────────

class CronInstallShTest(unittest.TestCase):
    def _text(self) -> str:
        return _CRON.read_text(encoding="utf-8")

    def test_has_bash_shebang(self) -> None:
        self.assertTrue(self._text().startswith("#!/"))

    def test_set_euo_pipefail(self) -> None:
        self.assertIn("set -euo pipefail", self._text())

    def test_cron_runs_at_0800_utc(self) -> None:
        # "0 8 * * 1-5" 또는 동등한 표현
        self.assertIn("0 8 * * 1-5", self._text())

    def test_cron_runs_weekdays_only(self) -> None:
        self.assertIn("1-5", self._text())

    def test_runs_docker_compose_pipeline(self) -> None:
        text = self._text()
        self.assertIn("docker compose", text)
        self.assertIn("pipeline", text)

    def test_idempotent_removes_old_entry(self) -> None:
        # 기존 cron 항목 제거 후 재등록 패턴
        self.assertIn("grep -v", self._text())

    def test_redirects_output_to_log(self) -> None:
        self.assertIn(">>", self._text())
        self.assertIn(".log", self._text())

    def test_uses_crontab_command(self) -> None:
        self.assertIn("crontab", self._text())


# ── logrotate.conf 검증 ───────────────────────────────────────────────────────

class LogrotateConfTest(unittest.TestCase):
    def _text(self) -> str:
        return _LOGROTATE.read_text(encoding="utf-8")

    def test_targets_valueforge_logs(self) -> None:
        self.assertIn("valueforge", self._text())
        self.assertIn(".log", self._text())

    def test_daily_rotation(self) -> None:
        self.assertIn("daily", self._text())

    def test_rotation_count(self) -> None:
        # rotate N 지정 (최소 7일)
        match = re.search(r"rotate\s+(\d+)", self._text())
        self.assertIsNotNone(match, "rotate 지시문이 있어야 합니다.")
        days = int(match.group(1))
        self.assertGreaterEqual(days, 7, "최소 7일 이상 보존해야 합니다.")

    def test_compress_enabled(self) -> None:
        self.assertIn("compress", self._text())

    def test_missingok(self) -> None:
        self.assertIn("missingok", self._text())

    def test_notifempty(self) -> None:
        self.assertIn("notifempty", self._text())

    def test_file_permissions_set(self) -> None:
        self.assertIn("create", self._text())


if __name__ == "__main__":
    unittest.main()
