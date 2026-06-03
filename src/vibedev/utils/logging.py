import json
import logging
from datetime import datetime, timezone

from vibedev import config


def get_pipeline_logger() -> logging.Logger:
    """Console logger for pipeline progress; level follows ``config.LOG_LEVEL``."""
    name = "vibedev.pipeline"
    log = logging.getLogger(name)
    if log.handlers:
        return log
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    log.propagate = False
    return log


class PipelineLogger:
    """Structured JSON log for pipeline orchestration (spec, dev, test loops)."""

    def __init__(self, user_prompt: str):
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = config.LOGS_DIR / f"pipeline_{run_id}.log"
        self._lines: list[str] = []
        self._console = get_pipeline_logger()
        self.log("pipeline_start", user_prompt=user_prompt)

    def log(self, event: str, **kwargs) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kwargs}
        self._lines.append(json.dumps(entry, default=str))

    def info(self, message: str) -> None:
        self._console.info(message)

    def flush(self) -> None:
        self.path.write_text("\n".join(self._lines) + "\n")
        self._console.info(f"  → Pipeline log: {self.path}")


class ConversationLogger:
    def __init__(self, session_id: str, role: str):
        self.path = config.LOGS_DIR / f"{session_id}_{role.lower().replace(' ', '_')}_conversation.log"
        self._lines: list[str] = []

    def log(self, event: str, **kwargs):
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kwargs}
        self._lines.append(json.dumps(entry, default=str))

    def flush(self):
        self.path.write_text("\n".join(self._lines) + "\n")
        print(f"  → Log: {self.path}")
