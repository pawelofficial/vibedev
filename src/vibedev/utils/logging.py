import json
from datetime import datetime, timezone

from vibedev import config


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
