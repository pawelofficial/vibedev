"""vibedev — agentic development as a Python package.

Typical use:

    import vibedev
    vibedev.run("Design a Dog class in Python")

Generated code and logs land in ``./vibedev-output/`` (created if missing).
"""

import asyncio
from pathlib import Path

from vibedev.config import LOG_LEVEL
from vibedev.pipeline import run_pipeline

__version__ = "0.1.0"
__all__ = ["run", "run_async", "prompt", "set_output_dir", "LOG_LEVEL", "__version__"]


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


prompt = run
