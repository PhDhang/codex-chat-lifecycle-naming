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
- `tests/test_chat_lifecycle_naming.py` — A–E regression coverage for new, blocked, complete, idempotent, and native/fallback behavior.

## Install

Place or link `skills/chat-lifecycle-naming` in a Codex user Skill directory such as `~/.agents/skills/chat-lifecycle-naming`. Add a short user-level `AGENTS.md` rule that triggers the Skill for new tasks and stage closure.

The Skill prefers the Codex App native `set_thread_title` capability and requires exact title readback. If the capability is absent or unreliable, it explicitly falls back to one user-confirmed `/rename` command and remains `SEMI_AUTO`.

## Verify

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The helper has no network dependency and is not a resident process.

## License

No open-source license has been granted in this repository. Public visibility permits inspection; reuse remains subject to the copyright holder's permission.
