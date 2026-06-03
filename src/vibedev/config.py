from pathlib import Path

CONFIG = {
    "model": "claude-haiku-4-5",
    "allowed_tools": ["Read", "Edit", "Bash", "Write"],
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
