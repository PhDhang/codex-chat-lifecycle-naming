import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_SOURCE = ROOT / "skills" / "chat-lifecycle-naming"
HELPER = SKILL_SOURCE / "scripts" / "chat_lifecycle.py"
INSTALLER = SKILL_SOURCE / "scripts" / "installer.py"


WINDOWS_STREAM_HARNESS = textwrap.dedent(
    r"""
    import io
    import os
    import runpy
    import sys

    target = sys.argv[1]
    force_tty = sys.argv[2] == "1"
    target_arguments = sys.argv[3:]
    input_bytes = sys.stdin.buffer.read()

    class SimulatedWindowsStdin(io.TextIOWrapper):
        def isatty(self):
            return force_tty

    stdin_bytes = io.BytesIO(input_bytes)
    stdout_bytes = io.BytesIO()
    stderr_bytes = io.BytesIO()
    sys.stdin = SimulatedWindowsStdin(
        stdin_bytes, encoding="gbk", errors="strict", newline=None
    )
    sys.stdout = io.TextIOWrapper(
        stdout_bytes, encoding="gbk", errors="strict", newline="\r\n"
    )
    sys.stderr = io.TextIOWrapper(
        stderr_bytes, encoding="gbk", errors="strict", newline="\r\n"
    )
    sys.argv = [target, *target_arguments]

    exit_code = 0
    try:
        runpy.run_path(target, run_name="__main__")
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        stdout_payload = stdout_bytes.getvalue()
        stderr_payload = stderr_bytes.getvalue()

    os.write(1, stdout_payload)
    os.write(2, stderr_payload)
    raise SystemExit(exit_code)
    """
)


def run_with_simulated_windows_streams(
    target, *arguments, input_bytes=b"", force_tty=False
):
    return subprocess.run(
        [
            sys.executable,
            "-c",
            WINDOWS_STREAM_HARNESS,
            str(target),
            "1" if force_tty else "0",
            *map(str, arguments),
        ],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def expected_config_output(status, device_emoji, config_path):
    return (
        f"CONFIG_STATUS={status}\n"
        f"DEVICE_EMOJI={device_emoji}\n"
        f"IN_PROGRESS_PREFIX={device_emoji}☀️\n"
        f"COMPLETE_PREFIX={device_emoji}✅️\n"
        f"CONFIG_PATH={config_path.resolve()}\n"
    ).encode("utf-8")


class WindowsIOBoundaryTests(unittest.TestCase):
    def test_C1_helper_machine_output_is_utf8_with_canonical_lf(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            cases = [
                (
                    (
                        "name",
                        "--state",
                        "IN_PROGRESS",
                        "--basename",
                        "测试项目｜Windows边界验证",
                    ),
                    "☀️测试项目｜Windows边界验证\n".encode("utf-8"),
                ),
                (
                    ("config", "show"),
                    expected_config_output("UNINITIALIZED", "", config),
                ),
                (
                    ("config", "set", "--device-emoji", "🪟"),
                    expected_config_output("INITIALIZED", "🪟", config),
                ),
                (
                    (
                        "name",
                        "--state",
                        "IN_PROGRESS",
                        "--basename",
                        "测试项目｜Windows边界验证",
                    ),
                    "🪟☀️测试项目｜Windows边界验证\n".encode("utf-8"),
                ),
                (
                    (
                        "name",
                        "--state",
                        "COMPLETE",
                        "--basename",
                        "测试项目｜Windows边界验证",
                    ),
                    "🪟✅️测试项目｜Windows边界验证\n".encode("utf-8"),
                ),
                (
                    ("config", "reset"),
                    expected_config_output("INITIALIZED", "", config),
                ),
            ]
            for arguments, expected in cases:
                with self.subTest(arguments=arguments):
                    result = run_with_simulated_windows_streams(
                        HELPER, "--config-path", config, *arguments
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)
                    self.assertTrue(result.stdout.endswith(b"\n"))
                    self.assertNotIn(b"\r\n", result.stdout)

    def test_C1_helper_stderr_is_utf8_with_canonical_lf(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            config = pathlib.Path(temp_directory) / "config.json"
            result = run_with_simulated_windows_streams(
                HELPER,
                "--config-path",
                config,
                "name",
                "--state",
                "IN_PROGRESS",
                "--basename",
                "无效标题",
            )
            self.assertEqual(result.returncode, 2)
            self.assertTrue(result.stderr.endswith(b"\n"))
            self.assertNotIn(b"\r\n", result.stderr)
            self.assertIn("ERROR=".encode("utf-8"), result.stderr)

    def test_C1_installer_status_output_is_utf8_with_canonical_lf(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            result = run_with_simulated_windows_streams(
                INSTALLER,
                "install",
                "--home",
                root / "home",
                "--codex-home",
                root / "codex-home",
                "--source-skill",
                SKILL_SOURCE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.endswith(b"\n"))
            self.assertNotIn(b"\r\n", result.stdout)
            self.assertIn(b"INSTALL_STATUS=CHANGED\n", result.stdout)
            self.assertIn(b"CONFIG_STATUS=UNINITIALIZED\n", result.stdout)

    def test_C2_utf8_pipe_initializes_each_supported_device_marker_exactly(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            for index, marker in enumerate(["🍎", "🪟", "🛰️", "🧑‍💻"]):
                with self.subTest(marker=marker):
                    config = root / str(index) / "config.json"
                    result = run_with_simulated_windows_streams(
                        HELPER,
                        "--config-path",
                        config,
                        "config",
                        "init",
                        "--interactive",
                        input_bytes=f"2\n{marker}\n".encode("utf-8"),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn(b"\r\n", result.stdout)
                    self.assertIn(
                        f"DEVICE_EMOJI={marker}\n".encode("utf-8"), result.stdout
                    )
                    self.assertEqual(
                        json.loads(config.read_text(encoding="utf-8"))["device_emoji"],
                        marker,
                    )

    def test_C2_utf8_pipe_roundtrips_required_unicode_text(self):
        payload = "🍎\n🪟\n🛰️\n🧑‍💻\n中文\n｜\n".encode("utf-8")
        boundary_probe = textwrap.dedent(
            f"""
            import importlib.util
            import sys

            spec = importlib.util.spec_from_file_location("boundary_helper", {str(HELPER)!r})
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            module.configure_utf8_stdio()
            sys.stdout.write(sys.stdin.read())
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", boundary_probe],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "gbk"},
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, payload)

    def test_C3_default_install_never_prompts_even_when_stdin_claims_tty(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            config = root / "codex-home" / "chat-lifecycle-naming" / "config.json"
            result = run_with_simulated_windows_streams(
                INSTALLER,
                "install",
                "--home",
                root / "home",
                "--codex-home",
                root / "codex-home",
                "--source-skill",
                SKILL_SOURCE,
                force_tty=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"CONFIG_STATUS=UNINITIALIZED\n", result.stdout)
            self.assertNotIn("请输入".encode("utf-8"), result.stdout)
            self.assertFalse(config.exists())

    def test_C3_explicit_interactive_install_accepts_utf8_pipe(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            config = root / "codex-home" / "chat-lifecycle-naming" / "config.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "install",
                    "--interactive-config",
                    "--home",
                    str(root / "home"),
                    "--codex-home",
                    str(root / "codex-home"),
                    "--source-skill",
                    str(SKILL_SOURCE),
                ],
                input="2\n🍎\n".encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONIOENCODING": "gbk"},
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(config.read_text(encoding="utf-8"))["device_emoji"],
                "🍎",
            )

    def test_C4_default_mode_uses_isolated_config_not_real_codex_home(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = pathlib.Path(temp_directory)
            real_config = root / "real-codex" / "chat-lifecycle-naming" / "config.json"
            real_config.parent.mkdir(parents=True)
            real_config.write_text(
                '{"schema_version": 1, "device_emoji": "🪟"}\n',
                encoding="utf-8",
            )
            isolated_config = root / "isolated" / "config.json"
            for state, expected in [
                ("IN_PROGRESS", "☀️项目｜默认模式\n"),
                ("COMPLETE", "✅️项目｜默认模式\n"),
            ]:
                with self.subTest(state=state):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(HELPER),
                            "--config-path",
                            str(isolated_config),
                            "name",
                            "--state",
                            state,
                            "--basename",
                            "项目｜默认模式",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env={
                            **os.environ,
                            "CODEX_HOME": str(root / "real-codex"),
                        },
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected.encode("utf-8"))
            self.assertFalse(isolated_config.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
