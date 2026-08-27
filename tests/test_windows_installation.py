import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_SOURCE = ROOT / "skills" / "chat-lifecycle-naming"
INSTALLER = SKILL_SOURCE / "scripts" / "installer.py"
SCRIPT_ROOT = SKILL_SOURCE / "scripts"
START_MARKER = "<!-- chat-lifecycle-naming:managed:start -->"
END_MARKER = "<!-- chat-lifecycle-naming:managed:end -->"


def run_installer(*arguments, environment=None):
    return subprocess.run(
        [sys.executable, str(INSTALLER), *map(str, arguments)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )


def output_fields(result):
    return dict(
        line.split("=", 1)
        for line in result.stdout.decode("utf-8").splitlines()
        if "=" in line
    )


class WindowsInstallationAcceptanceTests(unittest.TestCase):
    def test_H_install_preserves_existing_agents_and_uses_codex_home(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "custom-codex-home"
            agents = codex_home / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            original = b"\xef\xbb\xbf# Existing\r\nkeep=this\r\n"
            agents.write_bytes(original)

            result = run_installer(
                "install",
                "--home",
                home,
                "--codex-home",
                codex_home,
                "--source-skill",
                SKILL_SOURCE,
            )

            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            installed = agents.read_bytes()
            self.assertTrue(installed.startswith(original))
            text = installed.decode("utf-8-sig")
            self.assertEqual(text.count(START_MARKER), 1)
            self.assertEqual(text.count(END_MARKER), 1)
            self.assertFalse((home / ".agents" / "AGENTS.md").exists())
            self.assertTrue(
                (home / ".agents" / "skills" / "chat-lifecycle-naming" / "SKILL.md").is_file()
            )

    def test_I_repeated_install_is_idempotent_and_rollback_is_exact(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            agents = codex_home / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            original = "# Existing\nkeep=中文｜✅️\n".encode("utf-8")
            agents.write_bytes(original)
            common = (
                "--home",
                home,
                "--codex-home",
                codex_home,
                "--source-skill",
                SKILL_SOURCE,
            )

            first = run_installer("install", *common)
            self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
            first_bytes = agents.read_bytes()
            first_fields = output_fields(first)
            backup_path = pathlib.Path(first_fields["BACKUP_PATH"])
            backups_after_first = sorted((codex_home / "backups").rglob("manifest.json"))

            second = run_installer("install", *common)
            self.assertEqual(second.returncode, 0, second.stderr.decode("utf-8"))
            self.assertEqual(output_fields(second)["INSTALL_STATUS"], "UNCHANGED")
            self.assertEqual(agents.read_bytes(), first_bytes)
            self.assertEqual(
                sorted((codex_home / "backups").rglob("manifest.json")),
                backups_after_first,
            )

            rollback = run_installer("rollback", "--backup", backup_path, *common)
            self.assertEqual(
                rollback.returncode, 0, rollback.stderr.decode("utf-8")
            )
            self.assertEqual(agents.read_bytes(), original)
            self.assertFalse(
                (home / ".agents" / "skills" / "chat-lifecycle-naming").exists()
            )

    def test_I_uninstall_removes_only_managed_files_and_block(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            agents = codex_home / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            agents.write_text("# Existing\nkeep=yes\n", encoding="utf-8")
            common = (
                "--home",
                home,
                "--codex-home",
                codex_home,
                "--source-skill",
                SKILL_SOURCE,
            )
            installed_skill = home / ".agents" / "skills" / "chat-lifecycle-naming"

            install = run_installer("install", *common)
            self.assertEqual(install.returncode, 0, install.stderr.decode("utf-8"))
            extra = installed_skill / "user-note.txt"
            extra.write_text("preserve", encoding="utf-8")

            uninstall = run_installer("uninstall", *common)
            self.assertEqual(
                uninstall.returncode, 0, uninstall.stderr.decode("utf-8")
            )
            agents_text = agents.read_text(encoding="utf-8")
            self.assertEqual(agents_text, "# Existing\nkeep=yes\n")
            self.assertTrue(extra.is_file())
            self.assertFalse((installed_skill / "SKILL.md").exists())

    def test_I_uninstall_reports_partial_and_keeps_state_for_modified_managed_file(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            common = (
                "--home",
                home,
                "--codex-home",
                codex_home,
                "--source-skill",
                SKILL_SOURCE,
            )
            install = run_installer("install", *common)
            self.assertEqual(install.returncode, 0, install.stderr.decode("utf-8"))
            installed_skill = home / ".agents" / "skills" / "chat-lifecycle-naming"
            modified = installed_skill / "SKILL.md"
            modified.write_text("user modified\n", encoding="utf-8")

            uninstall = run_installer("uninstall", *common)
            self.assertEqual(
                uninstall.returncode, 0, uninstall.stderr.decode("utf-8")
            )
            fields = output_fields(uninstall)
            self.assertEqual(fields["UNINSTALL_STATUS"], "PARTIAL")
            self.assertEqual(fields["PRESERVED_MODIFIED_FILES"], "1")
            self.assertTrue(modified.is_file())
            self.assertTrue(
                (codex_home / "state" / "chat-lifecycle-naming" / "install.json").is_file()
            )

    def test_J_verify_runs_installed_cp936_utf8_smoke(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            common = (
                "--home",
                home,
                "--codex-home",
                codex_home,
                "--source-skill",
                SKILL_SOURCE,
            )
            install = run_installer("install", *common)
            self.assertEqual(install.returncode, 0, install.stderr.decode("utf-8"))

            verify = run_installer("verify", *common)
            self.assertEqual(verify.returncode, 0, verify.stderr.decode("utf-8"))
            fields = output_fields(verify)
            self.assertEqual(fields["VERIFY_STATUS"], "PASS")
            self.assertEqual(fields["CP936_UTF8_SMOKE"], "PASS")

    def test_H_default_codex_home_is_dot_codex_not_dot_agents(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            home = pathlib.Path(temp_directory) / "home"
            environment = os.environ.copy()
            environment.pop("CODEX_HOME", None)
            result = run_installer(
                "install",
                "--home",
                home,
                "--source-skill",
                SKILL_SOURCE,
                environment=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            self.assertTrue((home / ".codex" / "AGENTS.md").is_file())
            self.assertFalse((home / ".agents" / "AGENTS.md").exists())

    def test_I_malformed_managed_markers_fail_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            agents = codex_home / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            original = f"# Existing\n{START_MARKER}\ntruncated\n".encode("utf-8")
            agents.write_bytes(original)

            result = run_installer(
                "install",
                "--home",
                home,
                "--codex-home",
                codex_home,
                "--source-skill",
                SKILL_SOURCE,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("managed block markers", result.stderr.decode("utf-8"))
            self.assertEqual(agents.read_bytes(), original)

    def test_windows_launchers_discover_python_without_assuming_python3(self):
        common = (SCRIPT_ROOT / "windows_python.ps1").read_text(encoding="utf-8")
        for required in [
            "Windows_NT",
            'Name = "py"',
            '"-3"',
            'Name = "python"',
            "sys.version_info.major",
        ]:
            self.assertIn(required, common)
        for script, action in [
            ("install_windows.ps1", "install"),
            ("verify_windows.ps1", "verify"),
            ("uninstall_windows.ps1", "uninstall"),
        ]:
            text = (SCRIPT_ROOT / script).read_text(encoding="utf-8")
            self.assertIn("windows_python.ps1", text)
            self.assertIn(f'-Action "{action}"', text)
            self.assertNotIn("C:\\Users\\", text)
        install = (SCRIPT_ROOT / "install_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch] $InteractiveConfig", install)
        self.assertIn('if ($InteractiveConfig)', install)
        self.assertIn('"--interactive-config"', install)

    def test_windows_install_verify_uninstall_and_retest_contract_is_documented(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (SKILL_SOURCE / "SKILL.md").read_text(encoding="utf-8")
        for required in [
            "install_windows.ps1",
            "-InteractiveConfig",
            "non-interactive by default",
            "verify_windows.ps1",
            "uninstall_windows.ps1",
            "rollback_windows.ps1",
            "$CODEX_HOME",
            "$HOME\\.codex\\AGENTS.md",
            "UNINSTALL_STATUS=PARTIAL",
            "requires real Windows Codex smoke test",
        ]:
            self.assertIn(required, readme)
        for required in [
            "py -3",
            "python3",
            "CODEX_HOME",
            "managed block",
            "non-interactive by default",
            "-InteractiveConfig",
        ]:
            self.assertIn(required, skill)


if __name__ == "__main__":
    unittest.main(verbosity=2)
