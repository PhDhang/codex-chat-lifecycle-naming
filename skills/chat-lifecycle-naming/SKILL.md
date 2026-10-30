---
name: chat-lifecycle-naming
description: Use for ChatGPT cloud and Codex task lifecycle naming, environment markers, stage closure, and explicitly requested historical conversation title cleanup.
related: [verification-before-completion]
reads: [AGENTS.md]
---

# Chat Lifecycle Naming

Keep one stable basename per stage. An optional machine-local device marker may
precede—but never replace—the exact lifecycle prefix.

## When to Use

- A new independent Codex task, work package, or project stage starts.
- A stage reaches a stopping point and its title may need to remain in progress or become closed.
- A title contains repeated, mixed, or obsolete lifecycle markers.

## When Not to Use

- The user is continuing the same stage with only minor wording changes.
- A new independent work package should receive its own task instead of replacing an unrelated basename.
- Historical cleanup without an explicit user request.

## Context Required

- The first effective task description and the stable basename derived from it.
- The native Codex task-title capability available in the current client, if any.
- Saved deliverables, fresh verification results, acceptance conditions, blockers, and disclosed follow-up work.

## Workflow

1. Derive `项目或对象｜本阶段核心目标` from the first effective task description. Aim for about 12–30 Chinese characters. Do not use `新任务`, `继续工作`, `修改代码`, `问题处理`, or `项目开发` as either title part.
2. Select an available Python 3 command: on Windows prefer `py -3`, then `python`; on macOS/Linux prefer `python3`, then `python`. Run `<python> scripts/chat_lifecycle.py config show`. Configuration lives at `${CODEX_HOME:-$HOME/.codex}/chat-lifecycle-naming/config.json` (the equivalent Codex home on Windows), never in the repository.
3. If the result is `CONFIG_STATUS=UNINITIALIZED`, ask once in an interactive Codex session whether to keep the default empty device marker or set a short Unicode marker. Save the answer with `config reset` or `config set --device-emoji '<marker>'`. In unattended work, do not block or write a config; use the empty marker and preserve legacy titles.
4. Run `<python> scripts/chat_lifecycle.py name --state IN_PROGRESS --basename '<basename>'`. The helper removes the current configured device marker plus all leading `☀️`, `✅️`, `🚦`, and `🚥` markers. It returns `[device marker]☀️<basename>`; with the empty default it returns the byte-compatible `☀️<basename>`.
5. In Codex App, discover whether native `set_thread_title` is available before calling it for the current task, then read back the task list or native title state and confirm the exact value. For explicitly requested historical cleanup, follow the batch workflow below.
6. If the native tool is missing, errors, times out, or readback differs, provide the exact proposed title for manual editing. Recommend `/rename <generated-title>` only when the current client is verified to support it. Report `SEMI_AUTO`, never an automatic rename.
7. At the stage boundary, inspect actual evidence before declaring a status. The helper validates declared fields; it never decides whether work is complete and never renames a task.
8. For an incomplete stage, run `<python> scripts/chat_lifecycle.py block --phase-status IN_PROGRESS --basename '<basename>' --blockers '<blocker-or-NONE>' --next-action '<next action>'`. Then run `<python> scripts/chat_lifecycle.py name --state IN_PROGRESS --basename '<basename>'` and keep that exact title.
9. For a closed stage, run `<python> scripts/chat_lifecycle.py block --phase-status COMPLETE --basename '<basename>' --acceptance PASS --blockers NONE`. Only after the evidence gate passes, run `<python> scripts/chat_lifecycle.py name --state COMPLETE --basename '<basename>'`, use that exact title with the same device marker and `✅️`, then read back the native title.

## Decision Gates

`COMPLETE` requires all six conditions:

1. Agreed deliverables exist and are saved.
2. Applicable tests, builds, checks, reviews, or human acceptance ran with recorded real results.
3. The stated objective and acceptance conditions are satisfied.
4. No critical blocker makes the deliverable unusable.
5. Non-blocking leftovers are disclosed as follow-up work.
6. The final summary explicitly contains `PHASE_STATUS=COMPLETE`.

Any failed or missing check, missing input, unverified result, unresolved key decision, partial implementation, permission problem, or critical blocker forces `IN_PROGRESS`. `COMPLETE` title replacement additionally requires the three exact fields `PHASE_STATUS=COMPLETE`, `ACCEPTANCE=PASS`, and `BLOCKERS=NONE`.

## Output Format

For an incomplete stage, end with:

```text
PHASE_STATUS=IN_PROGRESS
CHAT_PREFIX=☀️
CHAT_BASENAME=<basename>
BLOCKERS=<critical blockers or NONE>
NEXT_ACTION=<next action>
```

For a closed stage, end with:

```text
PHASE_STATUS=COMPLETE
CHAT_PREFIX=✅️
CHAT_BASENAME=<basename>
ACCEPTANCE=PASS
BLOCKERS=NONE
```

## Evidence and Source Rules

- Generated code, an answer, elapsed time, pause, or an agent self-report is not closure evidence.
- The normalization helper only validates text and declared gate fields; it cannot infer acceptance or prove a native rename.
- Claim an automatic rename only after exact native title readback. A suggested title or a successful helper run is insufficient.
- Keep the basename stable. Only a substantive objective change may justify a new stage, normally in a new task.
- A device marker change never changes the basename or lifecycle state. When the user explicitly changes it during the current task, rename only that current task and require the same native readback or `/rename` fallback. For explicitly requested historical cleanup, follow the batch workflow below.

## Frameworks and Best Practices

- Use exactly two states: `☀️` for in progress and `✅️` for closed.
- Normalize repeated or mixed leading markers idempotently before applying the requested state.
- Treat the title as `optional device marker + required lifecycle marker + basename`. Strip only the configured device marker; never guess arbitrary emoji or remove a normal basename character.
- Keep the production chain minimal: user-level `AGENTS.md` triggers this Skill; the Skill prefers native `set_thread_title`; the script remains offline and non-resident, with pure normalization/gate functions and only local config I/O.
- On Windows, install with `scripts/install_windows.ps1`. It writes one idempotent managed block to `$CODEX_HOME/AGENTS.md`, or to the default `.codex/AGENTS.md` when `CODEX_HOME` is unset, while the Skill itself remains under `.agents/skills/chat-lifecycle-naming`.
- The installer is non-interactive by default and leaves a missing config as `CONFIG_STATUS=UNINITIALIZED`. Only the explicit Windows `-InteractiveConfig` option may prompt during installation; otherwise the interactive Codex first-use flow in step 3 owns initialization.
- Installation preserves an existing per-device config. Normal uninstall also preserves it; only the explicit purge option removes it.
- Preserve unrelated user and project instructions; lifecycle naming is orthogonal to task execution.

## Failure Modes

- Changing to `✅️` without saved deliverables and fresh verification evidence.
- Treating helper output, a status block, or tool availability as proof that the visible title changed.
- Adding a second status prefix or using any completion symbol other than `✅️`.
- Rewriting the basename for minor wording changes or silently repurposing an old task.
- Claiming `FULL_AUTO` when the current Agent must manually invoke the title tool or when readback is unavailable.

## Related Skills

- `verification-before-completion` — requires fresh evidence before any completion claim.

## Examples

Start: `Hermes修复｜微信投递可靠性` becomes `☀️Hermes修复｜微信投递可靠性`.

Close: only after all gates pass, `☀️Hermes修复｜微信投递可靠性` becomes `✅️Hermes修复｜微信投递可靠性`; the basename remains byte-for-byte unchanged.

Normalize: `✅️☀️🚥测试项目｜会话命名验证` becomes `☀️测试项目｜会话命名验证` for an in-progress stage or `✅️测试项目｜会话命名验证` for a closed stage.

## Cloud and execution-environment rules

- Format new titles as `环境标识 + ☀️/✅️ + 项目或对象｜本阶段核心目标`.
- Use ☁️ for established cloud execution, 🍎 for established Mac execution, and 🪟 for established Windows execution. Preserve an existing user-selected marker.
- Identify the task execution environment, not the device viewing the conversation. Do not infer it from browser user-agent, Linux alone, or presence in a sidebar.
- When the user has chosen ☁️ for a cloud environment, use the existing helper's `config set --device-emoji '☁️'` in that environment. Do not overwrite unrelated local-device configuration. Installers retain their existing non-interactive behavior and empty-marker default.
- An isolated cloud deployment may use `--config-path <deployment-config.json>` before the helper subcommand. Keep runtime configuration outside this source repository; a packaged cloud skill may provide its own explicit default.
- Discover actual title tools or an authorized browser UI before attempting a rename. Installing this skill does not grant title API access or browser control.
- User login and agent access to the user's tab are distinct. An empty tool-visible tab list does not mean the user is logged out. Report the missing connection accurately; do not request another login without observing a sign-in wall.
- In ChatGPT, never assume `/rename` is supported. Without a usable title operation, report `SEMI_AUTO` and provide proposed titles, not a success claim.
- Persisting these rules in a skill or repository is not a ChatGPT long-term Memory write. Claim a Memory update only after a supported write succeeds.

## Explicit historical batch workflow

1. Confirm scope from the user's explicit request. Existing authorization in the conversation remains valid; do not ask again for the same scope.
2. Enumerate accessible conversations with stable identifiers, current titles, and known execution environments. Disclose incomplete coverage; memory summaries are not a complete inventory.
3. Read each conversation's closing evidence and apply all six completion gates above. Unknown or insufficient evidence stays ☀️, with uncertainty recorded. Age or generated files alone do not prove closure.
4. Prepare an old/new title mapping. Preserve each existing basename exactly, including titles without `｜`. The helper requires `｜` for new titles, so do not force legacy titles through it or silently rewrite their subjects.
5. Preserve known environment markers. Apply ☁️ only to established cloud tasks; do not relabel every visible conversation as cloud. Strip only known lifecycle markers and an explicitly identified environment marker; never arbitrary emoji.
6. Use an available authorized native tool or browser UI to change titles. Record exact readback per conversation and distinguish successful, failed, skipped, and unverified items. If a write's result is uncertain, inspect before retrying.
7. If mutation capability is absent, stop at proposed mappings and state that zero titles were changed. Skill installation and title generation never count as actual renaming.

Examples: `☁️☀️会话命名｜云端规则适配`, `🍎☀️仿真工具｜本地调试`, `🪟✅️测试平台｜阶段验收`. Completion examples apply only after the evidence gate passes.
