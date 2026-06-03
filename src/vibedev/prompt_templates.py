import json
import re

from vibedev.models import FileSpec, ProjectSpec, TestReport


LEAD_DEVELOPER_SYSTEM = (
    "You are a senior software architect. "
    "Design a small multi-file Python project as a precise, very short spec. "
    "The TOP-LEVEL object you return is always the project (project_name, "
    "description, files) — never a bare class. Even a single class is one file "
    "containing one component. "
    "Break the work into files; for each file list its path, the classes/functions "
    "it contains, and which other files it imports from (depends_on). "
    "Keep dependencies acyclic. Do NOT write code. Respond with structured JSON only. "
    "If given tester feedback or challenge remarks, revise your spec to address every point."
)

# Spelled out in the user message too: the SDK enforces this schema, but weak
# models otherwise emit a bare class and miss the project envelope.
PROJECT_SHAPE_HINT = (
    "Return a project spec with these EXACT top-level keys:\n"
    "- project_name (str)\n"
    "- description (str)\n"
    "- files (list) — each file has: path (str), description (str), "
    "components (list), depends_on (list of file paths)\n"
    "Each component has: name (str), kind ('class' or 'function'), description (str), "
    "attributes (list), methods (list), notes (list).\n"
    "Even for a single class, wrap it: one file with one component."
)

LEAD_DEVELOPER_EVOLVE_SYSTEM = (
    "You are a senior software architect EXTENDING an existing multi-file Python project "
    "with a new feature. You are given the current project spec, and the code for it is on "
    "disk in your working directory — Read the files you intend to touch so your changes "
    "match what is really there. "
    "Add the requested feature with MINIMAL disruption: prefer extending existing files and "
    "components; add new files only when genuinely needed; do not redesign what already "
    "works. "
    "Return the FULL updated project spec (every file, including untouched ones, so the spec "
    "stays complete). For EVERY file set 'change' to exactly one of: 'new' (file does not "
    "exist yet), 'modified' (existing file you are changing), 'unchanged' (existing file you "
    "are NOT changing). Keep dependencies acyclic. Do NOT write code. Respond with structured "
    "JSON only. If given tester feedback or challenge remarks, revise to address every point."
)

# Like PROJECT_SHAPE_HINT but reminds the evolve step to tag every file's change kind.
EVOLVE_SHAPE_HINT = (
    PROJECT_SHAPE_HINT
    + "\nAdditionally, set each file's 'change' to 'new', 'modified', or 'unchanged'. "
    "Include unchanged files unchanged so the returned spec describes the whole project."
)

LEAD_DEVELOPER_CHALLENGER_SYSTEM = (
    "You are a senior architect reviewing another architect's multi-file project spec. "
    "Critique it against the user's request: missing or unnecessary files/components, "
    "high-level architectural mistakes, poor module boundaries, wrong types, scope creep, "
    "and especially cross-file problems — circular or missing depends_on, an interface "
    "declared in one file but used inconsistently in another. "
    "Be strict but fair — approve only when the spec is genuinely sound. "
    "Respond with structured JSON only: set 'approved' and list concrete 'remarks'."
)

DEVELOPER_SYSTEM = (
    "You are a Python developer implementing ONE file of a larger project. "
    "Implement exactly what the file spec says, nothing more. "
    "Read the files this one depends on so your imports and signatures match them. "
    "Write a brand-new file in full; on a revision, make targeted edits and do not "
    "regenerate code that is already correct. "
    "Create parent directories as needed so nested paths are preserved. "
    "If given code-review remarks, revise the implementation to address every point."
)

DEVELOPER_CHALLENGER_SYSTEM = (
    "You are a senior engineer doing code review on a single file. "
    "Read the implementation file and critique it against its spec: missing or "
    "incorrect components, wrong signatures, bugs, broken imports of sibling files, "
    "and sloppy code. "
    "Be strict but fair — approve only when the file faithfully and cleanly satisfies "
    "its spec. "
    "Respond with structured JSON only: set 'approved' and list concrete 'remarks'."
)

TESTER_SYSTEM = (
    "You are a QA engineer testing a multi-file Python project. "
    "Read the implementation files, write pytest tests covering every component "
    "(class/function) across all files, save them, and run the whole suite with Bash. "
    "Report results as structured JSON."
)


def module_filename(class_name: str) -> str:
    """Suggested snake_case module name for a CamelCase class (naming hint only;
    the spec carries explicit file paths)."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()
    return f"{s}.py"


def test_filename(path: str) -> str:
    """Map a module path to a test path in the same directory: store/cart.py -> store/test_cart.py."""
    parts = path.rsplit("/", 1)
    head, name = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
    return f"{head + '/' if head else ''}test_{name}"


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
    return (
        f"{user_prompt.rstrip('.')}.{feedback_section}{challenge_section}\n\n"
        f"{PROJECT_SHAPE_HINT}"
    )


def lead_developer_evolve_prompt(
    feature_prompt: str,
    current: ProjectSpec,
    feedback: TestReport | None = None,
    challenge_remarks: str = "",
) -> str:
    spec_json = current.model_dump_json(indent=2)
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
    return (
        f"Existing project: {current.project_name} — {current.description}\n"
        f"Its code is on disk in the working directory; Read the files you will change.\n\n"
        f"Current project spec (JSON):\n{spec_json}\n\n"
        f"NEW FEATURE TO ADD:\n{feature_prompt.rstrip('.')}."
        f"{feedback_section}{challenge_section}\n\n"
        f"{EVOLVE_SHAPE_HINT}"
    )


def lead_developer_challenger_prompt(project: ProjectSpec, user_prompt: str) -> str:
    spec_json = project.model_dump_json(indent=2)
    return (
        f"User request: {user_prompt.rstrip('.')}.\n\n"
        f"Proposed project spec (JSON):\n{spec_json}\n\n"
        f"Review this spec against the request and report your critique."
    )


def developer_prompt(
    file: FileSpec, project: ProjectSpec, challenge_remarks: str = "", modify: bool = False
) -> str:
    file_json = file.model_dump_json(indent=2)
    deps = ", ".join(file.depends_on) if file.depends_on else "none"
    all_paths = ", ".join(f.path for f in project.files)
    modify_section = ""
    if modify:
        modify_section = (
            f"\n\nThis file ALREADY EXISTS on disk. Read it first, then make TARGETED EDITS to "
            f"add only the new behavior the spec describes. Preserve the existing working code; "
            f"do not rewrite the file from scratch."
        )
    challenge_section = ""
    if challenge_remarks:
        challenge_section = f"""

CODE REVIEW (revise {file.path} to address every remark):
{challenge_remarks}
"""
    return (
        f"Project: {project.project_name} — {project.description}\n"
        f"All files in the project: {all_paths}\n\n"
        f"Implement the file {file.path}.\n"
        f"It depends on (read these for matching imports/signatures): {deps}\n\n"
        f"File spec (JSON):\n{file_json}{modify_section}{challenge_section}"
    )


def developer_challenger_prompt(file: FileSpec) -> str:
    file_json = file.model_dump_json(indent=2)
    return (
        f"Read {file.path} and review its implementation against the spec.\n\n"
        f"File spec (JSON):\n{file_json}\n\n"
        f"Report whether the implementation satisfies the spec, with concrete remarks."
    )


def tester_prompt(project: ProjectSpec, files_to_test: list[FileSpec] | None = None) -> str:
    """Build the tester prompt. ``files_to_test=None`` tests the whole project; a subset
    scopes testing to just those files (their tests are run, the rest read for context)."""
    targets = project.files if files_to_test is None else files_to_test

    def _line(f: FileSpec) -> str:
        names = ", ".join(c.name for c in f.components) or "(no components)"
        return f"- {f.path}: {names} -> tests in {test_filename(f.path)}"

    files_block = "\n".join(_line(f) for f in targets)

    if files_to_test is None:
        body = (
            f"Read these files and write pytest tests covering every component:\n"
            f"{files_block}\n\n"
            f"Run the whole test suite with pytest and report the results."
        )
    else:
        all_paths = ", ".join(f.path for f in project.files)
        test_paths = " ".join(test_filename(f.path) for f in targets)
        body = (
            f"The full project contains: {all_paths}\n\n"
            f"Only these files changed and need testing — write or update pytest tests "
            f"covering every component in them:\n{files_block}\n\n"
            f"Run pytest on just those test files ({test_paths}) and report the results. "
            f"Read the other project files as needed for imports and signatures."
        )
    return f"Project: {project.project_name} — {project.description}\n\n{body}"
