# GPTREADME

This file is a short handoff for future ChatGPT/Cursor sessions working on
this repository. Read `CLAUDE.md` for the long-form project guide, but treat
this as the quick state snapshot.

## What This Project Is

`vibedev` is a small Python package that turns:

```python
import vibedev
vibedev.prompt("build a calculator app")
```

into an autonomous Claude Code run inside an isolated workspace directory.
It wraps `claude-agent-sdk`; it does not reimplement the agent loop.

The package intentionally exposes a tiny public API from `vibedev/__init__.py`:

- `prompt`
- `set_permissions`
- `set_model`
- `set_workspace_root`
- `set_team`
- `get_config`

The user-facing idea is "vibe coding an app that can vibe code another app"
or "vibeception".

## Current Architecture

Solo mode (`set_team([])`) still uses one Claude agent with
`ORCHESTRATOR_SYSTEM_PROMPT` from `src/vibedev/prompts.py`.

Normal team mode is now code-owned when both `developer` and `tester` are
configured. If `business_analyst` is present, it runs as a coded planning
review stage:

1. Python reads or creates `.vibedev/plan.md` inside the target workspace.
2. Python appends the current prompt as a pending task if it is not already
   listed.
3. Python optionally runs `business_analyst` against the request and current
   plan.
4. Python parses the analyst's `## Proposed Tasks` section and appends missing
   tasks.
5. Python passes the full analyst brief to developer and tester as acceptance
   context.
6. Python selects the first `[ ]` task.
7. Python runs the developer agent on that one task.
8. Python runs the tester agent on the developer result.
9. Python parses `VIBEDEV_VERDICT: PASS` or `VIBEDEV_VERDICT: FAIL`.
10. On fail or missing verdict, Python sends the tester report back to the
   developer, up to `MAX_TEAM_FIX_ATTEMPTS`.
11. Only Python marks the plan item `[x]`, and only after tester pass.
12. If retries are exhausted, Python leaves the task pending and records a
   blocker in plan history.
13. A README-updater agent may update `README.md`, but Python restores
    `.vibedev/plan.md` if that agent touches it.

The old SDK-native manager prompt remains only as a fallback for unusual teams
that do not include both `developer` and `tester`.

## Important Files

- `src/vibedev/core.py` - public `prompt(...)`, SDK query driving, transcript
  logging, and the coded developer/tester workflow.
- `src/vibedev/roles.py` - business analyst/developer/tester role prompts plus
  fallback manager helpers.
- `src/vibedev/prompts.py` - solo orchestrator prompt.
- `src/vibedev/config.py` - global config and `set_*` functions.
- `src/vibedev/workspace.py` - workspace creation.
- `tests/test_smoke.py` - current regression suite.
- `CLAUDE.md` - detailed repo guidance.
- `docs/architecture.md` - human-readable architecture notes.
- `myapp.py` - local example driver.
- `vibedev-output/` - generated sample app workspace, not package source.

## Development Commands

```bash
pip install -e ".[dev]"
python -m pytest tests/test_smoke.py
python -m ruff check .
python -m compileall src tests
```

`claude-agent-sdk` shells out to the Claude Code CLI, so real `vibedev.prompt`
runs require the Claude Code CLI installed and authenticated.

## Current Known Environment Notes

- The PowerShell Conda startup error was fixed by guarding
  `C:\Users\zdune\Documents\WindowsPowerShell\profile.ps1` with `Test-Path`.
- Cursor's Python language server may still report `claude_agent_sdk` as
  unresolved in `roles.py`, even when pytest imports pass in the active shell.
- Installing dev extras may reveal local dependency tension around
  `starlette`, `sse-starlette`, and `fastapi`; the repository smoke tests pass.

## Recent Design Decisions

- Team workflow should not depend on a manager prompt remembering control
  flow. Coded invariants belong in `core.py`.
- Agents should own judgment, requirements critique, code, and test work, not
  task lifecycle state.
- `.vibedev/plan.md` is inside the generated workspace because team and solo
  runs need resumability.
- Transcript logs live in a sibling directory
  `<workspace>.vibedev-logs/` so generated agents do not read prior logs as
  ordinary workspace context.

## Things To Be Careful About

- Do not expand the public API casually; the tiny surface is deliberate.
- Do not revert user/generated changes in `vibedev-output/` unless asked.
- Do not reintroduce normal team lifecycle instructions into the manager
  prompt. The normal developer+tester lifecycle is code-owned.
- `business_analyst` may challenge the plan, but only Python applies its
  proposed tasks to `.vibedev/plan.md`.
- Keep long-running process rules in prompts. Agents must not leave dev
  servers, watchers, or daemons running.
- If changing `.vibedev/plan.md` behavior, update both `core.py` plan helpers
  and tests in `tests/test_smoke.py`.
