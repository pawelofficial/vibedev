from vibedev import config
from vibedev.agents import developer, lead_developer, tester
from vibedev.config import MAX_ITERATIONS
from vibedev.utils.logging import PipelineLogger


async def run_pipeline(user_prompt: str) -> None:
    log = PipelineLogger(user_prompt)

    try:
        output_dir = config.OUTPUT_DIR.resolve()
        log.info(f"\n📁 Output directory: {output_dir}")
        log.log("output_dir", path=str(output_dir))

        specs = await lead_developer(user_prompt)
        spec_msg = (
            f"\n📋 Spec: {specs.class_name} — "
            f"{len(specs.attributes)} attrs, {len(specs.methods)} methods"
        )
        log.info(spec_msg)
        log.log(
            "spec_ready",
            class_name=specs.class_name,
            attributes=len(specs.attributes),
            methods=len(specs.methods),
        )
        
        
        await developer(specs)

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

            specs = await lead_developer(user_prompt, feedback=report)
            log.log(
                "spec_revised",
                iteration=iteration,
                class_name=specs.class_name,
                attributes=len(specs.attributes),
                methods=len(specs.methods),
            )
            await developer(specs)
    finally:
        log.log("pipeline_end")
        log.flush()
