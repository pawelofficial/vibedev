"""Core entry point — drives the Claude Agent SDK on behalf of the user."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk import ClaudeAgentOptions, query

from vibedev.config import Config, get_config
from vibedev.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from vibedev.workspace import create_workspace


def prompt(
    user_prompt: str,
    *,
    workspace: str | Path | None = None,
    quiet: bool = False,
) -> Path:
    """Run an agentic dev session for ``user_prompt``.

    Blocks until the agent is done. Returns the path of the workspace directory
    where the agent worked, so the caller can inspect / open the generated code.
    """
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise ValueError("user_prompt must be a non-empty string")

    cfg = get_config()
    ws = (
        Path(workspace).expanduser().resolve()
        if workspace is not None
        else create_workspace(cfg["workspace_root"])
    )
    ws.mkdir(parents=True, exist_ok=True)

    if not quiet:
        print(f"[vibedev] workspace: {ws}", file=sys.stderr, flush=True)
        print(f"[vibedev] model: {cfg['model']}", file=sys.stderr, flush=True)
        print(f"[vibedev] permissions: {cfg['permission_mode']}", file=sys.stderr, flush=True)

    anyio.run(_run, user_prompt, ws, cfg, quiet)
    return ws


async def _run(user_prompt: str, workspace: Path, cfg: Config, quiet: bool) -> None:
    options = ClaudeAgentOptions(
        cwd=str(workspace),
        permission_mode=cfg["permission_mode"],
        model=cfg["model"],
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    )
    async for message in query(prompt=user_prompt, options=options):
        if not quiet:
            _print_message(message)


def _print_message(message: Any) -> None:
    """Best-effort streaming print of an Agent SDK message.

    The SDK yields a handful of message types (AssistantMessage, UserMessage,
    SystemMessage, ResultMessage). We do not couple to the exact class names
    here — we look for a ``content`` list of blocks and print whatever text is
    in them, ignoring anything else (ResultMessage's ``total_cost_usd`` is
    intentionally skipped: it reports API-pricing equivalents that are
    misleading for users on a Claude.ai subscription).
    """
    content = getattr(message, "content", None)
    if not content:
        return
    for block in content:
        text = getattr(block, "text", None)
        if text:
            print(text, flush=True)
        else:
            block_type = type(block).__name__
            tool_name = getattr(block, "name", None)
            label = f"{block_type}:{tool_name}" if tool_name else block_type
            print(f"[{label}]", flush=True)
