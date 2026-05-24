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

The package exposes exactly six names from `vibedev/__init__.py`:

```python
import vibedev

vibedev.set_permissions("bypassPermissions")    # or acceptEdits / default / plan
vibedev.set_model("claude-opus-4-7")            # any model ID the Claude CLI accepts
vibedev.set_workspace_root("./vibedev-output")  # where projects land
vibedev.set_team(["developer", "tester"])       # opt into team mode (see "Team mode" below)

workspace = vibedev.prompt(
    "build a hello-world flask app that returns JSON from /hello",
    workspace=None,   # None -> use the configured workspace_root; or pass a path to override
    quiet=False,      # True silences streaming output
)

vibedev.get_config()  # returns a copy of the current config dict
```

Mental model: the four `set_*` calls mutate module-level state. The next
`prompt()` reads whatever was last set. There's no `Vibedev` class, no context
manager, no per-call config object — global state is the deliberate UX, since
script-driven users want to configure once and fire many prompts.

`prompt()` blocks until the agent is done and returns the absolute `Path` of
the workspace, so the caller can open / inspect the generated code afterwards.

### Team mode

`set_team([...])` opts into a multi-agent run. Pass a list of **subagent**
role names (currently `"developer"` and `"tester"`). When the list is
non-empty:

- The main agent runs a **manager** system prompt — it plans, delegates via
  the Task tool, and integrates results. It does *not* write code itself
  unless no developer is on the team.
- Each named role is exposed as a subagent via
  `ClaudeAgentOptions.agents`, so the manager can dispatch atomic tasks to it
  through the Task tool.

The `"manager"` role is **implicit** — it is always the main agent when a
team is configured, and `set_team(...)` rejects it if listed explicitly.
This avoids the manager-as-peer confusion: structurally the manager is the
orchestrator, not a team member.

**Duplicates are meaningful.** `set_team(["developer", "developer", "tester"])`
gives the manager **two distinct developer subagents** (named `developer`
and `developer-2` to the SDK) that it can dispatch to in parallel for
independent subtasks. The user only writes role names; the instance-naming
scheme is internal to `roles.py`. The manager prompt grows a parallelism
note whenever the team has more than one member.

**Per-role models.** Each list entry is either a bare role name (inherits the
main-agent model from `set_model(...)`) or a `(role, model)` tuple that
overrides just that instance. The forms mix freely:

```python
vibedev.set_model("claude-opus-4-7")    # the manager
vibedev.set_team([
    ("developer", "claude-haiku-4-5"),
    ("developer", "claude-haiku-4-5"),
    ("tester",    "claude-sonnet-4-6"),
])
```

The model string is passed straight to the SDK, so aliases (`"haiku"`,
`"sonnet"`, `"opus"`, `"inherit"`) work alongside full IDs. When at least one
subagent runs a different model from the manager, `build_manager_prompt`
annotates each instance with its model in the system prompt and adds a note
telling the manager to weight delegation decisions accordingly (don't ask a
Haiku subagent to do deep-reasoning work). When the team is homogeneous,
those annotations are omitted to keep the prompt clean.

Under the hood, `subagents_for(team, default_model)` uses
`dataclasses.replace(SUBAGENT_ROLES[role], model=model or default_model)`
to materialise a fresh `AgentDefinition` per instance — the registry holds
templates, not the live objects passed to the SDK.

When `set_team([])` (the default), team mode is off entirely: the main agent
runs the single-orchestrator prompt (`ORCHESTRATOR_SYSTEM_PROMPT`) and no
subagents are exposed. The non-team path is preserved bit-for-bit.

**On turns.** We do not set `max_turns` on either the main agent
(`ClaudeAgentOptions.max_turns`) or any subagent
(`AgentDefinition.maxTurns`). SDK defaults apply. Agents do not strictly
alternate — the manager produces a message that may contain one or more
Task tool calls, each Task spawns a subagent that runs its own internal
loop to completion, and only then does the manager produce its next
message. So "turns" is a per-agent concept, not a global round-robin.

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

The package is intentionally small — six modules under `src/vibedev/`:

- **`config.py`** — owns a single module-level dict (`_config`) and the `set_*`
  setters that mutate it. State is global on purpose (see "Public API" above).
  `set_permissions` validates against `_VALID_PERMISSIONS`; `set_model` /
  `set_workspace_root` reject empty strings; `set_team` validates against
  `_VALID_SUBAGENT_ROLES`, rejects `"manager"` explicitly, and de-dupes while
  preserving order. `get_config()` returns a **copy** (`dict(_config)` plus a
  fresh copy of the inner `team` list) so callers cannot bypass the setters
  by mutating the returned dict. The role-name set is duplicated here (not
  imported from `roles.py`) so this module stays importable without
  `claude_agent_sdk` — keeps config tests cheap and the CLI's `--help` fast.
  The `Config` TypedDict and `PermissionMode` literal are the type contract.
- **`workspace.py`** — `ensure_workspace(path)` does `Path(path).expanduser()
  .resolve()` then `mkdir(parents=True, exist_ok=True)` and returns the
  absolute path. The agent is scoped to this directory via the SDK's `cwd`
  option, which is the only thing keeping a run from touching files
  elsewhere. There is intentionally **no timestamp nesting** — the configured
  `workspace_root` (or per-call `workspace=`) is used as-is. Re-running with
  the same path operates on whatever's already there.
- **`prompts.py`** — `ORCHESTRATOR_SYSTEM_PROMPT`. The system prompt used
  when **no team is configured** — a single self-sufficient agent that
  plans, implements, verifies (without leaving long-running processes
  alive), and writes a short README. This is the biggest lever on
  no-team-mode behavior; when iterating on solo-run output quality, edit
  this first.
- **`roles.py`** — the team-mode prompt registry. Holds the static
  `DEVELOPER_PROMPT` and `TESTER_PROMPT`, the `SUBAGENT_ROLES` dict mapping
  role name → `claude_agent_sdk.AgentDefinition` *templates* (model=None),
  and two pure functions: `build_manager_prompt(team, default_model)` which
  renders the manager prompt with the current team listing baked in, and
  `subagents_for(team, default_model)` which materialises fresh
  `AgentDefinition` instances via `dataclasses.replace` so each subagent
  can carry its own model. Both functions take the manager's model as
  `default_model` so bare-role entries (no per-role override) inherit it.
  The "don't leave servers alive" rule is duplicated into the developer and
  tester prompts because in team mode they're the ones holding the bash
  tool, not the manager.
- **`core.py`** — `prompt(...)` is the public entry point. It validates the
  user prompt, snapshots config via `get_config()`, resolves the workspace via
  `ensure_workspace(...)`, prints a header to stderr (unless `quiet`), and
  uses `anyio.run` to drive the async `_run`. `_run` branches on
  `cfg["team"]`: if non-empty it builds `ClaudeAgentOptions` with the manager
  prompt and `agents=subagents_for(team)`; otherwise it falls back to the
  single-orchestrator path with `ORCHESTRATOR_SYSTEM_PROMPT`. It then iterates
  `claude_agent_sdk.query(...)`, streaming each message through
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

### Multi-agent layering: SDK-native, not hand-rolled

vibedev does not implement its own agent-to-agent router. The team-mode
manager dispatches to subagents through the **SDK's** Task tool, which is
already supported by `claude-agent-sdk` via `ClaudeAgentOptions.agents` and
is far cheaper than a hand-rolled coordinator (no extra process, no extra
turn loop, subagents inherit the manager's `cwd`). The role catalog in
`roles.py` is intentionally tiny — three named prompts (manager, developer,
tester) and a registry — because adding a custom coordination layer above
the SDK is exactly the wrong place to invest until a concrete use case
shows the SDK's primitives are the bottleneck.

Custom roles are deliberately **not** supported in v1. The role set is
closed (`developer`, `tester`) so the public surface stays small; if a user
wants finer control over prompts, they fork them in `roles.py`. Per-role
models *are* supported via the `(role, model)` tuple form of `set_team`
(see "Per-role models" above).

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
