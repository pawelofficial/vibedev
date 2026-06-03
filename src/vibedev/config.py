from pathlib import Path

# Repo root (…/src/vibedev/config.py -> repo root). Used as the default extra
# directory agents may touch beyond their output sandbox.
REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG = {
    "model": "claude-haiku-4-5",
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

LOG_LEVEL = "INFO"
