from vibedev.models import ChallengeReport, DevResult, FileSpec, ProjectSpec, TestReport
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
) -> ProjectSpec:
    raw = await run_agent(
        role="Lead Developer",
        system_prompt=LEAD_DEVELOPER_SYSTEM,
        prompt=lead_developer_prompt(user_prompt, feedback, challenge_remarks),
        output_schema=ProjectSpec,
    )
    return ProjectSpec.model_validate(raw)


async def lead_developer_challenger(project: ProjectSpec, user_prompt: str) -> ChallengeReport:
    raw = await run_agent(
        role="Lead Developer Challenger",
        system_prompt=LEAD_DEVELOPER_CHALLENGER_SYSTEM,
        prompt=lead_developer_challenger_prompt(project, user_prompt),
        output_schema=ChallengeReport,
    )
    return ChallengeReport.model_validate(raw)


async def developer(file: FileSpec, project: ProjectSpec, challenge_remarks: str = "") -> None:
    await run_agent(
        role="Software Developer",
        system_prompt=DEVELOPER_SYSTEM,
        prompt=developer_prompt(file, project, challenge_remarks),
        output_schema=DevResult,
    )


async def developer_challenger(file: FileSpec) -> ChallengeReport:
    raw = await run_agent(
        role="Software Developer Challenger",
        system_prompt=DEVELOPER_CHALLENGER_SYSTEM,
        prompt=developer_challenger_prompt(file),
        output_schema=ChallengeReport,
    )
    return ChallengeReport.model_validate(raw)


async def tester(project: ProjectSpec) -> TestReport:
    raw = await run_agent(
        role="Tester",
        system_prompt=TESTER_SYSTEM,
        prompt=tester_prompt(project),
        output_schema=TestReport,
    )
    return TestReport.model_validate(raw)
