# Codex Chat Lifecycle Naming

A small Codex Skill for stable task titles with exactly two lifecycle states and
an optional per-device marker:

```text
☀️项目或对象｜本阶段核心目标
✅️项目或对象｜本阶段核心目标

[DEVICE_EMOJI]☀️项目或对象｜本阶段核心目标
[DEVICE_EMOJI]✅️项目或对象｜本阶段核心目标
```

The device marker never replaces `☀️` or `✅️`. With no local configuration,
titles remain byte-for-byte compatible with earlier releases. The basename
remains stable, and completion still requires the full evidence gate.

## Contents

- `skills/chat-lifecycle-naming/SKILL.md` — lifecycle and fallback rules.
- `skills/chat-lifecycle-naming/scripts/chat_lifecycle.py` — offline helper with pure normalization/gate functions and small local-config commands. It never decides acceptance and never renames a task.
- `skills/chat-lifecycle-naming/scripts/installer.py` — dependency-free install, verify, uninstall, and backup rollback engine.
- `skills/chat-lifecycle-naming/scripts/*_windows.ps1` — Windows PowerShell 5.1/7 launchers with Python interpreter discovery.
- `tests/` — lifecycle, per-device configuration, CP936/Unicode, AGENTS preservation, install idempotency, uninstall, and rollback coverage.

## Per-device identity

`DEVICE_EMOJI` is optional machine-local identity, not lifecycle state or Git
metadata. The same Skill code can therefore produce `☀️...` on an unconfigured
machine or a two-layer title such as `🍎☀️...` after the user chooses a marker.
The Skill only recognizes the currently configured device marker plus the
supported lifecycle and legacy markers; it never guesses arbitrary emoji at the
start of a basename and never mass-renames historical tasks.

## Config location

Configuration is outside the Git repository:

```text
${CODEX_HOME:-$HOME/.codex}/chat-lifecycle-naming/config.json
```

On Windows this is
`$env:CODEX_HOME\chat-lifecycle-naming\config.json`, falling back to
`$HOME\.codex\chat-lifecycle-naming\config.json` when `CODEX_HOME` is unset.
Schema version 1 stores only the local marker; the default is empty:

```json
{
  "schema_version": 1,
  "device_emoji": ""
}
```

No hostname, username, IP address, credential, account identity, or Git identity
is stored.

## First-time setup

An existing config is preserved without prompting. A missing config reports
`CONFIG_STATUS=UNINITIALIZED`. Interactive first installation offers default or
custom identity once; unattended installation never blocks and continues with
the empty marker without creating a config. The next interactive Codex use can
initialize it.

From an installed Skill, inspect the effective configuration:

```bash
python3 "$HOME/.agents/skills/chat-lifecycle-naming/scripts/chat_lifecycle.py" config show
```

```powershell
py -3 "$HOME\.agents\skills\chat-lifecycle-naming\scripts\chat_lifecycle.py" config show
```

## Change device emoji

macOS/Linux:

```bash
python3 "$HOME/.agents/skills/chat-lifecycle-naming/scripts/chat_lifecycle.py" config set --device-emoji "🍎"
```

Windows:

```powershell
py -3 "$HOME\.agents\skills\chat-lifecycle-naming\scripts\chat_lifecycle.py" config set --device-emoji "🪟"
```

The change applies to later generated titles. If the user explicitly requests a
change during the current task, keep its basename and lifecycle state unchanged,
replace only the device marker, then require native title readback or `/rename`.

## Reset device emoji

macOS/Linux:

```bash
python3 "$HOME/.agents/skills/chat-lifecycle-naming/scripts/chat_lifecycle.py" config reset
```

Windows:

```powershell
py -3 "$HOME\.agents\skills\chat-lifecycle-naming\scripts\chat_lifecycle.py" config reset
```

Reset writes the initialized empty marker and restores the exact `☀️` and `✅️`
prefixes.

## Windows install

From the cloned repository in Windows PowerShell 5.1 or PowerShell 7:

```powershell
& .\skills\chat-lifecycle-naming\scripts\install_windows.ps1
& .\skills\chat-lifecycle-naming\scripts\verify_windows.ps1
```

The launcher discovers `py -3` first and then `python`; it does not assume `python3.exe`. The installer uses these locations:

```text
Skill:  $HOME\.agents\skills\chat-lifecycle-naming
AGENTS: $CODEX_HOME\AGENTS.md
Default when CODEX_HOME is unset: $HOME\.codex\AGENTS.md
```

It preserves existing AGENTS content, writes exactly one marked block, and creates a timestamped backup before a change. Repeating installation with identical inputs returns `INSTALL_STATUS=UNCHANGED` without adding another block or backup.

## Upgrade behavior

Installation and Skill upgrades never overwrite an existing device config.
Repeated installation preserves the same marker. Older machines with no config
remain backward compatible and report `CONFIG_STATUS=UNINITIALIZED` until an
interactive initialization or explicit `config set`/`config reset`.

The install output includes `BACKUP_PATH` and a `ROLLBACK_COMMAND`. Explicit operations are also available:

```powershell
& .\skills\chat-lifecycle-naming\scripts\uninstall_windows.ps1
& .\skills\chat-lifecycle-naming\scripts\rollback_windows.ps1 -BackupPath '<BACKUP_PATH>'
```

Uninstall removes only unchanged managed Skill files and the managed AGENTS block; modified or unrelated files are preserved. If a managed file was modified, it returns `UNINSTALL_STATUS=PARTIAL` and retains installation state for follow-up. Rollback is an explicit restore to the exact pre-install AGENTS and Skill snapshot recorded at `BACKUP_PATH`.

## Uninstall behavior

Normal uninstall preserves the machine-local device config so reinstalling does
not lose identity:

```powershell
& .\skills\chat-lifecycle-naming\scripts\uninstall_windows.ps1
```

Delete the config only with the explicit destructive option:

```powershell
& .\skills\chat-lifecycle-naming\scripts\uninstall_windows.ps1 -PurgeConfig
```

## macOS/Linux install

Place or link `skills/chat-lifecycle-naming` in `~/.agents/skills/chat-lifecycle-naming`. Put the same compact lifecycle trigger in the user Codex home `AGENTS.md`; when `CODEX_HOME` is unset, the default Codex home is `~/.codex`.

The Skill prefers the Codex App native `set_thread_title` capability and requires exact title readback. If the capability is absent or unreliable, it explicitly falls back to one user-confirmed `/rename` command and remains `SEMI_AUTO`.

## Verify

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall skills tests
```

The helper has no network dependency and is not a resident process.

Mac tests exercise the actual CP936-parent subprocess boundary, device markers,
and the complete install/idempotency/uninstall/rollback engine. PowerShell
launchers receive static contract checks because this Mac has no `pwsh`;
launcher execution and native Codex title behavior **requires real Windows Codex smoke test**.
A Mac result never substitutes for Windows A–T acceptance.

## License

No open-source license has been granted in this repository. Public visibility permits inspection; reuse remains subject to the copyright holder's permission.
