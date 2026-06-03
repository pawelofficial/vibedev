import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from pydantic import BaseModel
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

# --- Global config ---
CONFIG = {
    "model": "claude-haiku-4-5",
    "allowed_tools": ["Read", "Edit", "Bash", "Write"],
}

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


# ── Structured contracts between agents ──────────────────────────────────────

class DesignSpec(BaseModel):
    class_name: str
    description: str
    attributes: list[dict]   # [{"name": "...", "type": "...", "description": "..."}]
    methods: list[dict]      # [{"name": "...", "signature": "...", "description": "..."}]
    notes: list[str]

class TestReport(BaseModel):
    passed: bool
    summary: str
    failed_tests: list[dict]  # [{"test_name": "...", "reason": "..."}]
    missing_features: list[str]


# ── Logger ────────────────────────────────────────────────────────────────────

class ConversationLogger:
    def __init__(self, session_id: str, role: str):
        self.path = LOGS_DIR / f"{session_id}_{role.lower().replace(' ', '_')}_conversation.log"
        self._lines: list[str] = []

    def log(self, event: str, **kwargs):
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kwargs}
        self._lines.append(json.dumps(entry, default=str))

    def flush(self):
        self.path.write_text("\n".join(self._lines) + "\n")
        print(f"  → Log: {self.path}")


# ── Generic agent runner ──────────────────────────────────────────────────────

async def run_agent(
    role: str,
    system_prompt: str,
    prompt: str,
    output_schema: type[BaseModel],
) -> dict:
    options = ClaudeAgentOptions(
        model=CONFIG["model"],
        system_prompt=system_prompt,
        allowed_tools=CONFIG["allowed_tools"],
        output_format={
            "type": "json_schema",
            "schema": output_schema.model_json_schema(),
        },
    )

    logger: ConversationLogger | None = None
    result_data: dict = {}

    print(f"\n{'='*50}")
    print(f"AGENT: {role}  [{CONFIG['model']}]")
    print(f"{'='*50}")

    async for message in query(prompt=prompt, options=options):

        # Initialise logger on first message that has a session_id
        if logger is None and hasattr(message, "session_id") and message.session_id:
            logger = ConversationLogger(message.session_id, role)
            logger.log("agent_start", role=role, model=CONFIG["model"], prompt=prompt)

        # Log every message
        if logger:
            try:
                logger.log("message", type=type(message).__name__, data=message.__dict__)
            except Exception:
                logger.log("message", type=type(message).__name__, data=str(message))

        print(message)

        # Extract structured output from the final result message
        if isinstance(message, ResultMessage):
            if message.subtype == "success" and message.structured_output:
                result_data = message.structured_output
                if logger:
                    logger.log("structured_output", data=result_data)
            elif message.subtype == "error_max_structured_output_retries":
                if logger:
                    logger.log("error", reason="max_structured_output_retries")
                raise RuntimeError(f"[{role}] Failed to produce valid structured output")

    if logger:
        logger.log("agent_end", role=role)
        logger.flush()

    return result_data


# ── Agents ────────────────────────────────────────────────────────────────────

async def lead_developer(feedback: TestReport | None = None) -> DesignSpec:
    feedback_section = ""
    if feedback:
        feedback_section = f"""

TESTER FEEDBACK (address all of this):
- Summary: {feedback.summary}
- Missing features: {', '.join(feedback.missing_features)}
- Failed tests: {json.dumps(feedback.failed_tests, indent=2)}
"""

    raw = await run_agent(
        role="Lead Developer",
        system_prompt=(
            "You are a senior software architect. "
            "Output a precise, very short design spec for a Python class. "
            "Do NOT write code. Respond with structured JSON only."
            "If given tester feedback, revise your spec to address every point."
        ),
        prompt=f"Design a Dog class in Python.{feedback_section}",
        output_schema=DesignSpec,
    )
    return DesignSpec.model_validate(raw)


async def developer(specs: DesignSpec) -> None:
    spec_json = specs.model_dump_json(indent=2)
    await run_agent(
        role="Software Developer",
        system_prompt=(
            "You are a Python developer. "
            "Implement exactly what the spec says, nothing more. "
            "Always overwrite dog.py completely."
        ),
        prompt=(
            f"Implement this Dog class in dog.py.\n\n"
            f"Spec (JSON):\n{spec_json}"
        ),
        output_schema=type("DevResult", (BaseModel,), {
            "__annotations__": {"status": str, "file_written": str}
        }),
    )


async def tester(specs: DesignSpec) -> TestReport:
    expected_methods = [m["name"] for m in specs.methods]
    raw = await run_agent(
        role="Tester",
        system_prompt=(
            "You are a QA engineer. "
            "Read dog.py, write pytest tests for every attribute and method, "
            "save to test_dog.py, and run them with Bash. "
            "Report results as structured JSON."
        ),
        prompt=(
            f"Read dog.py. Write and run pytest tests covering:\n"
            f"- All attributes from spec\n"
            f"- All methods: {', '.join(expected_methods)}\n"
            f"- Include a bite_mailman() test\n"
            f"Save tests to test_dog.py and run them."
        ),
        output_schema=TestReport,
    )
    return TestReport.model_validate(raw)


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def main():
    MAX_ITERATIONS = 3

    specs = await lead_developer()
    print(f"\n📋 Spec: {specs.class_name} — {len(specs.attributes)} attrs, {len(specs.methods)} methods")
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

        specs = await lead_developer(feedback=report)
        await developer(specs)


asyncio.run(main())