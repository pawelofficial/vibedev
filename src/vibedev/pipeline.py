from vibedev import config
from vibedev.agents import (
    developer,
    developer_challenger,
    lead_developer,
    lead_developer_challenger,
    tester,
)
from vibedev.config import MAX_CHALLENGE_ITERATIONS, MAX_ITERATIONS
from vibedev.models import FileSpec, ProjectSpec, TestReport
from vibedev.utils.logging import PipelineLogger, start_transcript


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


async def develop_with_challenge(file: FileSpec, project: ProjectSpec, log: PipelineLogger) -> None:
    """Implement one ``file``, then let a reviewer challenge the code until approved."""
    challenge_remarks = ""
    for attempt in range(1, MAX_CHALLENGE_ITERATIONS + 1):
        await developer(file, project, challenge_remarks=challenge_remarks)
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


async def build_project(project: ProjectSpec, log: PipelineLogger) -> None:
    """Implement every file in dependency order so each file can read the ones it imports."""
    order = topo_sort(project.files)
    log.info("\n🏗️  Build order: " + " -> ".join(f.path for f in order))
    log.log("build_order", paths=[f.path for f in order])
    for file in order:
        await develop_with_challenge(file, project, log)


async def run_pipeline(user_prompt: str) -> None:
    log = PipelineLogger(user_prompt)
    transcript = start_transcript(log.run_id)

    try:
        output_dir = config.OUTPUT_DIR.resolve()
        log.info(f"\n📁 Output directory: {output_dir}")
        log.info(f"📝 Conversation transcript: {transcript.path}")
        log.log("output_dir", path=str(output_dir))

        project = await design_with_challenge(user_prompt, log)
        await build_project(project, log)

        for iteration in range(1, MAX_ITERATIONS + 1):
            log.log("test_iteration_start", iteration=iteration)
            report = await tester(project)
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
                break

            if iteration == MAX_ITERATIONS:
                log.info("\n⚠️  Max testing iterations reached. Stopping.")
                log.log("pipeline_stopped", reason="max_iterations", iteration=iteration)
                break

            log.log("spec_revised", iteration=iteration)
            project = await design_with_challenge(
                user_prompt, log, feedback=report, challenge=False
            )
            await build_project(project, log)
    finally:
        log.log("pipeline_end")
        log.flush()
