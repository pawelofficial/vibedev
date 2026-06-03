# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`vibedev` is "agentic development as a Python package": you give it a natural-language prompt and it drives a multi-agent pipeline (powered by `claude-agent-sdk`) that designs, implements, and tests a small multi-file Python project for you. Generated code and logs are written to `./vibedev-output/`.

The public API is tiny — `vibedev.run(prompt)` (sync) / `vibedev.run_async(prompt)` (async). See `myapp.py` for the canonical usage example.

## Commands

This project uses a `.venv` in the repo root. There is no console-script entry point; you invoke it as a library.

- Run the pipeline: `python myapp.py` (edit the prompt string in that file), or `python -c "import vibedev; vibedev.run('Design a Foo class')"`
- Install (editable, with dev deps): `pip install -e ".[dev]"`
- Lint: `ruff check src` / `ruff format src`
- Tests: `pytest` — note `pyproject.toml` points `testpaths` at a `tests/` directory that does not yet exist, so there are currently no project unit tests. (`test.py` in the root is empty; the `pytest` runs that matter happen *inside* the pipeline, executed by the Tester agent against generated code.)

Running the pipeline requires Anthropic credentials in the environment (e.g. `ANTHROPIC_API_KEY`), read from `.env` / the shell by `claude-agent-sdk`.

## Architecture

The pipeline is a **lead-developer → developer → tester** loop, orchestrated in `src/vibedev/pipeline.py::run_pipeline`. Each design and implementation step is wrapped by a **challenger** (critic) agent that can push back before work moves on:

1. **Lead Developer** turns the user prompt into a `ProjectSpec` — a set of `FileSpec`s (path, components, `depends_on`), each holding `ComponentSpec`s (a class or function). Structured JSON only, no code. On the *initial* design a **Lead Developer Challenger** reviews cross-file coherence (missing/unnecessary files, circular or missing `depends_on`, interface mismatches) and the spec is revised until approved, up to `MAX_CHALLENGE_ITERATIONS`.
2. **Developer** implements the project **one file at a time, in dependency order** (`pipeline.topo_sort` → `build_project`), so each file's dependencies are already on disk for it to `Read`. Each file is reviewed by a **Developer Challenger** and revised until approved (again bounded by `MAX_CHALLENGE_ITERATIONS`). The developer writes a *new* file in full but makes *targeted edits* on revision.
3. **Tester** reads all files, writes pytest tests for every component, runs the whole suite, and returns a `TestReport` (`passed`, failed tests, missing features).
4. If tests fail, the report is fed back to the Lead Developer to revise the spec (this revision is **not** challenged — the tester is the critic) and the whole project is rebuilt, up to `MAX_ITERATIONS` (default 5, in `config.py`).

The two iteration budgets are distinct: `MAX_CHALLENGE_ITERATIONS` (default 2) bounds each challenge loop; `MAX_ITERATIONS` (default 5) bounds the outer test/revise loop.

Layered structure (each layer depends only on those below it):

- `__init__.py` — public `run`/`run_async`/`set_output_dir` facade; wraps the async pipeline with `asyncio.run`.
- `pipeline.py` — orchestration: `design_with_challenge` / `develop_with_challenge` (the challenge loops), `topo_sort` + `build_project` (dependency-ordered build), and the outer test/revise loop.
- `agents.py` — the role functions (`lead_developer`, `lead_developer_challenger`, `developer`, `developer_challenger`, `tester`), each a thin wrapper over `run_agent` that validates output into a Pydantic model.
- `runner.py` — `run_agent`: the single chokepoint that calls the SDK. Builds `ClaudeAgentOptions`, streams the `query()` response, enforces structured output via JSON Schema, logs the full conversation, and appends a human-readable block to the run's transcript. **All SDK interaction lives here** — change agent behavior, tooling, or model config through this function and `config.py`, not by calling the SDK elsewhere.
- `models.py` — the Pydantic contracts: `ProjectSpec` / `FileSpec` / `ComponentSpec` (the design), `ChallengeReport` (a challenger's `approved` + `remarks`), `DevResult`, and `TestReport`.
- `prompt_templates.py` — system prompts and prompt builders. `module_filename()` (CamelCase → snake_case) is now only a *naming hint* — real paths are explicit in each `FileSpec.path`; `test_filename(path)` keeps tests beside their module.
- `utils/logging.py` — three loggers: `PipelineLogger` (one structured JSON log per run + console progress), `TranscriptLogger` (one human-readable, ASCII transcript of the whole agent conversation per run; module-level singleton via `start_transcript`/`get_transcript`, written to by `run_agent`), and `ConversationLogger` (one raw log per agent session). All buffer in memory and write on `flush()` (the transcript appends per agent call).

### Key conventions

- **Structured output is enforced at the SDK layer.** `run_agent` passes each model's `model_json_schema()` as the SDK `output_format`; if the agent can't produce valid output the run raises `RuntimeError`. Validation happens again in `agents.py` via `Model.model_validate(...)`.
- **The `ProjectSpec.files` graph is built in dependency order.** `topo_sort` orders leaf-dependencies first, ignores deps on paths outside the project (stdlib/third-party), and raises `ValueError` on a cycle (a spec bug — better to fail than loop forever). A single class in one file is just a one-file, one-component `ProjectSpec`.
- **Agents run with a sandboxed cwd.** All agents execute with `cwd=config.OUTPUT_DIR` and `allowed_tools=["Read", "Edit", "Bash", "Write"]` (see `config.CONFIG`). Generated files therefore live in `vibedev-output/`, not the package source tree. The toolset is shared across roles; the developer relies on both `Write` (new files) and `Edit` (targeted revisions).
- **Models are per-role.** `config.DEFAULT_MODEL` (`claude-haiku-4-5`) backs every role; `config.ROLE_MODELS` overrides specific roles (the Lead Developer runs on a stronger model since it owns the hardest structured output — the whole nested `ProjectSpec`). `config.model_for(role)` resolves the two; `runner.run_agent` calls it. Structured-output *coercion* always uses `DEFAULT_MODEL` (reshaping text to JSON is cheap work).
- **`config.OUTPUT_DIR` / `LOGS_DIR` are module-level and created on import.** `set_output_dir()` reassigns them at runtime — when changing output location, go through that function so both dirs and their `mkdir` happen together.
