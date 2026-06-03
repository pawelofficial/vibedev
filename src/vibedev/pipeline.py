from vibedev import config
from vibedev.agents import developer, lead_developer, tester
from vibedev.config import MAX_ITERATIONS


async def run_pipeline(user_prompt: str) -> None:
    print(f"\n📁 Output directory: {config.OUTPUT_DIR.resolve()}")

    specs = await lead_developer(user_prompt)
    print(
        f"\n📋 Spec: {specs.class_name} — "
        f"{len(specs.attributes)} attrs, {len(specs.methods)} methods"
    )
    await developer(specs)

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n{'#'*50}")
        print(f"# TEST ITERATION {iteration}")
        print(f"{'#'*50}")

        report = await tester(specs)

        if report.passed:
            print("\n✅ All tests passed — pipeline complete.")
            break

        print(f"\n❌ Tests failed (iteration {iteration}).")
        print(f"   Missing: {report.missing_features}")

        if iteration == MAX_ITERATIONS:
            print("\n⚠️  Max iterations reached. Stopping.")
            break

        specs = await lead_developer(user_prompt, feedback=report)
        await developer(specs)
