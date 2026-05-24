# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this package is

`vibedev` is a thin Python package that turns a one-line user prompt
(`vibedev.prompt("build a calculator app")`) into an autonomous Claude agent that
builds the requested project end-to-end inside an isolated workspace directory.
It is **a wrapper around the Claude Agent SDK** (`claude-agent-sdk`), not a
reimplementation of the agent loop. Heavy lifting (tool dispatch, file editing,
bash, subagents) is delegated to the SDK — vibedev's job is configuration,
workspace isolation, and a friendly public surface.

## Commands

```bash
# Editable install for development
pip install -e ".[dev]"

# Run tests
pytest                       # all tests
pytest tests/test_smoke.py   # one file
pytest -k workspace          # by keyword
pytest -x -vv                # stop on first failure, verbose

# Lint
ruff check .
ruff format .

# Try the CLI locally
vibedev "build a hello-world flask app"
```

## Architecture

The package is intentionally small — five modules under `src/vibedev/`:

- **`config.py`** — owns a single module-level dict (`_config`) and the `set_*`
  setters that mutate it. State is global on purpose: the user's mental model is
  `vibedev.set_permissions(...)` then `vibedev.prompt(...)`, with the second
  call reading whatever the first one set. `get_config()` returns a **copy** so
  callers cannot bypass the setters.
- **`workspace.py`** — `create_workspace(root)` produces a fresh timestamped
  subdirectory and handles same-second collisions with a numeric suffix. The
  agent is then scoped to this directory via the SDK's `cwd` option, which is
  the only thing keeping a run from touching files elsewhere.
- **`prompts.py`** — the orchestrator system prompt. This is the single biggest
  lever on agent behavior; when iterating on output quality, edit this first.
- **`core.py`** — `prompt(...)` is the public entry point. It resolves the
  workspace, snapshots config, and uses `anyio.run` to drive the async `_run`
  which calls `claude_agent_sdk.query(...)` and streams messages back to stdout.
  `_print_message` is deliberately loose-typed (`getattr`-based) so SDK message
  shape changes don't break us.
- **`cli.py`** — argparse wrapper that maps `--model` / `--permissions` /
  `--workspace-root` flags onto the same `set_*` functions before calling
  `core.prompt`. Registered as the `vibedev` console script via
  `[project.scripts]` in `pyproject.toml`.

### Why a single orchestrator (for now)

There is one agent, not a custom multi-agent router. If the orchestrator needs
parallel work, it spawns SDK-native subagents — those are already supported by
`claude-agent-sdk` and cheaper than a hand-rolled coordinator. Add a custom
multi-agent layer only when a concrete v1 use case shows the single-agent
approach is the bottleneck.

### Runtime dependency: Claude Code CLI

`claude-agent-sdk` is a thin Python wrapper that subprocesses the
[Claude Code CLI](https://docs.claude.com/en/docs/claude-code). The CLI must
be installed and authenticated on the host machine — there's no way to use this
package with just an `ANTHROPIC_API_KEY` env var. Mention this in any
install/debug docs you touch.

### Long-running processes are the system's sharpest edge

The orchestrator prompt explicitly forbids leaving servers / watchers / daemons
running at the end of a run, because we cannot reliably reap them from Python:
they're grandchildren spawned by the Claude Code CLI's bash tool, not direct
children of our process. On Windows in particular, a `flask run` left in the
foreground will hold the parent terminal even after `vibedev.prompt()` returns.

If you change `prompts.py`, preserve the "verify without leaving processes
alive" rules — use framework test clients, not foreground dev servers. If you
genuinely need a reaper, it has to live in or below `claude-agent-sdk`, not in
vibedev.

### Defaults that are load-bearing

- `permission_mode="bypassPermissions"` — the package's UX is "fire and forget";
  changing this default would break the core experience. Workspace isolation is
  the safety net, not interactive prompts.
- Workspace defaults under `./vibedev-output/`, not `cwd` and not `tempfile` —
  users want to find their generated code without hunting and without it
  landing inside their existing project tree.
- Model defaults to `claude-opus-4-7`. The package targets agentic codegen
  quality over latency/cost.

## Layout

```
src/vibedev/        # the package
tests/              # pytest suite, no network calls
pyproject.toml      # hatchling build, src layout, console_scripts entry
```

`pyproject.toml` uses the `src/` layout deliberately — without it, `pytest`
would import `vibedev` from the working directory instead of the installed
package, masking packaging bugs. Always run tests against the editable install,
never against a bare PYTHONPATH hack.
