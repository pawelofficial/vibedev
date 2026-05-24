"""Workspace directory resolution for a single vibedev run."""

from __future__ import annotations

from pathlib import Path


def ensure_workspace(path: str | Path) -> Path:
    """Resolve ``path``, create it if missing, and return the absolute Path.

    The agent is scoped to this directory (via the SDK's ``cwd`` option) so a
    run cannot write outside of it. We deliberately do *not* nest into a
    timestamped subdir — the path the caller passes is the path the agent
    works in directly.
    """
    workspace = Path(path).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace
