---
name: chat-lifecycle-naming
description: Use when a new independent Codex task, work package, or project stage starts, when a stage ends, or when deciding whether a task title may change from in progress to closed.
related: [verification-before-completion]
reads: [AGENTS.md]
---

# Chat Lifecycle Naming

Keep one stable basename per stage and change only its exact lifecycle prefix.

## When to Use

- A new independent Codex task, work package, or project stage starts.
- A stage reaches a stopping point and its title may need to remain in progress or become closed.
- A title contains repeated, mixed, or obsolete lifecycle markers.

## When Not to Use

- The user is continuing the same stage with only minor wording changes.
- A new independent work package should receive its own task instead of replacing an unrelated basename.
- Historical tasks are being considered for bulk cleanup; this Skill only handles the current and future tasks.

## Context Required

- The first effective task description and the stable basename derived from it.
- The native Codex task-title capability available in the current client, if any.
- Saved deliverables, fresh verification results, acceptance conditions, blockers, and disclosed follow-up work.

## Workflow

1. Derive `项目或对象｜本阶段核心目标` from the first effective task description. Aim for about 12–30 Chinese characters. Do not use `新任务`, `继续工作`, `修改代码`, `问题处理`, or `项目开发` as either title part.
2. From this Skill directory, run `python3 scripts/chat_lifecycle.py name --state IN_PROGRESS --basename '<basename>'`. The helper removes all leading `☀️`, `✅️`, `🚦`, and `🚥` markers and returns exactly one `☀️` prefix.
3. In Codex App, call native `set_thread_title` for the current task, then read back the task list or native title state and confirm the exact value. Never mass-rename historical tasks.
4. If the native tool is missing, errors, times out, or readback differs, put `建议任务名：☀️<basename>` at the top of the first response and tell the user to run `/rename ☀️<basename>`. Report `SEMI_AUTO`, never an automatic rename.
5. At the stage boundary, inspect actual evidence before declaring a status. The helper validates declared fields; it never decides whether work is complete and never renames a task.
6. For an incomplete stage, run `python3 scripts/chat_lifecycle.py block --phase-status IN_PROGRESS --basename '<basename>' --blockers '<blocker-or-NONE>' --next-action '<next action>'` and keep or restore `☀️<basename>`.
7. For a closed stage, run `python3 scripts/chat_lifecycle.py block --phase-status COMPLETE --basename '<basename>' --acceptance PASS --blockers NONE`. Only after the evidence gate passes, call `set_thread_title` with `✅️<basename>` and read back the exact title.
8. If completion rename or readback fails, put `建议改名：✅️<basename>` at the top and tell the user to run `/rename ✅️<basename>`; keep the implementation classification at `SEMI_AUTO`.

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

## Frameworks and Best Practices

- Use exactly two states: `☀️` for in progress and `✅️` for closed.
- Normalize repeated or mixed leading markers idempotently before applying the requested state.
- Keep the production chain minimal: user-level `AGENTS.md` triggers this Skill; the Skill prefers native `set_thread_title`; the script remains an offline, non-resident pure helper.
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
