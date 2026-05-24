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

`set_team([...])` opts into a multi-agent run. Pass a list of **role** names
(currently `"business_analyst"`, `"developer"`, and `"tester"`). When developer
and tester are configured, Python owns the lifecycle: read/create
`.vibedev/plan.md`, append the current request as a pending task when needed,
write a draft `.vibedev/common_knowledge.md`, run an internal ad hoc
`knowledge_curator` to inspect the workspace and return shared project context,
rewrite common knowledge with that report, pass agents a pointer to that file,
optionally run the business analyst against the current plan, append
analyst-proposed tasks, pick the next `[ ]` task, run developer, run tester,
parse the tester’s
`VIBEDEV_VERDICT`, send failures back to the developer, and mark `[x]` only
after tester pass. This is deliberately code-owned control flow rather than a
manager-prompt convention.

The SDK-native manager prompt still exists as a fallback for unusual teams
that do not include both `"developer"` and `"tester"`. The `"manager"` role
is **implicit** in that fallback and `set_team(...)` rejects it if listed
explicitly; users never configure it as a peer role.

**Duplicates are preserved in config.** `set_team(["developer", "developer",
"tester"])` records two developer entries and preserves their per-role model
overrides. The coded developer/tester loop currently uses the first matching
developer and tester for the serial verification loop; duplicate instances
remain available to the SDK-native manager fallback.

**Per-role models.** Each list entry is either a bare role name (inherits the
main-agent model from `set_model(...)`) or a `(role, model)` tuple that
overrides just that instance. The forms mix freely:

```python
vibedev.set_model("claude-opus-4-7")    # README updater / fallback manager model
vibedev.set_team([
    ("business_analyst", "claude-opus-4-7"),
    ("developer", "claude-haiku-4-5"),
    ("developer", "claude-haiku-4-5"),
    ("tester",    "claude-sonnet-4-6"),
])
```

The model string is passed straight to the SDK, so aliases (`"haiku"`,
`"sonnet"`, `"opus"`, `"inherit"`) work alongside full IDs. Bare role entries
inherit the main model from `set_model(...)`; tuple entries override just
that role.

When `set_team([])` (the default), team mode is off entirely: the main agent
runs the single-orchestrator prompt (`ORCHESTRATOR_SYSTEM_PROMPT`) and no
subagents are exposed. The non-team path is preserved bit-for-bit.

**On turns.** We do not set `max_turns`; SDK defaults apply. In the coded
developer/tester loop, each role is a separate `query(...)` call that runs to
completion before Python advances to the next step.

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
  alive), and writes a short README. It also owns the `.vibedev/plan.md`
  contract (see "Resumability" below): read-and-reconcile on startup,
  append new asks instead of overwriting, mark items off as they
  complete. This is the biggest lever on no-team-mode behavior; when
  iterating on solo-run output quality, edit this first.
- **`roles.py`** — the team-mode prompt registry. Holds the static
  `BUSINESS_ANALYST_PROMPT`, `KNOWLEDGE_CURATOR_PROMPT`, `DEVELOPER_PROMPT`,
  and `TESTER_PROMPT`, the
  `SUBAGENT_ROLES` dict mapping role name →
  `claude_agent_sdk.AgentDefinition` *templates* (model=None), and fallback
  manager helpers (`build_manager_prompt` / `subagents_for`) for teams that do
  not include both developer and tester. The normal team prompts do not own
  plan or task orchestration. The tester prompt must end with
  `VIBEDEV_VERDICT: PASS` or `VIBEDEV_VERDICT: FAIL`; `core.py` parses that
  machine-readable line to drive the fix/retest loop. `knowledge_curator` is
  deliberately not exposed through `set_team(...)`; Python runs it as an
  internal ad hoc stage at the start of coded team deploys.
- **`core.py`** — `prompt(...)` is the public entry point. It validates the
  user prompt, snapshots config via `get_config()`, resolves the workspace via
  `ensure_workspace(...)`, prepares a transcript log path via
  `_prepare_log_path(...)`, prints a header to stderr (unless `quiet`), and
  uses `anyio.run` to drive the async `_run`. `_run` branches on team shape:
  developer+tester teams use the coded lifecycle in
  `_run_coded_team_workflow`; solo mode uses `ORCHESTRATOR_SYSTEM_PROMPT`;
  other team shapes use the fallback SDK-native manager prompt.
  `_run_coded_team_workflow` owns plan creation/parsing/writing, common
  knowledge generation, optional analyst review, task selection, checkoff,
  blocker recording, and the dev/test retry policy. Every
  `claude_agent_sdk.query(...)` message is fanned out to (a) a
  `_TranscriptLogger` writing to `<workspace>.vibedev-logs/<UTC>.log` (a
  **sibling** of the workspace, deliberately outside it — see "Transcript
  logging" below) and (b) `_print_message` for live stdout (skipped when
  `quiet=True`).
  `_print_message` is deliberately loose-typed (`getattr`-based) so SDK
  message-shape changes don't break us; it intentionally **skips
  `total_cost_usd`** because that figure reports API pricing equivalents
  and is misleading for users on a Claude.ai subscription. The
  `_TranscriptLogger` mirrors the same loose-typed pattern and captures
  full block content (text, thinking, tool_use input as JSON, tool_result
  body with `tool_use_id`) — see "Transcript logging" below.
- **`cli.py`** — argparse wrapper that maps `--model` / `--permissions` /
  `--workspace-root` flags onto the same `set_*` functions before calling
  `core.prompt`. Registered as the `vibedev` console script via
  `[project.scripts]` in `pyproject.toml`.

### End-to-end flow of a single `vibedev.prompt(...)` call

1. User calls `vibedev.prompt("build X", workspace=None, quiet=False)`.
2. `core.prompt` validates the string is non-empty, snapshots config with
   `get_config()`, resolves workspace via `ensure_workspace(...)`.
3. `anyio.run(_run, ...)` bridges sync→async.
4. `_run` chooses solo, coded developer+tester team mode, or fallback manager
   mode based on config.
5. In coded team mode, Python updates `.vibedev/plan.md`, runs the ad hoc
   knowledge curator to enrich `.vibedev/common_knowledge.md`, sends one
   pending task through developer/tester `query(...)` calls, and updates plan
   state from the tester verdict.
6. The SDK subprocesses the Claude Code CLI for each `query(...)`; the CLI
   runs the agent loop (tool calls, file edits, bash) inside the workspace dir.
7. The async iterator yields messages back; `_print_message` streams text /
   tool-use markers to stdout.
8. When the selected workflow is done, `_run` returns, `anyio.run` unblocks,
   and `prompt()` returns the workspace `Path`.

### Multi-agent layering: coded lifecycle, SDK execution

vibedev owns the high-level team lifecycle in Python when both `developer`
and `tester` are configured. It reads/writes `.vibedev/plan.md`, writes
`.vibedev/common_knowledge.md` for shared project context, optionally runs
`business_analyst` to challenge the plan and propose tasks, selects the next
pending task, runs the developer agent, runs the tester agent, parses the
tester’s `VIBEDEV_VERDICT`, sends failures back to the developer, marks the
task complete only after tester pass, and records blockers on repeated failure.
The SDK still does the heavy agent execution for each role via `query(...)`;
vibedev owns the ordering, retry policy, and plan state transitions.

The SDK-native manager/Task-tool path remains as a fallback for unusual team
shapes, but the normal developer+tester path should not rely on a prompt to
remember that verification gates completion.

Custom roles are deliberately **not** supported in v1. The role set is
closed (`developer`, `tester`) so the public surface stays small; if a user
wants finer control over prompts, they fork them in `roles.py`. Per-role
models *are* supported via the `(role, model)` tuple form of `set_team`
(see "Per-role models" above).

### Resumability via `.vibedev/plan.md`

Because the workspace is reused as-is across runs (no timestamp nesting), a
second `vibedev.prompt(...)` call against the same workspace can pick up
where the previous one left off — *if* there's enough state on disk to
reconstruct progress. In normal developer+tester team mode, Python owns
`.vibedev/plan.md` (under the workspace) as a checklist of atomic tasks. Solo
mode still uses the solo orchestrator prompt for this behavior.

The contract:

- **First team run**: Python creates `.vibedev/plan.md` with one pending task
  for the current user prompt.
- **Subsequent team runs**: Python parses the plan, appends the current prompt
  as a new pending task if it is not already listed, and resumes from the top
  `[ ]`.
- **Business analyst review**: if configured, Python passes the user request
  current plan, and the common knowledge path/purpose to the analyst, parses only
  `## Proposed Tasks` for plan additions, and passes the full analyst brief
  into developer/tester prompts as acceptance context.
- **Common knowledge**: Python writes `.vibedev/common_knowledge.md` with the
  project goal, current request, plan summary, docs, tests, notable files, and
  workflow rules. Its path and purpose are injected into
  analyst/developer/tester/README-updater prompts; the full contents are not
  injected, so agents can read the file only when useful.
- **Team checkoff**: Python flips a task to `[x]` only after the tester returns
  `VIBEDEV_VERDICT: PASS`; repeated failures leave the task `[ ]` and append a
  blocker to `## History`.
- **Plan modification by the user**: the user can edit `.vibedev/plan.md`
  directly (the solo orchestrator prompt also accepts plan-modification
  requests phrased in natural language, e.g. "drop the Docker step").
- **File location is hidden**: `.vibedev/` rather than `PLAN.md` at the
  workspace root, so the plan file does not ship as a project artifact in
  the generated code.
- **Never delete the plan on success**: it documents history across runs.

For normal team mode this is **code-layer behavior** in `core.py`. If you
change the file path, format, parser, or checkoff rules, update the plan helper
functions and tests in `tests/test_smoke.py`. Solo mode remains prompt-layer
behavior in `prompts.py`.

A killed-mid-task run leaves the workspace partially mutated; the
reconciliation step on the next run is best-effort, not transactional.

### Transcript logging

Every `vibedev.prompt(...)` call writes a per-run transcript at
`<workspace>.vibedev-logs/<UTC-ISO-timestamp>.log` — a **sibling** directory
next to the workspace, deliberately not inside it. The file is created at
the top of `prompt()` (before the async work starts) so the stderr header
can announce its path and the user can `tail -f` it during a run.

**The log lives outside the workspace on purpose.** The agent's `cwd` is
the workspace, so if logs lived under `<workspace>/.vibedev/runs/` the
agent would list and read them as ordinary workspace files, which would
let one run's transcript leak into the next run's context (noisy, token-
expensive, and competes with the dedicated resumption signal in
`.vibedev/plan.md`). Moving logs to a sibling directory removes them from
the agent's view entirely — the user is the only consumer. The plan file
stays *inside* the workspace because the agent legitimately needs it; the
transcript log is the inverse.

The logger lives in `core.py` (`_TranscriptLogger`). It is intentionally
loose-typed via `getattr` so SDK message-shape changes don't break it —
same defensive pattern as `_print_message`. It captures **more** than
`_print_message` does: text, thinking, tool_use blocks with their full
JSON input, and tool_result blocks (with `tool_use_id` so calls and
results correlate). The point is post-hoc reconstruction — if the user
runs vibedev overnight, they should be able to read the log the next day
and understand exactly what files were edited, what bash commands ran,
and what came back.

**Always on, not configurable.** There is no `set_logging(False)` or
`log=False` kwarg — the public API stays small (see "Public API" above)
and the cost of an unwanted log file is trivially small (a few KB to a
few MB of text, sitting in a sibling directory). `quiet=True` only
silences stdout; the file log still gets written, because the two
concerns are orthogonal.

**Never truncated.** Tool results (bash output, file reads) are written
in full. Truncation hides exactly the information you need when something
went wrong. Old logs accumulate in `<workspace>.vibedev-logs/`; prune by
hand if you care.

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
