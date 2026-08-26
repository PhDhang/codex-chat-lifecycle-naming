import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_SOURCE = ROOT / "skills" / "chat-lifecycle-naming"
HELPER = SKILL_SOURCE / "scripts" / "chat_lifecycle.py"
INSTALLER = SKILL_SOURCE / "scripts" / "installer.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("chat_lifecycle_device", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_helper(config_path, *arguments, environment=None, input_text=None):
    return subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "--config-path",
            str(config_path),
            *arguments,
        ],
        input=None if input_text is None else input_text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )


def run_installer(home, codex_home, *arguments):
    return subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            *arguments,
            "--home",
            str(home),
            "--codex-home",
            str(codex_home),
            "--source-skill",
            str(SKILL_SOURCE),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def output_fields(result):
    return dict(
        line.split("=", 1)
        for line in result.stdout.decode("utf-8").splitlines()
        if "=" in line
    )


class DeviceEmojiAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = load_helper()

    def test_M_default_device_config_is_byte_compatible(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            show = run_helper(config, "config", "show")
            self.assertEqual(show.returncode, 0, show.stderr.decode("utf-8"))
            fields = output_fields(show)
            self.assertEqual(fields["CONFIG_STATUS"], "UNINITIALIZED")
            self.assertEqual(fields["DEVICE_EMOJI"], "")
            self.assertEqual(fields["IN_PROGRESS_PREFIX"], "☀️")
            self.assertEqual(fields["COMPLETE_PREFIX"], "✅️")
            self.assertFalse(config.exists())
            self.assertEqual(
                self.helper.normalize_title("项目｜阶段", "IN_PROGRESS"),
                "☀️项目｜阶段",
            )
            self.assertEqual(
                self.helper.normalize_title("项目｜阶段", "COMPLETE"),
                "✅️项目｜阶段",
            )

    def test_M_default_config_path_follows_codex_home(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            codex_home = pathlib.Path(temp_directory) / "custom-codex"
            environment = os.environ.copy()
            environment["CODEX_HOME"] = str(codex_home)
            result = subprocess.run(
                [sys.executable, str(HELPER), "config", "reset"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
            config = codex_home / "chat-lifecycle-naming" / "config.json"
            self.assertTrue(config.is_file())
            self.assertEqual(
                output_fields(result)["CONFIG_PATH"], str(config.resolve())
            )

    def test_N_custom_device_emoji_builds_two_layer_titles(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            set_result = run_helper(
                config, "config", "set", "--device-emoji", "🍎"
            )
            self.assertEqual(
                set_result.returncode, 0, set_result.stderr.decode("utf-8")
            )
            for state, expected in [
                ("IN_PROGRESS", "🍎☀️项目｜阶段"),
                ("COMPLETE", "🍎✅️项目｜阶段"),
            ]:
                result = run_helper(
                    config,
                    "name",
                    "--state",
                    state,
                    "--basename",
                    "项目｜阶段",
                )
                self.assertEqual(
                    result.returncode, 0, result.stderr.decode("utf-8")
                )
                self.assertEqual(result.stdout.decode("utf-8"), expected + "\n")

    def test_N_complete_gate_preserves_device_and_machine_fields(self):
        decision = self.helper.validate_gate(
            phase_status="COMPLETE",
            acceptance="PASS",
            blockers="NONE",
            basename="🍎☀️项目｜阶段",
            next_action=None,
            device_emoji="🍎",
        )
        self.assertEqual(decision.basename, "项目｜阶段")
        self.assertEqual(decision.chat_prefix, "✅️")
        self.assertEqual(decision.title, "🍎✅️项目｜阶段")
        self.assertIn("CHAT_PREFIX=✅️", decision.status_block)
        self.assertNotIn("CHAT_PREFIX=🍎", decision.status_block)

    def test_O_config_persists_as_minimal_schema(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            first = run_helper(config, "config", "set", "--device-emoji", "🍎")
            self.assertEqual(first.returncode, 0, first.stderr.decode("utf-8"))
            self.assertEqual(
                json.loads(config.read_text(encoding="utf-8")),
                {"schema_version": 1, "device_emoji": "🍎"},
            )
            show = run_helper(config, "config", "show")
            self.assertEqual(show.returncode, 0, show.stderr.decode("utf-8"))
            self.assertEqual(output_fields(show)["DEVICE_EMOJI"], "🍎")

    def test_O_first_use_interactive_initialization_previews_titles(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            initialized = run_helper(
                config,
                "config",
                "init",
                "--interactive",
                input_text="2\n🍎\n",
            )
            self.assertEqual(
                initialized.returncode, 0, initialized.stderr.decode("utf-8")
            )
            output = initialized.stdout.decode("utf-8")
            self.assertIn("本机标题预览", output)
            self.assertIn("🍎☀️示例项目｜任务进行中", output)
            self.assertIn("🍎✅️示例项目｜任务已完成", output)
            self.assertEqual(
                json.loads(config.read_text(encoding="utf-8"))["device_emoji"],
                "🍎",
            )

    def test_P_config_change_applies_immediately(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            self.assertEqual(
                run_helper(
                    config, "config", "set", "--device-emoji", "🍎"
                ).returncode,
                0,
            )
            changed = run_helper(
                config, "config", "set", "--device-emoji", "🛰️"
            )
            self.assertEqual(changed.returncode, 0, changed.stderr.decode("utf-8"))
            title = run_helper(
                config,
                "name",
                "--state",
                "IN_PROGRESS",
                "--basename",
                "项目｜阶段",
            )
            self.assertEqual(title.stdout.decode("utf-8"), "🛰️☀️项目｜阶段\n")

    def test_Q_config_reset_restores_default_prefixes(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            run_helper(config, "config", "set", "--device-emoji", "🍎")
            reset = run_helper(config, "config", "reset")
            self.assertEqual(reset.returncode, 0, reset.stderr.decode("utf-8"))
            fields = output_fields(reset)
            self.assertEqual(fields["CONFIG_STATUS"], "INITIALIZED")
            self.assertEqual(fields["DEVICE_EMOJI"], "")
            self.assertEqual(fields["IN_PROGRESS_PREFIX"], "☀️")
            self.assertEqual(fields["COMPLETE_PREFIX"], "✅️")
            self.assertEqual(
                json.loads(config.read_text(encoding="utf-8")),
                {"schema_version": 1, "device_emoji": ""},
            )

    def test_R_device_title_normalization_strips_only_current_device(self):
        inputs = [
            "🍎☀️测试项目｜会话命名",
            "🍎✅️测试项目｜会话命名",
            "☀️测试项目｜会话命名",
            "✅️测试项目｜会话命名",
            "🚦测试项目｜会话命名",
            "🚥测试项目｜会话命名",
            "🍎🍎✅️☀️测试项目｜会话命名",
        ]
        for value in inputs:
            with self.subTest(value=value):
                self.assertEqual(
                    self.helper.normalize_basename(value, device_emoji="🍎"),
                    "测试项目｜会话命名",
                )
        self.assertEqual(
            self.helper.normalize_basename(
                "🪟☀️测试项目｜会话命名", device_emoji="🍎"
            ),
            "🪟☀️测试项目｜会话命名",
        )
        self.assertEqual(
            self.helper.normalize_basename("AI项目｜测试", device_emoji="A"),
            "AI项目｜测试",
        )

    def test_S_install_and_uninstall_preserve_device_config(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            config = codex_home / "chat-lifecycle-naming" / "config.json"
            config.parent.mkdir(parents=True)
            original = '{\n  "schema_version": 1,\n  "device_emoji": "🪟"\n}\n'.encode(
                "utf-8"
            )
            config.write_bytes(original)

            first = run_installer(home, codex_home, "install")
            second = run_installer(home, codex_home, "install")
            verify = run_installer(home, codex_home, "verify")
            uninstall = run_installer(home, codex_home, "uninstall")

            for result in (first, second, verify, uninstall):
                self.assertEqual(
                    result.returncode, 0, result.stderr.decode("utf-8")
                )
            self.assertEqual(output_fields(first)["CONFIG_STATUS"], "INITIALIZED")
            self.assertEqual(output_fields(second)["DEVICE_EMOJI"], "🪟")
            self.assertEqual(output_fields(verify)["DEVICE_EMOJI"], "🪟")
            self.assertEqual(config.read_bytes(), original)

            purge = run_installer(home, codex_home, "uninstall", "--purge-config")
            self.assertEqual(purge.returncode, 0, purge.stderr.decode("utf-8"))
            self.assertFalse(config.exists())

    def test_S_noninteractive_install_keeps_missing_config_uninitialized(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            home = root / "home"
            codex_home = root / "codex-home"
            config = codex_home / "chat-lifecycle-naming" / "config.json"
            installed = run_installer(home, codex_home, "install")
            self.assertEqual(
                installed.returncode, 0, installed.stderr.decode("utf-8")
            )
            fields = output_fields(installed)
            self.assertEqual(fields["CONFIG_STATUS"], "UNINITIALIZED")
            self.assertEqual(fields["DEVICE_EMOJI"], "")
            self.assertFalse(config.exists())

    def test_T_unicode_device_emoji_and_cp936_output(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "gbk"
            for index, emoji in enumerate(["🍎", "🪟", "🛰️", "🧑‍💻"]):
                with self.subTest(emoji=emoji):
                    config = root / str(index) / "config.json"
                    set_result = run_helper(
                        config,
                        "config",
                        "set",
                        "--device-emoji",
                        emoji,
                        environment=environment,
                    )
                    self.assertEqual(
                        set_result.returncode,
                        0,
                        set_result.stderr.decode("utf-8"),
                    )
                    for state, lifecycle in [
                        ("IN_PROGRESS", "☀️"),
                        ("COMPLETE", "✅️"),
                    ]:
                        title = run_helper(
                            config,
                            "name",
                            "--state",
                            state,
                            "--basename",
                            "测试项目｜Windows验证",
                            environment=environment,
                        )
                        self.assertEqual(
                            title.returncode, 0, title.stderr.decode("utf-8")
                        )
                        self.assertEqual(
                            title.stdout.decode("utf-8"),
                            f"{emoji}{lifecycle}测试项目｜Windows验证\n",
                        )

    def test_device_marker_validation_rejects_ambiguous_or_unsafe_values(self):
        invalid = [
            " ",
            "a b",
            "line\nfeed",
            "device｜marker",
            "☀️",
            "✅️",
            "unsafe\u202emarker",
            "x" * 17,
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.helper.validate_device_emoji(value)

    def test_config_io_error_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            parent_file = pathlib.Path(temp_directory) / "not-a-directory"
            parent_file.write_text("occupied", encoding="utf-8")
            result = run_helper(
                parent_file / "config.json",
                "config",
                "set",
                "--device-emoji",
                "🍎",
            )
            self.assertEqual(result.returncode, 2)
            error = result.stderr.decode("utf-8")
            self.assertIn("ERROR=", error)
            self.assertNotIn("Traceback", error)

    def test_device_config_contract_is_documented_without_machine_value(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (SKILL_SOURCE / "SKILL.md").read_text(encoding="utf-8")
        uninstall = (
            SKILL_SOURCE / "scripts" / "uninstall_windows.ps1"
        ).read_text(encoding="utf-8")
        for required in [
            "Per-device identity",
            "First-time setup",
            "Change device emoji",
            "Reset device emoji",
            "Config location",
            "Upgrade behavior",
            "Uninstall behavior",
            "config show",
            "config set --device-emoji",
            "config reset",
        ]:
            self.assertIn(required, readme)
        for required in [
            "device marker",
            "CONFIG_STATUS=UNINITIALIZED",
            "config show",
            "name --state IN_PROGRESS",
            "name --state COMPLETE",
            "Never mass-rename historical tasks",
        ]:
            self.assertIn(required, skill)
        self.assertIn("PurgeConfig", uninstall)
        self.assertNotIn('"device_emoji": "🍎"', readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
