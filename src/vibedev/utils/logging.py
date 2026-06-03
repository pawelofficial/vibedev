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
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = config.LOGS_DIR / f"pipeline_{self.run_id}.log"
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


def _rule(label: str) -> str:
    return f"\n-- {label} " + "-" * max(0, 76 - len(label)) + "\n"


def _format_output(output) -> str:
    if not output:
        return "(no structured output)"
    try:
        return json.dumps(output, indent=2, default=str)
    except (TypeError, ValueError):
        return str(output)


class TranscriptLogger:
    """Single human-readable transcript of the whole agent conversation for one run.

    One block per agent call: its input prompt, anything it said, and the
    structured output it handed to the next agent.
    """

    def __init__(self, run_id: str):
        self.path = config.LOGS_DIR / f"transcript_{run_id}.txt"
        self.path.write_text("", encoding="utf-8")

    def agent(self, role: str, model: str, prompt: str, output, narration: str = "") -> None:
        ts = datetime.now(timezone.utc).isoformat()
        bar = "=" * 80
        block = [
            f"\n{bar}\n {role.upper()}  |  {model}  |  {ts}\n{bar}\n",
            _rule("INPUT"),
            prompt.strip() + "\n",
        ]
        if narration.strip():
            block += [_rule("AGENT SAID"), narration.strip() + "\n"]
        block += [_rule("OUTPUT"), _format_output(output) + "\n"]
        with self.path.open("a", encoding="utf-8") as f:
            f.write("".join(block))


_active_transcript: "TranscriptLogger | None" = None


def start_transcript(run_id: str) -> TranscriptLogger:
    """Begin a fresh transcript for a pipeline run; ``run_agent`` writes to it."""
    global _active_transcript
    _active_transcript = TranscriptLogger(run_id)
    return _active_transcript


def get_transcript() -> "TranscriptLogger | None":
    return _active_transcript


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
