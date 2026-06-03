import json
import re

from vibedev.models import DesignSpec, TestReport


LEAD_DEVELOPER_SYSTEM = (
    "You are a senior software architect. "
    "Output a precise, very short design spec for a Python class. "
    "Do NOT write code. Respond with structured JSON only. "
    "If given tester feedback, revise your spec to address every point."
)

DEVELOPER_SYSTEM = (
    "You are a Python developer. "
    "Implement exactly what the spec says, nothing more. "
    "Always overwrite the target module file completely."
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


def lead_developer_prompt(user_prompt: str, feedback: TestReport | None = None) -> str:
    feedback_section = ""
    if feedback:
        feedback_section = f"""

TESTER FEEDBACK (address all of this):
- Summary: {feedback.summary}
- Missing features: {', '.join(feedback.missing_features)}
- Failed tests: {json.dumps(feedback.failed_tests, indent=2)}
"""
    return f"{user_prompt.rstrip('.')}.{feedback_section}"


def developer_prompt(specs: DesignSpec) -> str:
    target = module_filename(specs.class_name)
    spec_json = specs.model_dump_json(indent=2)
    return (
        f"Implement the {specs.class_name} class in {target}.\n\n"
        f"Spec (JSON):\n{spec_json}"
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
