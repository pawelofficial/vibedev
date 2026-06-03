from pathlib import Path

CONFIG = {
    "model": "claude-haiku-4-5",
    "allowed_tools": ["Read", "Edit", "Bash", "Write"],
}

OUTPUT_DIR = Path("vibedev-output")
OUTPUT_DIR.mkdir(exist_ok=True)

LOGS_DIR = OUTPUT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

MAX_ITERATIONS = 3

LOG_LEVEL = "INFO"
