#!/usr/bin/env python3
"""Pure title normalization and declared lifecycle-field validation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata


IN_PROGRESS_PREFIX = "☀️"
COMPLETE_PREFIX = "✅️"
_PREFIX_TOKEN = r"(?:☀\ufe0f?|✅\ufe0f?|🚦\ufe0f?|🚥\ufe0f?)"
_LEADING_PREFIXES = re.compile(rf"^(?:\s*{_PREFIX_TOKEN})+\s*")
_VAGUE = {"新任务", "继续工作", "修改代码", "问题处理", "项目开发"}
CONFIG_SCHEMA_VERSION = 1
CONFIG_DIRECTORY = "chat-lifecycle-naming"
CONFIG_FILENAME = "config.json"
MAX_DEVICE_MARKER_CODEPOINTS = 16


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


@dataclass(frozen=True)
class GateDecision:
    phase_status: str
    chat_prefix: str
    basename: str
    title: str
    status_block: str


def default_config_path() -> Path:
    """Resolve the per-machine config outside the Git repository."""
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return (base / CONFIG_DIRECTORY / CONFIG_FILENAME).resolve()


def validate_device_emoji(value: str) -> str:
    """Validate a short Unicode device marker without guessing emoji semantics."""
    if not isinstance(value, str):
        raise ValueError("device_emoji must be a string")
    if value == "":
        return value
    if len(value) > MAX_DEVICE_MARKER_CODEPOINTS:
        raise ValueError(
            f"device_emoji must not exceed {MAX_DEVICE_MARKER_CODEPOINTS} code points"
        )
    if any(character.isspace() for character in value):
        raise ValueError("device_emoji must not contain whitespace")
    if "｜" in value:
        raise ValueError("device_emoji must not contain the basename separator: ｜")
    if re.search(_PREFIX_TOKEN, value):
        raise ValueError("device_emoji must not contain lifecycle markers")
    if any(
        unicodedata.category(character) in {"Cc", "Cf", "Cs"}
        and character != "\u200d"
        for character in value
    ):
        raise ValueError("device_emoji must not contain control characters")
    return value


def load_device_config(config_path: Path) -> tuple[str, str]:
    """Return CONFIG_STATUS and device marker; absence preserves legacy behavior."""
    if not config_path.is_file():
        return "UNINITIALIZED", ""
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config root must be a JSON object")
    if payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"config schema_version must be {CONFIG_SCHEMA_VERSION}"
        )
    device_emoji = validate_device_emoji(payload.get("device_emoji"))
    return "INITIALIZED", device_emoji


def write_device_config(config_path: Path, device_emoji: str) -> None:
    """Atomically persist the minimal per-machine configuration."""
    device_emoji = validate_device_emoji(device_emoji)
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "device_emoji": device_emoji,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{config_path.name}.", suffix=".tmp", dir=config_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def config_lines(status: str, device_emoji: str, config_path: Path) -> list[str]:
    return [
        f"CONFIG_STATUS={status}",
        f"DEVICE_EMOJI={device_emoji}",
        f"IN_PROGRESS_PREFIX={device_emoji}{IN_PROGRESS_PREFIX}",
        f"COMPLETE_PREFIX={device_emoji}{COMPLETE_PREFIX}",
        f"CONFIG_PATH={config_path}",
    ]


def initialize_device_config(config_path: Path, *, interactive: bool) -> list[str]:
    """Initialize once when interactive; never block unattended execution."""
    status, device_emoji = load_device_config(config_path)
    if status == "INITIALIZED" or not interactive:
        return config_lines(status, device_emoji, config_path)

    print("请选择本机任务标识：")
    print()
    print("1. 使用默认模式")
    print("   ☀️进行中")
    print("   ✅️完成")
    print()
    print("2. 增加本机 Emoji 标识")
    print("   例如：🍎 / 🪟 / 💻 / 🛰️")
    print()
    selection = input("请输入选项，直接回车使用默认：").strip()
    if selection in {"", "1"}:
        device_emoji = ""
    elif selection == "2":
        device_emoji = validate_device_emoji(input("请输入本机 Emoji 标识：").strip())
        if not device_emoji:
            raise ValueError("custom device_emoji must not be empty")
    else:
        raise ValueError("selection must be 1, 2, or empty")
    write_device_config(config_path, device_emoji)
    print()
    print("本机标题预览：")
    print()
    print(f"{device_emoji}{IN_PROGRESS_PREFIX}示例项目｜任务进行中")
    print(f"{device_emoji}{COMPLETE_PREFIX}示例项目｜任务已完成")
    return config_lines("INITIALIZED", device_emoji, config_path)


def normalize_basename(value: str, device_emoji: str = "") -> str:
    """Strip all known leading state markers and validate the stable basename."""
    device_emoji = validate_device_emoji(device_emoji)
    basename = value.strip()
    stripped_lifecycle = False
    previous = None
    while basename != previous:
        previous = basename
        if device_emoji and basename.startswith(device_emoji):
            remainder = basename[len(device_emoji) :].strip()
            if (
                remainder.startswith(device_emoji)
                or _LEADING_PREFIXES.match(remainder)
                or stripped_lifecycle
            ):
                basename = remainder
        updated = _LEADING_PREFIXES.sub("", basename).strip()
        if updated != basename:
            stripped_lifecycle = True
            basename = updated

    if not basename:
        raise ValueError("basename is empty after removing status prefixes")
    if basename.count("｜") != 1:
        raise ValueError("basename must contain exactly one full-width separator: ｜")
    subject, objective = (part.strip() for part in basename.split("｜", 1))
    if not subject or not objective:
        raise ValueError("basename subject and objective must both be non-empty")
    if subject in _VAGUE or objective in _VAGUE or basename in _VAGUE:
        raise ValueError("basename contains a prohibited vague name")
    return f"{subject}｜{objective}"


def normalize_title(basename: str, state: str, device_emoji: str = "") -> str:
    """Return a title with exactly one permitted prefix."""
    device_emoji = validate_device_emoji(device_emoji)
    normalized = normalize_basename(basename, device_emoji=device_emoji)
    if state == "IN_PROGRESS":
        return f"{device_emoji}{IN_PROGRESS_PREFIX}{normalized}"
    if state == "COMPLETE":
        return f"{device_emoji}{COMPLETE_PREFIX}{normalized}"
    raise ValueError("state must be IN_PROGRESS or COMPLETE")


def validate_gate(
    *,
    phase_status: str,
    acceptance: str | None,
    blockers: str,
    basename: str,
    next_action: str | None,
    device_emoji: str = "",
) -> GateDecision:
    """Validate fields already judged by the agent; do not infer completion."""
    device_emoji = validate_device_emoji(device_emoji)
    normalized = normalize_basename(basename, device_emoji=device_emoji)

    if phase_status == "COMPLETE":
        if acceptance != "PASS" or blockers != "NONE":
            raise ValueError("COMPLETE requires ACCEPTANCE=PASS and BLOCKERS=NONE")
        prefix = COMPLETE_PREFIX
        block = "\n".join(
            [
                "PHASE_STATUS=COMPLETE",
                f"CHAT_PREFIX={prefix}",
                f"CHAT_BASENAME={normalized}",
                "ACCEPTANCE=PASS",
                "BLOCKERS=NONE",
            ]
        )
    elif phase_status == "IN_PROGRESS":
        if not blockers.strip():
            raise ValueError("IN_PROGRESS requires BLOCKERS, using NONE when empty")
        if not next_action or not next_action.strip():
            raise ValueError("IN_PROGRESS requires NEXT_ACTION")
        prefix = IN_PROGRESS_PREFIX
        block = "\n".join(
            [
                "PHASE_STATUS=IN_PROGRESS",
                f"CHAT_PREFIX={prefix}",
                f"CHAT_BASENAME={normalized}",
                f"BLOCKERS={blockers.strip()}",
                f"NEXT_ACTION={next_action.strip()}",
            ]
        )
    else:
        raise ValueError("phase_status must be IN_PROGRESS or COMPLETE")

    return GateDecision(
        phase_status=phase_status,
        chat_prefix=prefix,
        basename=normalized,
        title=f"{device_emoji}{prefix}{normalized}",
        status_block=block,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize Codex task titles and validate declared lifecycle fields."
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=None,
        help="override the per-machine config path for testing",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    name = subparsers.add_parser("name", help="print one normalized title")
    name.add_argument("--state", choices=["IN_PROGRESS", "COMPLETE"], required=True)
    name.add_argument("--basename", required=True)

    block = subparsers.add_parser("block", help="validate and print one status block")
    block.add_argument(
        "--phase-status", choices=["IN_PROGRESS", "COMPLETE"], required=True
    )
    block.add_argument("--basename", required=True)
    block.add_argument("--acceptance")
    block.add_argument("--blockers", required=True)
    block.add_argument("--next-action")

    config = subparsers.add_parser("config", help="show or change device identity")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("show", help="show effective device identity")
    set_config = config_commands.add_parser("set", help="set the device marker")
    set_config.add_argument("--device-emoji", required=True)
    config_commands.add_parser("reset", help="restore the empty device marker")
    initialize = config_commands.add_parser(
        "init", help="initialize once, optionally prompting when interactive"
    )
    initialize.add_argument("--interactive", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        config_path = (args.config_path or default_config_path()).expanduser().resolve()
        if args.command == "config":
            if args.config_command == "show":
                status, device_emoji = load_device_config(config_path)
                lines = config_lines(status, device_emoji, config_path)
            elif args.config_command == "set":
                device_emoji = validate_device_emoji(args.device_emoji)
                write_device_config(config_path, device_emoji)
                lines = config_lines("INITIALIZED", device_emoji, config_path)
            elif args.config_command == "reset":
                write_device_config(config_path, "")
                lines = config_lines("INITIALIZED", "", config_path)
            else:
                lines = initialize_device_config(
                    config_path, interactive=args.interactive
                )
            print("\n".join(lines))
            return 0

        _, device_emoji = load_device_config(config_path)
        if args.command == "name":
            print(normalize_title(args.basename, args.state, device_emoji=device_emoji))
        else:
            decision = validate_gate(
                phase_status=args.phase_status,
                acceptance=args.acceptance,
                blockers=args.blockers,
                basename=args.basename,
                next_action=args.next_action,
                device_emoji=device_emoji,
            )
            print(decision.status_block)
    except (EOFError, OSError, ValueError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
