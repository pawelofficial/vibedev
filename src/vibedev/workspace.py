"""Workspace directory resolution for a single vibedev run."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def create_workspace(root: str | Path) -> Path:
    """Create and return a fresh timestamped subdirectory under ``root``.

    The agent is scoped to this directory (via the SDK's ``cwd`` option) so a
    run can never overwrite files outside of it.
    """
    root_path = Path(root).expanduser().resolve()
    root_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    workspace = root_path / timestamp

    # If two runs start in the same second, suffix with -1, -2, ...
    suffix = 1
    candidate = workspace
    while candidate.exists():
        candidate = root_path / f"{timestamp}-{suffix}"
        suffix += 1

    candidate.mkdir()
    return candidate
