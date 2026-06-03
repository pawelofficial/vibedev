from typing import Awaitable, Callable

from vibedev import config
from vibedev.agents import (
    developer,
    developer_challenger,
    lead_developer,
    lead_developer_challenger,
    lead_developer_evolve,
    tester,
)
from vibedev.checkpoint import (
    PHASE_BUILDING,
    PHASE_COMPLETE,
    PHASE_DESIGNING,
    PHASE_TESTING,
    Checkpoint,
    resume_checkpoint,
    save_checkpoint,
)
from vibedev.config import MAX_CHALLENGE_ITERATIONS, MAX_ITERATIONS
from vibedev.manifest import build_manifest, load_manifest, save_manifest
from vibedev.models import FileSpec, ProjectSpec, TestReport
from vibedev.utils.logging import PipelineLogger, start_transcript

# A reviser turns a failing TestReport into the next spec to build (used by the shared
# build/test driver; run() re-designs, continue_development() re-evolves).
Reviser = Callable[[TestReport], Awaitable[ProjectSpec]]

# Picks which files the tester should cover for a given spec. Returning None means "the
# whole project" (full suite); a list scopes testing to just those files.
TestTargets = Callable[[ProjectSpec], "list[FileSpec] | None"]


def _all_files(project: ProjectSpec) -> "list[FileSpec] | None":
    return None  # test the whole project


def _changed_files(project: ProjectSpec) -> "list[FileSpec] | None":
    # Only files the evolve step tagged new/modified; fall back to the full suite if the
    # spec carries no tags (e.g. a from-scratch run, where nothing is "changed").
    changed = [f for f in project.files if f.change in ("new", "modified")]
    return changed or None


def _affected_files(project: ProjectSpec) -> "list[FileSpec] | None":
    """Changed files plus everything that transitively imports them — so a modified
    interface is re-tested in the files that depend on it. Falls back to the full suite
    when nothing is tagged changed."""
    changed = {f.path for f in project.files if f.change in ("new", "modified")}
    if not changed:
        return None
    # dependents[x] = files that directly depend_on x (the reverse of the import graph).
    dependents: dict[str, list[str]] = {f.path: [] for f in project.files}
    for f in project.files:
        for dep in f.depends_on:
            if dep in dependents:  # ignore deps outside the project (stdlib/third-party)
                dependents[dep].append(f.path)
    affected = set(changed)
    stack = list(changed)
    while stack:
        for dependent in dependents.get(stack.pop(), []):
            if dependent not in affected:
                affected.add(dependent)
                stack.append(dependent)
    return [f for f in project.files if f.path in affected]  # in project order


# Accepted values for continue_development(test_scope=...).
TEST_TARGETS: dict[str, TestTargets] = {
    "all": _all_files,
    "changed": _changed_files,
    "affected": _affected_files,
}


def topo_sort(files: list[FileSpec]) -> list[FileSpec]:
    """Order files so every file comes after the siblings it depends on.

    Dependencies on paths outside the project (stdlib, third-party) are ignored.
    Raises ValueError on a dependency cycle — that is a spec bug, not something to
    loop on forever.
    """
    by_path = {f.path: f for f in files}
    visited: dict[str, int] = {}  # path -> 0 = visiting, 1 = done
    ordered: list[FileSpec] = []

    def visit(f: FileSpec, trail: tuple[str, ...]) -> None:
        state = visited.get(f.path)
        if state == 1:
            return
        if state == 0:
            cycle = " -> ".join(trail + (f.path,))
            raise ValueError(f"Dependency cycle in spec: {cycle}")
        visited[f.path] = 0
        for dep in f.depends_on:
            dep_file = by_path.get(dep)
            if dep_file is not None:  # ignore external deps
                visit(dep_file, trail + (f.path,))
        visited[f.path] = 1
        ordered.append(f)

    for f in files:
        visit(f, ())
    return ordered


async def design_with_challenge(
    user_prompt: str,
    log: PipelineLogger,
    feedback: TestReport | None = None,
    challenge: bool = True,
) -> ProjectSpec:
    """Draft a project spec (optionally addressing tester feedback). When ``challenge``
    is True, let a reviewer challenge it until approved; otherwise return the first
    draft as-is (used for tester-driven revisions, where the tester is the critic)."""
    challenge_remarks = ""
    for attempt in range(1, MAX_CHALLENGE_ITERATIONS + 1):
        project = await lead_developer(
            user_prompt, feedback=feedback, challenge_remarks=challenge_remarks
        )
        log.info(
            f"\n📋 Spec (attempt {attempt}): {project.project_name} — "
            f"{len(project.files)} file(s)"
        )
        log.log(
            "spec_ready",
            attempt=attempt,
            project_name=project.project_name,
            files=len(project.files),
        )

        # Stop when challenging is disabled, or on the last attempt — in both
        # cases there is no further revision to make.
        if not challenge or attempt == MAX_CHALLENGE_ITERATIONS:
            break

        verdict = await lead_developer_challenger(project, user_prompt)
        log.log(
            "spec_challenged",
            attempt=attempt,
            approved=verdict.approved,
            remarks=len(verdict.remarks),
        )
        if verdict.approved:
            log.info(f"\n✅ Challenger approved the spec on attempt {attempt}.")
            break

        challenge_remarks = "\n".join(f"- {remark}" for remark in verdict.remarks)
        log.info(f"\n🔁 Challenger requested {len(verdict.remarks)} change(s); revising spec.")

    return project


async def evolve_with_challenge(
    feature_prompt: str,
    current: ProjectSpec,
    log: PipelineLogger,
    feedback: TestReport | None = None,
    challenge: bool = True,
) -> ProjectSpec:
    """Extend an existing project (``current``) with a new feature, returning the full
    updated spec with each file tagged new/modified/unchanged. Mirrors
    ``design_with_challenge`` but uses the evolve agent; the challenger judges the evolved
    spec against the feature request."""
    challenge_remarks = ""
    for attempt in range(1, MAX_CHALLENGE_ITERATIONS + 1):
        project = await lead_developer_evolve(
            feature_prompt, current, feedback=feedback, challenge_remarks=challenge_remarks
        )
        changed = [f.path for f in project.files if f.change in ("new", "modified")]
        log.info(
            f"\n📋 Evolved spec (attempt {attempt}): {project.project_name} — "
            f"{len(changed)} file(s) to build, {len(project.files)} total"
        )
        log.log(
            "evolve_ready",
            attempt=attempt,
            project_name=project.project_name,
            changed=len(changed),
            files=len(project.files),
        )

        if not challenge or attempt == MAX_CHALLENGE_ITERATIONS:
            break

        verdict = await lead_developer_challenger(project, feature_prompt)
        log.log(
            "evolve_challenged",
            attempt=attempt,
            approved=verdict.approved,
            remarks=len(verdict.remarks),
        )
        if verdict.approved:
            log.info(f"\n✅ Challenger approved the evolved spec on attempt {attempt}.")
            break

        challenge_remarks = "\n".join(f"- {remark}" for remark in verdict.remarks)
        log.info(f"\n🔁 Challenger requested {len(verdict.remarks)} change(s); revising spec.")

    return project


def _seed_built(project: ProjectSpec) -> list[str]:
    """Files the spec marks ``unchanged`` are already on disk, so the incremental build
    skips them. On a from-scratch run nothing is tagged, so this is empty and every file
    builds."""
    return [f.path for f in project.files if f.change == "unchanged"]


async def develop_with_challenge(file: FileSpec, project: ProjectSpec, log: PipelineLogger) -> None:
    """Implement one ``file``, then let a reviewer challenge the code until approved."""
    # A file tagged "modified" already exists on disk (continue_development): the developer
    # edits it in place rather than writing it fresh.
    modify = file.change == "modified"
    challenge_remarks = ""
    for attempt in range(1, MAX_CHALLENGE_ITERATIONS + 1):
        await developer(file, project, challenge_remarks=challenge_remarks, modify=modify)
        log.log("dev_done", attempt=attempt, path=file.path)

        # No point challenging on the last attempt — we won't revise again.
        if attempt == MAX_CHALLENGE_ITERATIONS:
            break

        verdict = await developer_challenger(file)
        log.log(
            "dev_challenged",
            attempt=attempt,
            path=file.path,
            approved=verdict.approved,
            remarks=len(verdict.remarks),
        )
        if verdict.approved:
            log.info(f"\n✅ Code review approved {file.path} on attempt {attempt}.")
            break

        challenge_remarks = "\n".join(f"- {remark}" for remark in verdict.remarks)
        log.info(
            f"\n🔁 Code review requested {len(verdict.remarks)} change(s) on {file.path}; revising."
        )


async def build_project(project: ProjectSpec, log: PipelineLogger, cp: Checkpoint) -> None:
    """Implement every file in dependency order so each file can read the ones it imports.

    Skips files already finished in the current build pass (``cp.built_paths``) and
    checkpoints after each one, so an interrupted build resumes mid-pass rather than
    redoing the expensive developer+challenger loop for files already on disk."""
    order = topo_sort(project.files)
    log.info("\n🏗️  Build order: " + " -> ".join(f.path for f in order))
    log.log("build_order", paths=[f.path for f in order])
    done = set(cp.built_paths)
    for file in order:
        if file.path in done:
            log.info(f"\n⏭️  Skipping {file.path} (already built this pass).")
            continue
        await develop_with_challenge(file, project, log)
        cp.built_paths.append(file.path)
        save_checkpoint(cp)


def _log_start(log: PipelineLogger, transcript, cp: Checkpoint, resuming: bool) -> None:
    output_dir = config.OUTPUT_DIR.resolve()
    log.info(f"\n📁 Output directory: {output_dir}")
    log.info(f"📝 Conversation transcript: {transcript.path}")
    log.log("output_dir", path=str(output_dir))
    if resuming:
        log.info(
            f"\n♻️  Resuming run {cp.run_id} at phase '{cp.phase}' "
            f"(iteration {cp.iteration}, {len(cp.built_paths)} file(s) built this pass)."
        )
        log.log("resume", phase=cp.phase, iteration=cp.iteration, built=len(cp.built_paths))


async def _build_then_test(
    cp: Checkpoint,
    log: PipelineLogger,
    revise: Reviser,
    test_targets: TestTargets = _all_files,
) -> ProjectSpec:
    """Shared core for both run and continue: build the current spec (resumable mid-pass,
    incremental when files are tagged ``unchanged``), then run the test→revise loop until
    tests pass or ``MAX_ITERATIONS`` is reached. ``revise`` turns a failing report into the
    next spec to build; ``test_targets`` selects which files the tester covers. ``cp`` must
    already hold the spec and be in the building/testing phase. Returns the final project."""
    while cp.phase != PHASE_COMPLETE:
        project = ProjectSpec.model_validate(cp.spec)

        # --- Build (initial, resumed mid-pass, or a revised pass). ---
        if cp.phase == PHASE_BUILDING:
            await build_project(project, log, cp)
            cp.phase = PHASE_TESTING
            save_checkpoint(cp)

        # --- One test iteration. cp.iteration counts completed iterations. ---
        iteration = cp.iteration + 1
        targets = test_targets(project)
        log.log(
            "test_iteration_start",
            iteration=iteration,
            scope=("all" if targets is None else [f.path for f in targets]),
        )
        report = await tester(project, targets)
        cp.last_report = report.model_dump()
        log.log(
            "test_iteration_result",
            iteration=iteration,
            passed=report.passed,
            summary=report.summary,
            failed_tests=len(report.failed_tests),
            missing_features=len(report.missing_features),
        )

        if report.passed:
            log.info("\n✅ All tests passed — pipeline complete.")
            log.log("pipeline_complete", iteration=iteration)
            cp.phase = PHASE_COMPLETE
            save_checkpoint(cp)
            break

        if iteration >= MAX_ITERATIONS:
            log.info("\n⚠️  Max testing iterations reached. Stopping.")
            log.log("pipeline_stopped", reason="max_iterations", iteration=iteration)
            cp.phase = PHASE_COMPLETE
            save_checkpoint(cp)
            break

        # --- Revise and start a fresh build pass. ---
        log.log("spec_revised", iteration=iteration)
        project = await revise(report)
        cp.iteration = iteration
        cp.spec = project.model_dump()
        cp.built_paths = _seed_built(project)  # empty for run(); keeps unchanged files for continue()
        cp.phase = PHASE_BUILDING
        save_checkpoint(cp)

    return ProjectSpec.model_validate(cp.spec)


async def run_pipeline(user_prompt: str) -> None:
    """Design and build a project from scratch (the from-blank pipeline)."""
    log = PipelineLogger(user_prompt)
    transcript = start_transcript(log.run_id)

    # Auto-detect an interrupted run for this prompt and resume it; otherwise start fresh.
    cp = resume_checkpoint(user_prompt)
    resuming = cp is not None
    if cp is None:
        cp = Checkpoint(user_prompt=user_prompt, run_id=log.run_id, phase=PHASE_DESIGNING)

    try:
        _log_start(log, transcript, cp, resuming)

        # Design (initial). Can't resume mid-design, so a crash here just redesigns.
        if cp.phase == PHASE_DESIGNING:
            project = await design_with_challenge(user_prompt, log)
            cp.spec = project.model_dump()
            cp.built_paths = _seed_built(project)
            cp.phase = PHASE_BUILDING
            save_checkpoint(cp)

        async def revise(report: TestReport) -> ProjectSpec:
            return await design_with_challenge(user_prompt, log, feedback=report, challenge=False)

        project = await _build_then_test(cp, log, revise)
        save_manifest(build_manifest(user_prompt, project, feature_history=[]))
        log.info(f"\n📦 Project manifest written: {config.OUTPUT_DIR / 'project.json'}")
    finally:
        log.log("pipeline_end")
        log.flush()


async def continue_pipeline(feature_prompt: str, test_scope: str = "all") -> None:
    """Extend the existing project (read from the manifest) with a new feature, building
    only the files the evolve step tags new/modified.

    ``test_scope`` controls what the tester covers: ``"all"`` (default) tests the whole
    project; ``"changed"`` tests only the new/modified files (fastest, but won't catch
    breakage a modified file causes elsewhere); ``"affected"`` tests the changed files plus
    everything that transitively depends on them."""
    if test_scope not in TEST_TARGETS:
        raise ValueError(
            f"test_scope must be one of {sorted(TEST_TARGETS)}, got {test_scope!r}"
        )
    test_targets = TEST_TARGETS[test_scope]

    log = PipelineLogger(feature_prompt)
    transcript = start_transcript(log.run_id)

    manifest = load_manifest()
    if manifest is None:
        raise RuntimeError(
            "No project manifest found in the output dir. Run vibedev.run(...) to create a "
            "project before calling vibedev.continue_development(...)."
        )

    # Resumability for the continue run is keyed to the feature prompt (distinct from the
    # original run's prompt), so the two don't accidentally resume each other.
    cp = resume_checkpoint(feature_prompt)
    resuming = cp is not None
    if cp is None:
        cp = Checkpoint(user_prompt=feature_prompt, run_id=log.run_id, phase=PHASE_DESIGNING)

    try:
        _log_start(log, transcript, cp, resuming)
        log.info(
            f"\n🧩 Extending '{manifest.project_name}' with: {feature_prompt}  "
            f"(test scope: {test_scope})"
        )

        current = ProjectSpec.model_validate(manifest.spec)

        # Evolve (initial). On resume we already have the evolved spec in the checkpoint.
        if cp.phase == PHASE_DESIGNING:
            project = await evolve_with_challenge(feature_prompt, current, log)
            cp.spec = project.model_dump()
            cp.built_paths = _seed_built(project)
            cp.phase = PHASE_BUILDING
            save_checkpoint(cp)

        async def revise(report: TestReport) -> ProjectSpec:
            return await evolve_with_challenge(
                feature_prompt,
                ProjectSpec.model_validate(cp.spec),
                log,
                feedback=report,
                challenge=False,
            )

        project = await _build_then_test(cp, log, revise, test_targets)
        history = manifest.feature_history + [feature_prompt]
        save_manifest(build_manifest(manifest.original_prompt, project, feature_history=history))
        log.info(f"\n📦 Project manifest updated: {config.OUTPUT_DIR / 'project.json'}")
    finally:
        log.log("pipeline_end")
        log.flush()
