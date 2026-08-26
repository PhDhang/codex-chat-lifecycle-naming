#!/usr/bin/env python3
"""Pure title normalization and declared lifecycle-field validation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
import sys


IN_PROGRESS_PREFIX = "☀️"
COMPLETE_PREFIX = "✅️"
_PREFIX_TOKEN = r"(?:☀\ufe0f?|✅\ufe0f?|🚦\ufe0f?|🚥\ufe0f?)"
_LEADING_PREFIXES = re.compile(rf"^(?:\s*{_PREFIX_TOKEN})+\s*")
_VAGUE = {"新任务", "继续工作", "修改代码", "问题处理", "项目开发"}


def configure_utf8_stdio() -> None:
    """Make CLI output deterministic when a parent process advertises CP936/GBK."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class GateDecision:
    phase_status: str
    chat_prefix: str
    basename: str
    title: str
    status_block: str


def normalize_basename(value: str) -> str:
    """Strip all known leading state markers and validate the stable basename."""
    basename = value.strip()
    previous = None
    while basename != previous:
        previous = basename
        basename = _LEADING_PREFIXES.sub("", basename).strip()

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


def normalize_title(basename: str, state: str) -> str:
    """Return a title with exactly one permitted prefix."""
    normalized = normalize_basename(basename)
    if state == "IN_PROGRESS":
        return f"{IN_PROGRESS_PREFIX}{normalized}"
    if state == "COMPLETE":
        return f"{COMPLETE_PREFIX}{normalized}"
    raise ValueError("state must be IN_PROGRESS or COMPLETE")


def validate_gate(
    *,
    phase_status: str,
    acceptance: str | None,
    blockers: str,
    basename: str,
    next_action: str | None,
) -> GateDecision:
    """Validate fields already judged by the agent; do not infer completion."""
    normalized = normalize_basename(basename)

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
        title=f"{prefix}{normalized}",
        status_block=block,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize Codex task titles and validate declared lifecycle fields."
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
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "name":
            print(normalize_title(args.basename, args.state))
        else:
            decision = validate_gate(
                phase_status=args.phase_status,
                acceptance=args.acceptance,
                blockers=args.blockers,
                basename=args.basename,
                next_action=args.next_action,
            )
            print(decision.status_block)
    except ValueError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
