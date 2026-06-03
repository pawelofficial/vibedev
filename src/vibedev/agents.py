from vibedev.models import ChallengeReport, DesignSpec, DevResult, TestReport
from vibedev.prompt_templates import (
    DEVELOPER_CHALLENGER_SYSTEM,
    DEVELOPER_SYSTEM,
    LEAD_DEVELOPER_CHALLENGER_SYSTEM,
    LEAD_DEVELOPER_SYSTEM,
    TESTER_SYSTEM,
    developer_challenger_prompt,
    developer_prompt,
    lead_developer_challenger_prompt,
    lead_developer_prompt,
    tester_prompt,
)
from vibedev.runner import run_agent


async def lead_developer(
    user_prompt: str,
    feedback: TestReport | None = None,
    challenge_remarks: str = "",
) -> DesignSpec:
    raw = await run_agent(
        role="Lead Developer",
        system_prompt=LEAD_DEVELOPER_SYSTEM,
        prompt=lead_developer_prompt(user_prompt, feedback, challenge_remarks),
        output_schema=DesignSpec,
    )
    return DesignSpec.model_validate(raw)


async def lead_developer_challenger(specs: DesignSpec, user_prompt: str) -> ChallengeReport:
    raw = await run_agent(
        role="Lead Developer Challenger",
        system_prompt=LEAD_DEVELOPER_CHALLENGER_SYSTEM,
        prompt=lead_developer_challenger_prompt(specs, user_prompt),
        output_schema=ChallengeReport,
    )
    return ChallengeReport.model_validate(raw)


async def developer(specs: DesignSpec, challenge_remarks: str = "") -> None:
    await run_agent(
        role="Software Developer",
        system_prompt=DEVELOPER_SYSTEM,
        prompt=developer_prompt(specs, challenge_remarks),
        output_schema=DevResult,
    )


async def developer_challenger(specs: DesignSpec) -> ChallengeReport:
    raw = await run_agent(
        role="Software Developer Challenger",
        system_prompt=DEVELOPER_CHALLENGER_SYSTEM,
        prompt=developer_challenger_prompt(specs),
        output_schema=ChallengeReport,
    )
    return ChallengeReport.model_validate(raw)


async def tester(specs: DesignSpec) -> TestReport:
    raw = await run_agent(
        role="Tester",
        system_prompt=TESTER_SYSTEM,
        prompt=tester_prompt(specs),
        output_schema=TestReport,
    )
    return TestReport.model_validate(raw)
