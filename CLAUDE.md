# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this package is

`vibedev` is a thin Python package that turns a one-line user prompt
(`vibedev.prompt("build a calculator app")`) into an autonomous Claude agent
that builds the requested project end-to-end inside an isolated workspace
directory. It is **a wrapper around the Claude Agent SDK**
(`claude-agent-sdk`), not a reimplementation of the agent loop. Heavy lifting
(tool dispatch, file editing, bash, subagents) is delegated to the SDK —
vibedev's job is configuration, workspace isolation, and a friendly public
surface.

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

## Public API (how users use vibedev)

The package exposes exactly five names from `vibedev/__init__.py`:

```python
import vibedev

vibedev.set_permissions("bypassPermissions")    # or acceptEdits / default / plan
vibedev.set_model("claude-opus-4-7")            # any model ID the Claude CLI accepts
vibedev.set_workspace_root("./vibedev-output")  # where projects land

workspace = vibedev.prompt(
    "build a hello-world flask app that returns JSON from /hello",
    workspace=None,   # None -> use the configured workspace_root; or pass a path to override
    quiet=False,      # True silences streaming output
)

vibedev.get_config()  # returns a copy of the current config dict
```

Mental model: the three `set_*` calls mutate module-level state. The next
`prompt()` reads whatever was last set. There's no `Vibedev` class, no context
manager, no per-call config object — global state is the deliberate UX, since
script-driven users want to configure once and fire many prompts.

`prompt()` blocks until the agent is done and returns the absolute `Path` of
the workspace, so the caller can open / inspect the generated code afterwards.

### CLI mirror

`vibedev "<prompt>" [--model ...] [--permissions ...] [--workspace-root ...] [--workspace ...] [--quiet]`
is just an argparse wrapper that calls the same `set_*` functions and then
`core.prompt`. The flags do not have separate semantics from the Python API.

### Defaults that are load-bearing

These three defaults define the package's UX. Don't change them casually:

- `permission_mode="bypassPermissions"` — the experience is "fire and forget";
  any other default would force interactive prompts and break that. Workspace
  isolation is the safety net, not user confirmation.
- `workspace_root="./vibedev-output"` — not `cwd` (would pollute the user's
  project), not `tempfile` (users want to find their generated code without
  hunting). The dir is used **directly** with no timestamp subfolder, so
  re-running with the same root operates on whatever's already there. Drivers
  that want one folder per project should override `workspace=` per call or
  call `set_workspace_root(...)` before each `prompt()`.
- `model="claude-opus-4-7"` — the package targets agentic codegen quality over
  latency / cost. Cheaper models are available via `set_model(...)`; Haiku is
  fine for "hello world" prompts and dramatically cheaper.

## Architecture

The package is intentionally small — five modules under `src/vibedev/`:

- **`config.py`** — owns a single module-level dict (`_config`) and the `set_*`
  setters that mutate it. State is global on purpose (see "Public API" above).
  `set_permissions` validates against `_VALID_PERMISSIONS`; `set_model` /
  `set_workspace_root` reject empty strings. `get_config()` returns a **copy**
  (`dict(_config)`) so callers cannot bypass the setters by mutating the
  returned dict. The `Config` TypedDict and `PermissionMode` literal are the
  type contract.
- **`workspace.py`** — `ensure_workspace(path)` does `Path(path).expanduser()
  .resolve()` then `mkdir(parents=True, exist_ok=True)` and returns the
  absolute path. The agent is scoped to this directory via the SDK's `cwd`
  option, which is the only thing keeping a run from touching files
  elsewhere. There is intentionally **no timestamp nesting** — the configured
  `workspace_root` (or per-call `workspace=`) is used as-is. Re-running with
  the same path operates on whatever's already there.
- **`prompts.py`** — `ORCHESTRATOR_SYSTEM_PROMPT`. This is the single biggest
  lever on agent behavior; when iterating on output quality, edit this first.
  Current rules: plan briefly, implement, verify **without leaving long-running
  processes alive**, then write a short README inside the workspace.
- **`core.py`** — `prompt(...)` is the public entry point. It validates the
  user prompt, snapshots config via `get_config()`, resolves the workspace via
  `ensure_workspace(...)`, prints a 3-line header to stderr (unless `quiet`),
  and uses `anyio.run` to drive the async `_run`. `_run` builds a
  `ClaudeAgentOptions(cwd, permission_mode, model, system_prompt)` and
  iterates `claude_agent_sdk.query(...)`, streaming each message through
  `_print_message`. `_print_message` is deliberately loose-typed
  (`getattr`-based) so SDK message-shape changes don't break us; it
  intentionally **skips `total_cost_usd`** because that figure reports API
  pricing equivalents and is misleading for users on a Claude.ai subscription.
- **`cli.py`** — argparse wrapper that maps `--model` / `--permissions` /
  `--workspace-root` flags onto the same `set_*` functions before calling
  `core.prompt`. Registered as the `vibedev` console script via
  `[project.scripts]` in `pyproject.toml`.

### End-to-end flow of a single `vibedev.prompt(...)` call

1. User calls `vibedev.prompt("build X", workspace=None, quiet=False)`.
2. `core.prompt` validates the string is non-empty, snapshots config with
   `get_config()`, resolves workspace via `ensure_workspace(...)`.
3. `anyio.run(_run, ...)` bridges sync→async.
4. `_run` constructs `ClaudeAgentOptions` (with the workspace as `cwd` and
   `ORCHESTRATOR_SYSTEM_PROMPT` as the system prompt) and calls
   `claude_agent_sdk.query(prompt=user_prompt, options=options)`.
5. The SDK subprocesses the Claude Code CLI; the CLI runs the agent loop
   (tool calls, file edits, bash) inside the workspace dir.
6. The async iterator yields messages back; `_print_message` streams text /
   tool-use markers to stdout.
7. When the agent signals done, `_run` returns, `anyio.run` unblocks, and
   `prompt()` returns the workspace `Path`.

### Why a single orchestrator (for now)

There is one agent, not a custom multi-agent router. If the orchestrator
needs parallel work, it spawns SDK-native subagents — those are already
supported by `claude-agent-sdk` and cheaper than a hand-rolled coordinator.
Add a custom multi-agent layer only when a concrete v1 use case shows the
single-agent approach is the bottleneck.

### Runtime dependency: Claude Code CLI

`claude-agent-sdk` is a thin Python wrapper that subprocesses the
[Claude Code CLI](https://docs.claude.com/en/docs/claude-code). The CLI must
be installed and authenticated on the host machine — there's no way to use
this package with just an `ANTHROPIC_API_KEY` env var. Mention this in any
install / debug docs you touch.

### Long-running processes are the system's sharpest edge

The orchestrator prompt explicitly forbids leaving servers / watchers /
daemons running at the end of a run, because we cannot reliably reap them
from Python: they're grandchildren spawned by the Claude Code CLI's bash
tool, not direct children of our process. On Windows in particular, a
`flask run` left in the foreground will hold the parent terminal even after
`vibedev.prompt()` returns.

If you change `prompts.py`, preserve the "verify without leaving processes
alive" rules — use framework test clients (`app.test_client()`,
`TestClient`), direct CLI invocation, or a background-then-kill+curl
pattern. Never foreground dev servers. If you genuinely need a reaper, it
has to live in or below `claude-agent-sdk`, not in vibedev.

## Layout

```
src/vibedev/        # the package (config, workspace, prompts, core, cli)
tests/              # pytest suite, no network calls
myapp.py            # example driver script (Haiku, ./vibedev-output)
pyproject.toml      # hatchling build, src layout, console_scripts entry
```

`pyproject.toml` uses the `src/` layout deliberately — without it, `pytest`
would import `vibedev` from the working directory instead of the installed
package, masking packaging bugs. Always run tests against the editable
install, never against a bare PYTHONPATH hack.
