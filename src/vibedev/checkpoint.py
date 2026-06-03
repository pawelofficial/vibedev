"""Durable, resumable pipeline state.

The generated code already lives on disk the moment each file is written; what an
interrupted run (e.g. token exhaustion) loses is only the *orchestration* state held in
memory — the current spec, how far the build got, which test iteration we're on. This
module persists exactly that to ``checkpoint.json`` in the output dir, written atomically
at each phase/file boundary, so ``run_pipeline`` can pick up where it left off.

Resume is best-effort and keyed to the user prompt: a checkpoint is only reused if it
exists, matches the prompt, and isn't already ``complete``.
"""

import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

from vibedev import config

CHECKPOINT_NAME = "checkpoint.json"

# Pipeline phases, in order. "designing" means no spec is saved yet (a crash here just
# re-designs); "building" means a spec exists and files are being written; "testing"
# means the build finished and we're in the test/revise loop; "complete" is a tombstone.
PHASE_DESIGNING = "designing"
PHASE_BUILDING = "building"
PHASE_TESTING = "testing"
PHASE_COMPLETE = "complete"


class Checkpoint(BaseModel):
    """Everything needed to resume a pipeline run mid-flight."""

    user_prompt: str
    run_id: str
    phase: str = PHASE_DESIGNING
    iteration: int = 0  # completed outer test iterations
    spec: dict | None = None  # current ProjectSpec, as model_dump()
    built_paths: list[str] = []  # files finished in the *current* build pass
    last_report: dict | None = None  # most recent TestReport, for transparency


def checkpoint_path() -> Path:
    # Resolved at call time — set_output_dir() can move OUTPUT_DIR after import.
    return config.OUTPUT_DIR / CHECKPOINT_NAME


def save_checkpoint(cp: Checkpoint) -> None:
    """Persist the checkpoint atomically (temp file + ``os.replace``) so a crash mid-write
    can never leave a half-written, unparseable resume file."""
    path = checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cp.model_dump_json(indent=2))
        os.replace(tmp, path)  # atomic rename on the same filesystem
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_checkpoint() -> Checkpoint | None:
    """Read the checkpoint, or None if absent / unparseable (corrupt → start fresh)."""
    path = checkpoint_path()
    if not path.exists():
        return None
    try:
        return Checkpoint.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def resume_checkpoint(user_prompt: str) -> Checkpoint | None:
    """Return a checkpoint to resume from — one that exists, matches this prompt, and is
    not already complete. Otherwise None, meaning start a fresh run."""
    cp = load_checkpoint()
    if cp is None or cp.phase == PHASE_COMPLETE or cp.user_prompt != user_prompt:
        return None
    return cp
