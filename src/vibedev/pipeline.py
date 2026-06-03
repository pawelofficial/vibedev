from vibedev import config
from vibedev.agents import (
    developer,
    developer_challenger,
    lead_developer,
    lead_developer_challenger,
    tester,
)
from vibedev.config import MAX_CHALLENGE_ITERATIONS, MAX_ITERATIONS
from vibedev.models import DesignSpec, TestReport
from vibedev.utils.logging import PipelineLogger, start_transcript


async def design_with_challenge(
    user_prompt: str,
    log: PipelineLogger,
    feedback: TestReport | None = None,
    challenge: bool = True,
) -> DesignSpec:
    """Draft a spec (optionally addressing tester feedback). When ``challenge`` is
    True, let a reviewer challenge it until approved; otherwise return the first
    draft as-is (used for tester-driven revisions, where the tester is the critic)."""
    challenge_remarks = ""
    for attempt in range(1, MAX_CHALLENGE_ITERATIONS + 1):
        specs = await lead_developer(
            user_prompt, feedback=feedback, challenge_remarks=challenge_remarks
        )
        log.info(
            f"\n📋 Spec (attempt {attempt}): {specs.class_name} — "
            f"{len(specs.attributes)} attrs, {len(specs.methods)} methods"
        )
        log.log(
            "spec_ready",
            attempt=attempt,
            class_name=specs.class_name,
            attributes=len(specs.attributes),
            methods=len(specs.methods),
        )

        # Stop when challenging is disabled, or on the last attempt — in both
        # cases there is no further revision to make.
        if not challenge or attempt == MAX_CHALLENGE_ITERATIONS:
            break

        verdict = await lead_developer_challenger(specs, user_prompt)
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

    return specs


async def develop_with_challenge(specs: DesignSpec, log: PipelineLogger) -> None:
    """Implement ``specs``, then let a reviewer challenge the code until approved."""
    challenge_remarks = ""
    for attempt in range(1, MAX_CHALLENGE_ITERATIONS + 1):
        await developer(specs, challenge_remarks=challenge_remarks)
        log.log("dev_done", attempt=attempt, class_name=specs.class_name)

        # No point challenging on the last attempt — we won't revise again.
        if attempt == MAX_CHALLENGE_ITERATIONS:
            break

        challenge = await developer_challenger(specs)
        log.log(
            "dev_challenged",
            attempt=attempt,
            approved=challenge.approved,
            remarks=len(challenge.remarks),
        )
        if challenge.approved:
            log.info(f"\n✅ Code review approved the implementation on attempt {attempt}.")
            break

        challenge_remarks = "\n".join(f"- {remark}" for remark in challenge.remarks)
        log.info(
            f"\n🔁 Code review requested {len(challenge.remarks)} change(s); revising implementation."
        )


async def run_pipeline(user_prompt: str) -> None:
    log = PipelineLogger(user_prompt)
    transcript = start_transcript(log.run_id)

    try:
        output_dir = config.OUTPUT_DIR.resolve()
        log.info(f"\n📁 Output directory: {output_dir}")
        log.info(f"📝 Conversation transcript: {transcript.path}")
        log.log("output_dir", path=str(output_dir))

        specs = await design_with_challenge(user_prompt, log)
        await develop_with_challenge(specs, log)

        for iteration in range(1, MAX_ITERATIONS + 1):
            log.log("test_iteration_start", iteration=iteration)
            report = await tester(specs)
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
            specs = await design_with_challenge(user_prompt, log, feedback=report, challenge=False)
            await develop_with_challenge(specs, log)
    finally:
        log.log("pipeline_end")
        log.flush()
