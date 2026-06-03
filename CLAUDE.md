# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`vibedev` is "agentic development as a Python package": you give it a natural-language prompt and it drives a multi-agent pipeline (powered by `claude-agent-sdk`) that designs, implements, and tests a Python class for you. Generated code and logs are written to `./vibedev-output/`.

The public API is tiny — `vibedev.run(prompt)` (sync) / `vibedev.run_async(prompt)` (async). See `myapp.py` for the canonical usage example.

## Commands

This project uses a `.venv` in the repo root. There is no console-script entry point; you invoke it as a library.

- Run the pipeline: `python myapp.py` (edit the prompt string in that file), or `python -c "import vibedev; vibedev.run('Design a Foo class')"`
- Install (editable, with dev deps): `pip install -e ".[dev]"`
- Lint: `ruff check src` / `ruff format src`
- Tests: `pytest` — note `pyproject.toml` points `testpaths` at a `tests/` directory that does not yet exist, so there are currently no project unit tests. (`test.py` in the root is empty; the `pytest` runs that matter happen *inside* the pipeline, executed by the Tester agent against generated code.)

Running the pipeline requires Anthropic credentials in the environment (e.g. `ANTHROPIC_API_KEY`), read from `.env` / the shell by `claude-agent-sdk`.

## Architecture

The pipeline is a **lead-developer → developer → tester** loop, orchestrated in `src/vibedev/pipeline.py::run_pipeline`:

1. **Lead Developer** turns the user prompt into a `DesignSpec` (class name, attributes, methods, notes) — structured JSON only, no code.
2. **Developer** implements the spec into a module file inside `vibedev-output/`, overwriting it completely.
3. **Tester** reads the implementation, writes and runs pytest tests, and returns a `TestReport` (`passed`, failed tests, missing features).
4. If tests fail, the report is fed back to the Lead Developer to revise the spec, and the loop repeats up to `MAX_ITERATIONS` (default 5, in `config.py`).

Layered structure (each layer depends only on those below it):

- `__init__.py` — public `run`/`run_async`/`set_output_dir` facade; wraps the async pipeline with `asyncio.run`.
- `pipeline.py` — orchestration and the test/revise loop.
- `agents.py` — the three role functions (`lead_developer`, `developer`, `tester`), each a thin wrapper over `run_agent` that validates output into a Pydantic model.
- `runner.py` — `run_agent`: the single chokepoint that calls the SDK. Builds `ClaudeAgentOptions`, streams the `query()` response, enforces structured output via JSON Schema, and logs the full conversation. **All SDK interaction lives here** — change agent behavior, tooling, or model config through this function and `config.py`, not by calling the SDK elsewhere.
- `models.py` — the three Pydantic contracts (`DesignSpec`, `DevResult`, `TestReport`) that define what each agent must return.
- `prompt_templates.py` — system prompts and prompt builders; also owns the `class_name → module_filename` / `test_filename` conventions (CamelCase → snake_case).
- `utils/logging.py` — two loggers: `PipelineLogger` (one structured JSON log per run + console progress) and `ConversationLogger` (one log per agent session). Both buffer in memory and write on `flush()`.

### Key conventions

- **Structured output is enforced at the SDK layer.** `run_agent` passes each model's `model_json_schema()` as the SDK `output_format`; if the agent can't produce valid output the run raises `RuntimeError`. Validation happens again in `agents.py` via `Model.model_validate(...)`.
- **Agents run with a sandboxed cwd.** All agents execute with `cwd=config.OUTPUT_DIR` and `allowed_tools=["Read", "Edit", "Bash", "Write"]` (see `config.CONFIG`). Generated files therefore live in `vibedev-output/`, not the package source tree.
- **Default model is `claude-haiku-4-5`** (`config.CONFIG["model"]`). The whole pipeline uses one model; change it in `config.py`.
- **`config.OUTPUT_DIR` / `LOGS_DIR` are module-level and created on import.** `set_output_dir()` reassigns them at runtime — when changing output location, go through that function so both dirs and their `mkdir` happen together.
