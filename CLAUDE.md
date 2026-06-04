# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`vibedev` is "agentic development as a Python package": you give it a natural-language prompt and it drives a multi-agent pipeline (powered by `claude-agent-sdk`) that designs, implements, and tests a small multi-file Python project for you. Generated code and logs are written to `./vibedev-output/`.

The public API is tiny — `vibedev.run(prompt)` builds a project from scratch, and `vibedev.continue_development(feature_prompt)` extends the project already in the output dir with a new feature (sync; each has an `_async` variant). See `myapp.py` for the canonical usage example.

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

- `__init__.py` — public `run`/`run_async` and `continue_development`/`continue_development_async` + `set_output_dir` facade; wraps the async pipeline with `asyncio.run`.
- `pipeline.py` — orchestration. `run_pipeline` (build from scratch) and `continue_pipeline` (extend an existing project) both set up a spec + checkpoint, then hand off to the shared `_build_then_test` driver (build + test/revise loop). The challenge loops are `design_with_challenge` / `evolve_with_challenge` / `develop_with_challenge`; `topo_sort` + `build_project` do the dependency-ordered, resumable, incremental build. Structured as a checkpoint-driven state machine (designing → building → testing → complete) so interrupted runs resume (see *Resumability*) and feature-adds build only changed files (see *Extending a project*).
- `checkpoint.py` — `Checkpoint` (the resumable state model) plus `save_checkpoint` (atomic temp-file + `os.replace`), `load_checkpoint`, and `resume_checkpoint`. Persists `checkpoint.json` in the output dir.
- `manifest.py` — `ProjectManifest` + `build_manifest`/`save_manifest`/`load_manifest`. The **stable** record of what the current project is (final spec, original prompt, feature history), written to `project.json` (+ a human-readable `PROJECT.md`) on completion. Distinct from the checkpoint: the checkpoint is transient resume state, the manifest is the durable project description `continue_development` reads.
- `agents.py` — the role functions (`lead_developer`, `lead_developer_evolve`, `lead_developer_challenger`, `developer`, `developer_challenger`, `tester`), each a thin wrapper over `run_agent` that validates output into a Pydantic model.
- `runner.py` — `run_agent`: the single chokepoint that calls the SDK. Builds `ClaudeAgentOptions`, streams the `query()` response (`_stream_session`), captures both the structured output and the agent's free-text narration, logs the full conversation, and appends a human-readable block to the run's transcript. **All SDK interaction lives here** — change agent behavior, tooling, or model config through this function and `config.py`, not by calling the SDK elsewhere.
- `models.py` — the Pydantic contracts: `ProjectSpec` / `FileSpec` / `ComponentSpec` (the design), `ChallengeReport` (a challenger's `approved` + `remarks`), `DevResult`, and `TestReport`. `FileSpec.change` (`new`/`modified`/`unchanged`, default `None`) is set **only** by the evolve step during `continue_development`; it drives the incremental build and is stripped before the manifest is saved.
- `prompt_templates.py` — system prompts and prompt builders. `module_filename()` (CamelCase → snake_case) is now only a *naming hint* — real paths are explicit in each `FileSpec.path`; `test_filename(path)` keeps tests beside their module.
- `utils/logging.py` — three loggers: `PipelineLogger` (one structured JSON log per run + console progress), `TranscriptLogger` (one human-readable, ASCII transcript of the whole agent conversation per run; module-level singleton via `start_transcript`/`get_transcript`, written to by `run_agent`), and `ConversationLogger` (one raw log per agent session). All buffer in memory and write on `flush()` (the transcript appends per agent call).

### Key conventions

- **Structured output is enforced at the SDK layer, with a coercion fallback.** `run_agent` passes each model's `model_json_schema()` as the SDK `output_format`. The expensive tool-using work runs **exactly once**; if the agent finishes but emits no structured output, `runner._coerce_to_schema` makes a cheap, tool-less `DEFAULT_MODEL` call that reshapes only the captured narration text into the schema (retried up to `MAX_STRUCTURED_OUTPUT_ATTEMPTS`, default 3). Only an empty narration or exhausted coercion raises `StructuredOutputError` (a `RuntimeError` subclass). Validation happens again in `agents.py` via `Model.model_validate(...)`.
- **The `ProjectSpec.files` graph is built in dependency order.** `topo_sort` orders leaf-dependencies first, ignores deps on paths outside the project (stdlib/third-party), and raises `ValueError` on a cycle (a spec bug — better to fail than loop forever). A single class in one file is just a one-file, one-component `ProjectSpec`.
- **Agents run with `cwd=OUTPUT_DIR` but are not truly sandboxed.** All agents execute with `cwd=config.OUTPUT_DIR`, so generated files land in `vibedev-output/`. But `permission_mode` is `bypassPermissions` (the pipeline drives `query()` non-interactively, so any prompt would stall it) and `add_dirs` is seeded with the **whole repo** (`config.CONFIG["extra_dirs"]`, default `[REPO_ROOT]`) — agents can read and write beyond the output dir. Trim `extra_dirs` to reduce reach.
- **Agents are handed absolute file paths, never project-relative ones.** `config.OUTPUT_DIR` is resolved to an absolute path on import (and by `set_output_dir`), and the prompt builders run every `FileSpec.path` through `config.abs_path(rel)` (= `OUTPUT_DIR / rel`, absolute) before putting it in a developer/challenger/tester prompt. This is load-bearing: the SDK's `Read`/`Write`/`Edit` tools require absolute paths, so a relative path like `pkg/foo.py` lets each agent pick its own base dir — and because `add_dirs` includes `REPO_ROOT`, they often pick the repo root, scattering files outside `vibedev-output/` and making the challenger (which reads the spec path) report the file "does not exist". The `FileSpec.path` stored in the spec/manifest stays project-relative (so `topo_sort`/`depends_on` matching is unaffected); only the prompt text is absolutized. The shared `allowed_tools` are `Read, Edit, Bash, Write, Glob, Grep, WebFetch, WebSearch` (`Glob`/`Grep` for navigating multi-file projects, `Web*` for looking up library APIs); the developer relies on both `Write` (new files) and `Edit` (targeted revisions).
- **Models are per-role.** `config.DEFAULT_MODEL` (`claude-haiku-4-5`) backs the critics and tester; `config.ROLE_MODELS` overrides the two code/spec-producing roles — **both `Lead Developer` and `Software Developer` run on `SONNET_MODEL` (`claude-sonnet-4-6`)**, the harder generative work. `config.model_for(role)` resolves the two; `runner.run_agent` calls it. Structured-output *coercion* always uses `DEFAULT_MODEL` (reshaping text to JSON is cheap work).
- **`config.OUTPUT_DIR` / `LOGS_DIR` are module-level and created on import.** `set_output_dir()` reassigns them at runtime — when changing output location, go through that function so both dirs and their `mkdir` happen together.

### Resumability

A run that dies mid-flight (e.g. token exhaustion) can be **resumed automatically**. The generated code is already on disk the moment each file is written — the only thing lost is in-memory orchestration state, so `checkpoint.py` persists exactly that to `<output_dir>/checkpoint.json`, written atomically at each boundary:

- after the initial design → full `ProjectSpec`, `phase="building"`
- after **each** built file → that path appended to `built_paths` (so a resumed build skips files already done *in the current pass* and doesn't redo the expensive developer+challenger loop)
- each test iteration → `iteration` + last `TestReport`; on a revision, the new spec with `built_paths` reset for the fresh pass
- on success/stop → `phase="complete"` (a tombstone — never resumed)

Both pipelines call `resume_checkpoint(prompt)` on startup: they resume only if a checkpoint exists, **matches the same prompt**, and isn't complete; otherwise they start fresh (mismatched/corrupt/absent → fresh). `run_pipeline` keys on the user prompt, `continue_pipeline` on the feature prompt, so the two never resume each other. This is why the driver is a `while cp.phase != complete` state machine rather than a straight-line function — each phase is re-entrant from a loaded checkpoint. The human-readable transcript is intentionally *not* the resume source (it's lossy prose); the checkpoint is the machine-readable source of truth.

### Extending a project

`continue_development(feature_prompt)` adds a feature to the project already in the output dir instead of regenerating it. It reads `project.json` (the manifest — the missing "what's already here" context that a from-scratch `run` lacks), then:

- **Evolve, not design.** `evolve_with_challenge` → `lead_developer_evolve` is given the existing spec (and the code on disk to `Read`) and the feature, and returns the *full* updated `ProjectSpec` with each `FileSpec.change` tagged `new` / `modified` / `unchanged`.
- **Incremental build.** This reuses the resume skip logic: `_seed_built(project)` seeds `cp.built_paths` with the `unchanged` files, so `build_project` only builds `new`/`modified` ones. A `modified` file is edited in place (the developer gets a "this file already exists, make targeted edits" instruction via `developer(..., modify=True)`); a `new` file is written fresh.
- **Shared loop.** From there it's the same `_build_then_test` driver as `run` (test → revise → rebuild), except the reviser re-evolves with tester feedback. On success the manifest is rewritten with the new spec and the feature appended to `feature_history`.

**Test scope** is selectable via `continue_development(feature_prompt, test_scope=...)`: `"all"` (default) tests the whole project; `"changed"` tests only the new/modified files (fastest, but won't catch breakage a modified file causes in its dependents); `"affected"` tests the changed files **plus everything that transitively depends on them** (`_affected_files` walks the reverse `depends_on` graph). The driver takes a `test_targets: TestTargets` callable (`_all_files` / `_changed_files` / `_affected_files`, dispatched via `pipeline.TEST_TARGETS`) that picks the file subset per spec; `tester(project, files_to_test)` and `tester_prompt` scope the suite accordingly. `run` always uses `_all_files`. Note: `test_scope` is a per-call argument, **not** persisted in the checkpoint — on a resumed continue-run, pass it again (the `change` tags it relies on do live in the checkpoint).

Prerequisite: a prior `run` must have produced a manifest — `continue_development` raises `RuntimeError` if `project.json` is absent.
