# Architecture

`vibedev` is a thin Python wrapper around `claude-agent-sdk`. Its job is to
configure Claude Code runs, isolate generated projects in a workspace, stream
output, write transcripts, and provide a tiny public API.

It deliberately does not implement the low-level agent loop. Claude Code still
owns tool execution, file editing, shell commands, and model interaction.

## Public Surface

The package exports six names:

```python
prompt
set_permissions
set_model
set_workspace_root
set_team
get_config
```

Configuration is module-level state. The user configures once with `set_*`,
then calls `prompt(...)`. There is no `Vibedev` class or per-call config
object.

## Runtime Flow

`vibedev.prompt(...)`:

1. Validates the prompt.
2. Snapshots config from `config.py`.
3. Resolves/creates the workspace via `workspace.py`.
4. Creates sibling transcript and conversation log paths.
5. Enters `_run(...)` in `core.py`.
6. Chooses solo mode, coded team mode, or fallback manager mode.
7. Streams every SDK message to stdout and the transcript log; records each
   stage prompt/response pair to the conversation log.
8. Returns the workspace path when complete.

Logs are written to `<workspace>.vibedev-logs/`, not inside the workspace. This
prevents generated agents from reading prior transcripts as ordinary project
files.

Each run writes two files:

- `<UTC>.log` is the full forensic transcript with SDK messages, thinking,
  tool calls, file reads, and bash output.
- `<UTC>.conversation.md` is the lightweight agent handoff log. It records the
  user prompt plus each coded workflow stage's prompt and final response, but
  omits tool reads and command output.

## Solo Mode

Solo mode is active when `set_team([])` is configured.

`core.py` runs a single SDK query with `ORCHESTRATOR_SYSTEM_PROMPT` from
`prompts.py`. The solo prompt owns planning, implementation, verification, and
README updates. It maintains `.vibedev/plan.md` by prompt instruction.

This path is intentionally simple and preserves the original wrapper design.

## Normal Team Mode

Normal team mode is active when the configured team contains both `developer`
and `tester`. Python also runs an internal ad hoc `knowledge_curator` at the
start of every coded team run. If `business_analyst` is configured, Python runs
it as a planning-review stage before choosing the next task.

This mode is code-owned in `core.py`, not manager-prompt-owned. The important
invariant is:

> A task is not complete until the tester returns `VIBEDEV_VERDICT: PASS`.

The coded flow is:

1. Load or create `.vibedev/plan.md`.
2. Append the current user prompt as a pending task if it is not already in the
   plan.
3. Write a draft `.vibedev/common_knowledge.md` with shared workspace context.
4. Run the ad hoc knowledge curator so it can inspect the workspace and return
   code-structure context.
5. Rewrite `.vibedev/common_knowledge.md` with the curator report included.
6. If `business_analyst` exists, run it against the user request, current
   plan, and a pointer to the common knowledge file.
7. Parse the analyst's `## Proposed Tasks` section and append missing tasks to
   the Python-owned plan.
8. Refresh common knowledge after analyst plan changes, preserving the curator
   report.
9. Pass the common knowledge path/purpose and the analyst brief to developer
   and tester as context.
10. Select the first pending task.
11. Run the developer agent on that task.
12. Run the tester agent on the developer report.
13. Parse the tester's verdict line:
   - `VIBEDEV_VERDICT: PASS`
   - `VIBEDEV_VERDICT: FAIL`
14. On pass, mark the task done in the plan.
15. On fail or missing verdict, feed the tester report back to the developer and
   retry.
16. After `MAX_TEAM_FIX_ATTEMPTS`, leave the task pending and record a blocker
   in plan history.
17. After pass, run a README updater agent with the common knowledge pointer.
18. Restore `.vibedev/plan.md` if the README updater agent edits it.

The business analyst, developer, and tester prompts in `roles.py` describe role
behavior only. They do not own plan lifecycle, task selection, checkoff, retry
policy, or blocker recording.

The analyst does not edit files. It returns structured Markdown with:

```markdown
## Missing Requirements
## Proposed Tasks
## Acceptance Criteria
## Risks
```

Python parses only `## Proposed Tasks` for plan changes. The full analyst brief
is passed into developer and tester prompts as acceptance context.

## Common Knowledge

Normal team mode writes:

```text
<workspace>/.vibedev/common_knowledge.md
```

This file is a generated shared context artifact for every role in the coded
team workflow. It includes:

- project goal and current request
- important paths such as the plan, common knowledge file, and README
- current plan tasks
- recent plan history
- discovered docs
- discovered tests
- notable project files
- team workflow rules

The `knowledge_curator` is an internal ad hoc role, not a public `set_team`
entry. It runs once at the beginning of each coded team deploy, reads relevant
workspace files when useful, and returns structured Markdown about code
structure only: modules, entry points, tests/tooling, extension points, and
structural notes. It should not summarize product requirements, acceptance
criteria, user stories, plan history, or broad project narrative. Python then
writes that report into `## Curated Project Context`. The agent does not edit
the file directly.

Python injects the common knowledge path and purpose into business analyst,
developer, tester, and README-updater prompts. It does not inject the full file
contents. Agents can decide when they need to read it, which keeps prompts
small and makes the file itself the source of shared context.

## Fallback Manager Mode

If `set_team(...)` is non-empty but does not include both `developer` and
`tester`, `core.py` uses the SDK-native manager prompt path.

This exists to keep unusual partial teams usable. It is not the primary path
for robust team orchestration.

## Plan File

Team mode uses:

```text
<workspace>/.vibedev/plan.md
```

Format:

```markdown
# vibedev plan

## Goal
<goal>

## Tasks
- [ ] Pending task
- [x] Completed task

## History
- 2026-05-24 - Request: ...
- 2026-05-24 - Completed: ...
- 2026-05-24 - Blocked: ...
```

In normal team mode, Python owns this file. If the format or semantics change,
update the helpers in `core.py` and the tests in `tests/test_smoke.py`.

## Role Prompts

`roles.py` contains:

- `DEVELOPER_PROMPT`
- `TESTER_PROMPT`
- `BUSINESS_ANALYST_PROMPT`
- `KNOWLEDGE_CURATOR_PROMPT`
- fallback manager prompt helpers
- `SUBAGENT_ROLES`

The knowledge curator is deliberately not in `SUBAGENT_ROLES`; users do not
configure it with `set_team`. It is a Python-owned ad hoc stage.

The business analyst should challenge the plan and produce acceptance criteria,
but it does not edit files or plan state directly.

The tester must end every report with exactly one verdict line. Python parses
that line to decide whether to continue or mark a task complete.

## Tests

The smoke suite currently covers:

- public API exports
- config setters and validation
- workspace creation
- team duplicates and per-role models
- business analyst role validation
- business analyst proposed-task parsing
- coded team workflow selection
- per-role model resolution
- tester verdict parsing
- team plan parsing/writing
- task completion and blocker recording
- plan restoration after README updater runs
- prompt-derived plan/common-knowledge compaction
- curated common knowledge insertion

Run:

```bash
python -m pytest tests/test_smoke.py
python -m ruff check .
python -m compileall src tests
```

## Non-Goals

- No custom low-level tool router.
- No broad public API.
- No custom roles in v1.
- No automatic cleanup of old transcript logs.
- No Python-side process reaper for grandchildren spawned by Claude Code.

## Sharp Edges

- The Claude Code CLI must be installed and authenticated for real agent runs.
- Long-running processes are dangerous, especially on Windows. Prompts must
  keep instructing agents to verify with test clients or commands that exit.
- The generated workspace is reused directly. That is intentional for
  resumability, but it means generated files may accumulate over time.
