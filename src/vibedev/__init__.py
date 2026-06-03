"""vibedev — agentic development as a Python package.

Typical use:

    import vibedev
    vibedev.run("Design a Dog class in Python")

Generated code and logs land in ``./vibedev-output/`` (created if missing).
"""

import asyncio
from pathlib import Path

from vibedev.config import LOG_LEVEL
from vibedev.pipeline import continue_pipeline, run_pipeline

__version__ = "0.1.0"
__all__ = [
    "run",
    "run_async",
    "continue_development",
    "continue_development_async",
    "prompt",
    "set_output_dir",
    "LOG_LEVEL",
    "__version__",
]


def set_output_dir(path: str | Path) -> None:
    """Change where agents write code and logs (default: ./vibedev-output/)."""
    import vibedev.config as cfg

    cfg.OUTPUT_DIR = Path(path)
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg.LOGS_DIR = cfg.OUTPUT_DIR / "logs"
    cfg.LOGS_DIR.mkdir(exist_ok=True)


async def run_async(user_prompt: str) -> None:
    """Run the lead-developer → developer → tester pipeline."""
    await run_pipeline(user_prompt)


def run(user_prompt: str) -> None:
    """Run the pipeline synchronously (blocks until complete)."""
    asyncio.run(run_async(user_prompt))


async def continue_development_async(feature_prompt: str, test_scope: str = "all") -> None:
    """Extend the existing project in the output dir with a new feature.

    Reads the project manifest written by a previous ``run`` (``project.json``), so a
    fresh session knows what's already there, then builds only the files the feature
    touches. Requires a prior ``run`` to have produced a project.

    ``test_scope`` selects what the tester covers:
    - ``"all"`` (default): test the whole project.
    - ``"changed"``: test only the new/modified files (fastest, but won't catch breakage a
      change causes in files that depend on it).
    - ``"affected"``: test the changed files plus everything that transitively depends on
      them (a middle ground between ``"changed"`` and ``"all"``).
    """
    await continue_pipeline(feature_prompt, test_scope=test_scope)


def continue_development(feature_prompt: str, test_scope: str = "all") -> None:
    """Extend the existing project synchronously (blocks until complete)."""
    asyncio.run(continue_development_async(feature_prompt, test_scope=test_scope))


prompt = run
