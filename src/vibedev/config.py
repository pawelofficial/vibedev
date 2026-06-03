from pathlib import Path

# Repo root (…/src/vibedev/config.py -> repo root). Used as the default extra
# directory agents may touch beyond their output sandbox.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Default model for every agent role.
DEFAULT_MODEL = "claude-haiku-4-5"
SONNET_MODEL = "claude-sonnet-4-6"
# Per-role model overrides (keys are the role names passed to run_agent). The two
# roles that produce code/specs run on a stronger model; the critics and tester
# stay on the cheaper default. Roles not listed fall back to DEFAULT_MODEL.
ROLE_MODELS = {
    "Lead Developer": SONNET_MODEL,
    "Software Developer": SONNET_MODEL,
    "Lead Developer Challenger": DEFAULT_MODEL,
    "Software Developer Challenger": DEFAULT_MODEL,
    "Tester": DEFAULT_MODEL,
}


def model_for(role: str) -> str:
    """Resolve the model for an agent role, falling back to DEFAULT_MODEL."""
    return ROLE_MODELS.get(role, DEFAULT_MODEL)


CONFIG = {
    # Tools every agent may use. Beyond file/Bash editing, Glob/Grep let agents
    # navigate larger multi-file projects and Web* let them look up library APIs.
    "allowed_tools": [
        "Read",
        "Edit",
        "Bash",
        "Write",
        "Glob",
        "Grep",
        "WebFetch",
        "WebSearch",
    ],
    # Run unattended: don't prompt/block on tool use. The pipeline drives query()
    # non-interactively, so anything that would prompt would otherwise stall.
    "permission_mode": "bypassPermissions",
    # Directories agents may access in addition to cwd (OUTPUT_DIR). Defaults to the
    # whole repo so agents can read/write beyond vibedev-output/. Trim for less reach.
    "extra_dirs": [str(REPO_ROOT)],
}

OUTPUT_DIR = Path("vibedev-output")
OUTPUT_DIR.mkdir(exist_ok=True)

LOGS_DIR = OUTPUT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

MAX_ITERATIONS = 5

# How many times a challenger may push back on a spec/implementation before we
# accept the latest version and move on. Kept small to bound cost and latency.
MAX_CHALLENGE_ITERATIONS = 2

# When an agent finishes its work but doesn't emit valid structured output, we
# don't redo the (expensive) agent work — we take the text it produced and make a
# cheap, tool-less call that reshapes just that text into the schema. This bounds
# how many times that coercion call may be retried before the run fails.
MAX_STRUCTURED_OUTPUT_ATTEMPTS = 3

LOG_LEVEL = "INFO"
