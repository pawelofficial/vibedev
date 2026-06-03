from vibedev.models import DesignSpec, DevResult, TestReport
from vibedev.prompt_templates import (
    DEVELOPER_SYSTEM,
    LEAD_DEVELOPER_SYSTEM,
    TESTER_SYSTEM,
    developer_prompt,
    lead_developer_prompt,
    tester_prompt,
)
from vibedev.runner import run_agent


async def lead_developer(user_prompt: str, feedback: TestReport | None = None) -> DesignSpec:
    raw = await run_agent(
        role="Lead Developer",
        system_prompt=LEAD_DEVELOPER_SYSTEM,
        prompt=lead_developer_prompt(user_prompt, feedback),
        output_schema=DesignSpec,
    )
    return DesignSpec.model_validate(raw)


async def developer(specs: DesignSpec) -> None:
    await run_agent(
        role="Software Developer",
        system_prompt=DEVELOPER_SYSTEM,
        prompt=developer_prompt(specs),
        output_schema=DevResult,
    )


async def tester(specs: DesignSpec) -> TestReport:
    raw = await run_agent(
        role="Tester",
        system_prompt=TESTER_SYSTEM,
        prompt=tester_prompt(specs),
        output_schema=TestReport,
    )
    return TestReport.model_validate(raw)
