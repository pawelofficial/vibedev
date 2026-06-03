import json
import re

from vibedev.models import DesignSpec, TestReport


LEAD_DEVELOPER_SYSTEM = (
    "You are a senior software architect. "
    "Output a precise, very short design spec for a Python class. "
    "Do NOT write code. Respond with structured JSON only. "
    "If given tester feedback or challenge remarks, revise your spec to address every point."
)

LEAD_DEVELOPER_CHALLENGER_SYSTEM = (
    "You are a senior architect reviewing another architect's design spec. "
    "Critique it against the user's request: look for missing or unnecessary "
    "Pay attention to high level architectural mistakes, ommissions, poor design choices "
    "attributes/methods, vague descriptions, wrong types, and scope creep. "
    "Be strict but fair — approve only when the spec is genuinely sound. "
    "Respond with structured JSON only: set 'approved' and list concrete 'remarks'."
)

DEVELOPER_SYSTEM = (
    "You are a Python developer. "
    "Implement exactly what the spec says, nothing more. "
    "Always overwrite the target module file completely. "
    "If given code-review remarks, revise the implementation to address every point."
)

DEVELOPER_CHALLENGER_SYSTEM = (
    "You are a senior engineer doing code review. "
    "Read the implementation file and critique it against the spec: missing or "
    "incorrect attributes/methods, wrong signatures, bugs, and sloppy code. "
    "Be strict but fair — approve only when the implementation faithfully and "
    "cleanly satisfies the spec. "
    "Respond with structured JSON only: set 'approved' and list concrete 'remarks'."
)

TESTER_SYSTEM = (
    "You are a QA engineer. "
    "Read the implementation file, write pytest tests for every attribute and method, "
    "save to the test file, and run them with Bash. "
    "Report results as structured JSON."
)


def module_filename(class_name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()
    return f"{s}.py"


def test_filename(class_name: str) -> str:
    return f"test_{module_filename(class_name)}"


def lead_developer_prompt(
    user_prompt: str,
    feedback: TestReport | None = None,
    challenge_remarks: str = "",
) -> str:
    feedback_section = ""
    if feedback:
        feedback_section = f"""

TESTER FEEDBACK (address all of this):
- Summary: {feedback.summary}
- Missing features: {', '.join(feedback.missing_features)}
- Failed tests: {json.dumps(feedback.failed_tests, indent=2)}
"""
    challenge_section = ""
    if challenge_remarks:
        challenge_section = f"""

REVIEWER CHALLENGE (revise the spec to address every remark):
{challenge_remarks}
"""
    return f"{user_prompt.rstrip('.')}.{feedback_section}{challenge_section}"


def lead_developer_challenger_prompt(specs: DesignSpec, user_prompt: str) -> str:
    spec_json = specs.model_dump_json(indent=2)
    return (
        f"User request: {user_prompt.rstrip('.')}.\n\n"
        f"Proposed design spec (JSON):\n{spec_json}\n\n"
        f"Review this spec against the request and report your critique."
    )


def developer_prompt(specs: DesignSpec, challenge_remarks: str = "") -> str:
    target = module_filename(specs.class_name)
    spec_json = specs.model_dump_json(indent=2)
    challenge_section = ""
    if challenge_remarks:
        challenge_section = f"""

CODE REVIEW (revise {target} to address every remark):
{challenge_remarks}
"""
    return (
        f"Implement the {specs.class_name} class in {target}.\n\n"
        f"Spec (JSON):\n{spec_json}{challenge_section}"
    )


def developer_challenger_prompt(specs: DesignSpec) -> str:
    target = module_filename(specs.class_name)
    spec_json = specs.model_dump_json(indent=2)
    return (
        f"Read {target} and review its implementation against the spec.\n\n"
        f"Spec (JSON):\n{spec_json}\n\n"
        f"Report whether the implementation satisfies the spec, with concrete remarks."
    )


def tester_prompt(specs: DesignSpec) -> str:
    target = module_filename(specs.class_name)
    tests = test_filename(specs.class_name)
    expected_methods = [m["name"] for m in specs.methods]
    return (
        f"Read {target}. Write and run pytest tests covering:\n"
        f"- All attributes from spec\n"
        f"- All methods: {', '.join(expected_methods)}\n"
        f"Save tests to {tests} and run them."
    )
