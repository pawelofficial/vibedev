# vibedev

Agentic development as a Python package. Give it a prompt, get a project.

```python
import vibedev
vibedev.prompt("build a calculator web app")
```

vibedev spins up Claude as an autonomous developer agent inside an isolated
workspace directory. By default, output lands in `./vibedev-output/` (created
if missing). Set `set_workspace_root(...)` or pass `workspace=` per call to
direct different projects to different folders.

## Install

```bash
pip install vibedev
```

You'll also need the [Claude Code CLI](https://docs.claude.com/en/docs/claude-code)
installed and authenticated — the underlying `claude-agent-sdk` shells out to it.

## Usage

```python
import vibedev

# defaults: model=claude-opus-4-7, permissions=bypassPermissions,
# workspace_root=./vibedev-output
vibedev.prompt("build a CLI todo app in Python with sqlite storage")

# tweak settings (module-level, so they persist for subsequent prompt() calls)
vibedev.set_permissions("acceptEdits")
vibedev.set_model("claude-sonnet-4-6")
vibedev.set_workspace_root("~/projects/vibedev-runs")
```

Or from the shell:

```bash
vibedev "build a calculator web app"
vibedev "a flask hello world" --permissions acceptEdits --model claude-sonnet-4-6
```

## Status

Early. The public surface is `vibedev.prompt(...)` plus the `set_*` configurators.

## Docs

- [`GPTREADME.md`](GPTREADME.md) — short handoff for future ChatGPT/Cursor sessions.
- [`docs/architecture.md`](docs/architecture.md) — architecture and workflow notes.
