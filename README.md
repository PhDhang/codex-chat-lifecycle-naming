# Codex Chat Lifecycle Naming

A small Codex Skill for stable task titles with exactly two lifecycle states:

```text
☀️项目或对象｜本阶段核心目标
✅️项目或对象｜本阶段核心目标
```

The basename remains stable. A task may change to `✅️` only after saved deliverables, fresh verification, acceptance, blocker clearance, transparent follow-ups, and the exact machine-readable completion fields all pass.

## Contents

- `skills/chat-lifecycle-naming/SKILL.md` — lifecycle and fallback rules.
- `skills/chat-lifecycle-naming/scripts/chat_lifecycle.py` — offline pure helper for prefix normalization and declared-field validation. It never decides acceptance and never renames a task.
- `skills/chat-lifecycle-naming/scripts/installer.py` — dependency-free install, verify, uninstall, and backup rollback engine.
- `skills/chat-lifecycle-naming/scripts/*_windows.ps1` — Windows PowerShell 5.1/7 launchers with Python interpreter discovery.
- `tests/` — lifecycle, CP936/Unicode, AGENTS preservation, install idempotency, uninstall, and rollback coverage.

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

The install output includes `BACKUP_PATH` and a `ROLLBACK_COMMAND`. Explicit operations are also available:

```powershell
& .\skills\chat-lifecycle-naming\scripts\uninstall_windows.ps1
& .\skills\chat-lifecycle-naming\scripts\rollback_windows.ps1 -BackupPath '<BACKUP_PATH>'
```

Uninstall removes only unchanged managed Skill files and the managed AGENTS block; modified or unrelated files are preserved. If a managed file was modified, it returns `UNINSTALL_STATUS=PARTIAL` and retains installation state for follow-up. Rollback is an explicit restore to the exact pre-install AGENTS and Skill snapshot recorded at `BACKUP_PATH`.

## macOS/Linux install

Place or link `skills/chat-lifecycle-naming` in `~/.agents/skills/chat-lifecycle-naming`. Put the same compact lifecycle trigger in the user Codex home `AGENTS.md`; when `CODEX_HOME` is unset, the default Codex home is `~/.codex`.

The Skill prefers the Codex App native `set_thread_title` capability and requires exact title readback. If the capability is absent or unreliable, it explicitly falls back to one user-confirmed `/rename` command and remains `SEMI_AUTO`.

## Verify

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall skills tests
```

The helper has no network dependency and is not a resident process.

Mac tests exercise the actual CP936-parent subprocess boundary and the complete install/idempotency/uninstall/rollback engine. PowerShell launchers receive static contract checks because this Mac has no `pwsh`; launcher execution and native Codex title behavior **requires real Windows Codex smoke test**. A Mac result never substitutes for Windows A–L acceptance.

## License

No open-source license has been granted in this repository. Public visibility permits inspection; reuse remains subject to the copyright holder's permission.
