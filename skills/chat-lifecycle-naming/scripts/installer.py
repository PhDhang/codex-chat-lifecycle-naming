#!/usr/bin/env python3
"""Dependency-free, idempotent installer for chat-lifecycle-naming."""

from __future__ import annotations

import argparse
import codecs
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SKILL_NAME = "chat-lifecycle-naming"
CONFIG_DIRECTORY = "chat-lifecycle-naming"
CONFIG_FILENAME = "config.json"
START_MARKER = "<!-- chat-lifecycle-naming:managed:start -->"
END_MARKER = "<!-- chat-lifecycle-naming:managed:end -->"
MANAGED_LINES = [
    START_MARKER,
    "## Task lifecycle naming",
    "",
    "- At the start of each new independent task, work package, or project stage, load and apply the user Skill `chat-lifecycle-naming` before substantive work.",
    "- At the end of each stage, apply that Skill's evidence and closure gate before writing the final response.",
    "- When the Skill requires a title change, prefer the Codex App native `set_thread_title` tool and verify the resulting title by reading it back.",
    "- If no native title tool is available, do not claim a rename; use the Skill's `/rename` fallback instructions.",
    END_MARKER,
]


def configure_utf8_stdio() -> None:
    """Use UTF-8 streams and canonical LF output across supported platforms."""
    reconfigure_stdin = getattr(sys.stdin, "reconfigure", None)
    if callable(reconfigure_stdin):
        reconfigure_stdin(encoding="utf-8", errors="strict", newline=None)
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict", newline="\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(source_skill: Path) -> list[Path]:
    return sorted(
        path
        for path in source_skill.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def decode_document(data: bytes) -> tuple[str, bool, str]:
    has_bom = data.startswith(codecs.BOM_UTF8)
    payload = data[len(codecs.BOM_UTF8) :] if has_bom else data
    text = payload.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text, has_bom, newline


def encode_document(text: str, has_bom: bool) -> bytes:
    payload = text.encode("utf-8")
    return codecs.BOM_UTF8 + payload if has_bom else payload


def managed_block(newline: str) -> str:
    return newline.join(MANAGED_LINES)


def marker_positions(text: str) -> tuple[int, int]:
    start_count = text.count(START_MARKER)
    end_count = text.count(END_MARKER)
    if start_count != end_count or start_count > 1:
        raise ValueError(
            "managed block markers are missing, duplicated, or unbalanced"
        )
    return start_count, end_count


def install_managed_block(data: bytes) -> bytes:
    text, has_bom, newline = decode_document(data)
    start_count, _ = marker_positions(text)
    block = managed_block(newline)
    if start_count == 1:
        start = text.index(START_MARKER)
        end = text.index(END_MARKER, start) + len(END_MARKER)
        updated = text[:start] + block + text[end:]
    elif not text:
        updated = block + newline
    else:
        updated = text
        if not updated.endswith(("\n", "\r")):
            updated += newline
        if not updated.endswith(newline * 2):
            updated += newline
        updated += block + newline
    return encode_document(updated, has_bom)


def remove_managed_block(data: bytes) -> bytes:
    text, has_bom, newline = decode_document(data)
    start_count, _ = marker_positions(text)
    if start_count == 0:
        return data
    start = text.index(START_MARKER)
    end = text.index(END_MARKER, start) + len(END_MARKER)
    prefix = text[:start]
    suffix = text[end:]
    if suffix.startswith(newline):
        suffix = suffix[len(newline) :]
    if prefix.endswith(newline * 2):
        prefix = prefix[: -len(newline)]
    return encode_document(prefix + suffix, has_bom)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_paths(
    args: argparse.Namespace,
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    home = Path(args.home).expanduser().resolve() if args.home else Path.home().resolve()
    codex_home_value = args.codex_home or os.environ.get("CODEX_HOME")
    codex_home = (
        Path(codex_home_value).expanduser().resolve()
        if codex_home_value
        else (home / ".codex").resolve()
    )
    source_skill = (
        Path(args.source_skill).expanduser().resolve()
        if args.source_skill
        else Path(__file__).resolve().parents[1]
    )
    skill_target = (home / ".agents" / "skills" / SKILL_NAME).resolve()
    agents_path = (codex_home / "AGENTS.md").resolve()
    state_path = codex_home / "state" / SKILL_NAME / "install.json"
    config_path = codex_home / CONFIG_DIRECTORY / CONFIG_FILENAME
    return (
        home,
        codex_home,
        source_skill,
        skill_target,
        agents_path,
        state_path,
        config_path,
    )


def validate_source(source_skill: Path) -> None:
    required = [
        source_skill / "SKILL.md",
        source_skill / "scripts" / "chat_lifecycle.py",
        source_skill / "scripts" / "installer.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"source Skill is incomplete: {', '.join(missing)}")


def skill_needs_update(source_skill: Path, skill_target: Path) -> bool:
    for source in source_files(source_skill):
        destination = skill_target / source.relative_to(source_skill)
        if not destination.is_file() or sha256(source) != sha256(destination):
            return True
    return False


def create_backup(
    codex_home: Path, agents_path: Path, skill_target: Path
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = codex_home / "backups" / SKILL_NAME / timestamp
    backup.mkdir(parents=True, exist_ok=False)
    agents_existed = agents_path.is_file()
    skill_existed = skill_target.is_dir()
    if agents_existed:
        shutil.copy2(agents_path, backup / "AGENTS.md.before")
    else:
        (backup / "AGENTS.md.was-absent").write_text("", encoding="utf-8")
    if skill_existed:
        shutil.copytree(skill_target, backup / "skill.before")
    else:
        (backup / "skill.was-absent").write_text("", encoding="utf-8")
    manifest = {
        "agents_existed": agents_existed,
        "agents_path": str(agents_path),
        "skill_existed": skill_existed,
        "skill_target": str(skill_target),
    }
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return backup


def copy_skill(source_skill: Path, skill_target: Path) -> dict[str, str]:
    installed: dict[str, str] = {}
    for source in source_files(source_skill):
        relative = source.relative_to(source_skill)
        destination = skill_target / relative
        if source.resolve() != destination.resolve():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        installed[relative.as_posix()] = sha256(source)
    return installed


def write_state(
    state_path: Path,
    *,
    agents_path: Path,
    skill_target: Path,
    backup: Path,
    installed: dict[str, str],
    agents_existed_before: bool,
) -> None:
    state = {
        "agents_path": str(agents_path),
        "skill_target": str(skill_target),
        "latest_backup": str(backup),
        "agents_existed_before": agents_existed_before,
        "installed_files": installed,
    }
    atomic_write(
        state_path,
        (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def run_helper(
    helper: Path,
    config_path: Path,
    *arguments: str,
    interactive: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    command = [
        sys.executable,
        str(helper),
        "--config-path",
        str(config_path),
        *arguments,
    ]
    if interactive:
        return subprocess.run(command, check=False)
    return subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def print_helper_output(result: subprocess.CompletedProcess[bytes]) -> None:
    if result.stdout:
        print(result.stdout.decode("utf-8"), end="")
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace")
        raise ValueError(f"device configuration failed: {message.strip()}")


def initialize_config(
    skill_target: Path, config_path: Path, *, interactive: bool
) -> None:
    helper = skill_target / "scripts" / "chat_lifecycle.py"
    result = run_helper(
        helper,
        config_path,
        "config",
        "init",
        *(["--interactive"] if interactive else []),
        interactive=interactive,
    )
    if not interactive:
        print_helper_output(result)
    elif result.returncode != 0:
        raise ValueError("interactive device configuration failed")


def config_fields(helper: Path, config_path: Path) -> dict[str, str]:
    result = run_helper(helper, config_path, "config", "show")
    if result.returncode != 0:
        raise ValueError(
            "device configuration validation failed: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    return dict(
        line.split("=", 1)
        for line in result.stdout.decode("utf-8").splitlines()
        if "=" in line
    )


def install(args: argparse.Namespace) -> int:
    (
        _,
        codex_home,
        source_skill,
        skill_target,
        agents_path,
        state_path,
        config_path,
    ) = resolve_paths(args)
    validate_source(source_skill)
    current_agents = agents_path.read_bytes() if agents_path.is_file() else b""
    desired_agents = install_managed_block(current_agents)
    agents_changed = desired_agents != current_agents
    skill_changed = skill_needs_update(source_skill, skill_target)
    if not agents_changed and not skill_changed:
        print("INSTALL_STATUS=UNCHANGED")
        print(f"SKILL_PATH={skill_target}")
        print(f"AGENTS_PATH={agents_path}")
        print("BACKUP_PATH=NONE")
        initialize_config(
            skill_target, config_path, interactive=args.interactive_config
        )
        return 0

    agents_existed_before = agents_path.is_file()
    backup = create_backup(codex_home, agents_path, skill_target)
    installed = copy_skill(source_skill, skill_target)
    if agents_changed:
        atomic_write(agents_path, desired_agents)
    write_state(
        state_path,
        agents_path=agents_path,
        skill_target=skill_target,
        backup=backup,
        installed=installed,
        agents_existed_before=agents_existed_before,
    )
    installed_installer = skill_target / "scripts" / "installer.py"
    print("INSTALL_STATUS=CHANGED")
    print(f"SKILL_PATH={skill_target}")
    print(f"AGENTS_PATH={agents_path}")
    print(f"BACKUP_PATH={backup}")
    print(
        "ROLLBACK_COMMAND="
        f'"{sys.executable}" "{installed_installer}" rollback --backup "{backup}"'
    )
    initialize_config(skill_target, config_path, interactive=args.interactive_config)
    return 0


def verify(args: argparse.Namespace) -> int:
    _, _, source_skill, skill_target, agents_path, _, config_path = resolve_paths(args)
    validate_source(source_skill)
    if not agents_path.is_file():
        raise ValueError(f"AGENTS.md is missing: {agents_path}")
    agents = agents_path.read_bytes()
    if install_managed_block(agents) != agents:
        raise ValueError("managed AGENTS block is missing or differs")
    if skill_needs_update(source_skill, skill_target):
        raise ValueError("installed Skill files are missing or differ")

    helper = skill_target / "scripts" / "chat_lifecycle.py"
    fields = config_fields(helper, config_path)
    device_emoji = fields["DEVICE_EMOJI"]
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "gbk"
    for state, lifecycle in [("IN_PROGRESS", "☀️"), ("COMPLETE", "✅️")]:
        result = subprocess.run(
            [
                sys.executable,
                str(helper),
                "--config-path",
                str(config_path),
                "name",
                "--state",
                state,
                "--basename",
                "测试项目｜Windows会话命名验证",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
        )
        expected = (
            f"{device_emoji}{lifecycle}测试项目｜Windows会话命名验证\n"
        ).encode("utf-8")
        if result.returncode != 0 or result.stdout != expected:
            raise ValueError(
                "installed helper failed the CP936-parent UTF-8 smoke test: "
                + result.stderr.decode("utf-8", errors="replace")
            )
    print("VERIFY_STATUS=PASS")
    print(f"SKILL_PATH={skill_target}")
    print(f"AGENTS_PATH={agents_path}")
    print(f"CONFIG_STATUS={fields['CONFIG_STATUS']}")
    print(f"DEVICE_EMOJI={device_emoji}")
    print(f"CONFIG_PATH={config_path}")
    print("CP936_UTF8_SMOKE=PASS")
    return 0


def uninstall(args: argparse.Namespace) -> int:
    _, _, source_skill, skill_target, agents_path, state_path, config_path = resolve_paths(
        args
    )
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.is_file()
        else {}
    )
    if agents_path.is_file():
        current = agents_path.read_bytes()
        updated = remove_managed_block(current)
        if updated != current:
            if not updated and not state.get("agents_existed_before", True):
                agents_path.unlink()
            else:
                atomic_write(agents_path, updated)

    installed_files = state.get("installed_files")
    if not isinstance(installed_files, dict):
        validate_source(source_skill)
        installed_files = {
            path.relative_to(source_skill).as_posix(): sha256(path)
            for path in source_files(source_skill)
        }
    preserved_modified: list[str] = []
    for relative, installed_hash in installed_files.items():
        path = skill_target / relative
        if not path.is_file():
            continue
        if sha256(path) == installed_hash:
            path.unlink()
        else:
            preserved_modified.append(relative)
    if skill_target.exists():
        directories = sorted(
            (path for path in skill_target.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            skill_target.rmdir()
        except OSError:
            pass
    if state_path.is_file() and not preserved_modified:
        state_path.unlink()
    if args.purge_config and config_path.is_file():
        config_path.unlink()
        try:
            config_path.parent.rmdir()
        except OSError:
            pass
    status = "PARTIAL" if preserved_modified else "PASS"
    print(f"UNINSTALL_STATUS={status}")
    print(f"PRESERVED_MODIFIED_FILES={len(preserved_modified)}")
    print(f"CONFIG_PRESERVED={'NO' if args.purge_config else 'YES'}")
    print(f"CONFIG_PATH={config_path}")
    return 0


def rollback(args: argparse.Namespace) -> int:
    _, _, _, skill_target, agents_path, state_path, _ = resolve_paths(args)
    if not args.backup:
        raise ValueError("rollback requires --backup")
    backup = Path(args.backup).expanduser().resolve()
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"backup manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if Path(manifest["agents_path"]).resolve() != agents_path:
        raise ValueError("backup AGENTS.md target does not match requested paths")
    if Path(manifest["skill_target"]).resolve() != skill_target:
        raise ValueError("backup Skill target does not match requested paths")

    if manifest["agents_existed"]:
        atomic_write(agents_path, (backup / "AGENTS.md.before").read_bytes())
    elif agents_path.exists():
        agents_path.unlink()
    if skill_target.exists():
        shutil.rmtree(skill_target)
    if manifest["skill_existed"]:
        shutil.copytree(backup / "skill.before", skill_target)
    if state_path.is_file():
        state_path.unlink()
    print("ROLLBACK_STATUS=PASS")
    print(f"BACKUP_PATH={backup}")
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", help="override the user home for testing")
    parser.add_argument("--codex-home", help="override CODEX_HOME")
    parser.add_argument("--source-skill", help="override the source Skill directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install, verify, uninstall, or roll back chat-lifecycle-naming."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    install_parser = commands.add_parser("install")
    add_common_arguments(install_parser)
    install_parser.add_argument(
        "--interactive-config",
        action="store_true",
        help="explicitly prompt for the optional per-machine device marker",
    )
    verify_parser = commands.add_parser("verify")
    add_common_arguments(verify_parser)
    uninstall_parser = commands.add_parser("uninstall")
    add_common_arguments(uninstall_parser)
    uninstall_parser.add_argument(
        "--purge-config",
        action="store_true",
        help="explicitly remove the otherwise preserved per-machine config",
    )
    rollback_parser = commands.add_parser("rollback")
    add_common_arguments(rollback_parser)
    rollback_parser.add_argument("--backup", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        return {
            "install": install,
            "verify": verify,
            "uninstall": uninstall,
            "rollback": rollback,
        }[args.command](args)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
