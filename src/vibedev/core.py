"""Core entry point — drives the Claude Agent SDK on behalf of the user."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

import anyio
from claude_agent_sdk import ClaudeAgentOptions, query

from vibedev.config import Config, get_config
from vibedev.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from vibedev.roles import build_manager_prompt, subagents_for
from vibedev.workspace import ensure_workspace


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
    ws = ensure_workspace(workspace if workspace is not None else cfg["workspace_root"])
    log_path = _prepare_log_path(ws)

    if not quiet:
        print(f"[vibedev] workspace: {ws}", file=sys.stderr, flush=True)
        print(f"[vibedev] model: {cfg['model']}  (main agent)", file=sys.stderr, flush=True)
        print(f"[vibedev] permissions: {cfg['permission_mode']}", file=sys.stderr, flush=True)
        if cfg["team"]:
            parts = [
                f"{role}({model or cfg['model']})" for role, model in cfg["team"]
            ]
            team_label = ", ".join(parts)
        else:
            team_label = "(none — single orchestrator)"
        print(f"[vibedev] team: {team_label}", file=sys.stderr, flush=True)
        print(f"[vibedev] transcript: {log_path}", file=sys.stderr, flush=True)

    anyio.run(_run, user_prompt, ws, cfg, quiet, log_path)
    return ws


def _prepare_log_path(workspace: Path) -> Path:
    """Compute and ensure the per-run transcript log path.

    Logs land in ``<workspace>.vibedev-logs/<UTC-ISO-timestamp>.log`` — a
    sibling directory **next to** the workspace, not inside it. Keeping the
    transcript outside the workspace ensures the agent (whose ``cwd`` is the
    workspace) cannot list, read, or otherwise factor transcript files into
    its own context. The transcript is for the human user, not the agents.

    The plan file at ``<workspace>/.vibedev/plan.md`` stays inside the
    workspace because the agent legitimately needs it for resumption; only
    the logs move out.
    """
    base_name = workspace.name or "vibedev"
    log_dir = workspace.parent / f"{base_name}.vibedev-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return log_dir / f"{ts}.log"


async def _run(
    user_prompt: str,
    workspace: Path,
    cfg: Config,
    quiet: bool,
    log_path: Path,
) -> None:
    if cfg["team"]:
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode=cfg["permission_mode"],
            model=cfg["model"],
            system_prompt=build_manager_prompt(cfg["team"], cfg["model"]),
            agents=subagents_for(cfg["team"], cfg["model"]),
        )
    else:
        options = ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode=cfg["permission_mode"],
            model=cfg["model"],
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        )
    with _TranscriptLogger(log_path) as logger:
        logger.write_header(user_prompt, workspace, cfg)
        try:
            async for message in query(prompt=user_prompt, options=options):
                logger.log_message(message)
                if not quiet:
                    _print_message(message)
        finally:
            logger.write_footer()


class _TranscriptLogger:
    """Writes a per-run transcript of every SDK message to a log file.

    Loose-typed on purpose (mirror of :func:`_print_message`) so SDK
    message-shape changes don't break us. Captures text, thinking, tool_use
    (with full JSON input), and tool_result blocks — including
    ``tool_use_id`` so a result can be correlated with its call.

    Tool results are intentionally **not** truncated: the point of the log is
    to let the user reconstruct what the agent did after the fact, and a
    truncated bash output is the most likely place that reconstruction
    fails. If your log files get unwieldy, prune
    ``<workspace>/.vibedev/runs/`` by hand.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fh: IO[str] = path.open("w", encoding="utf-8")

    def __enter__(self) -> "_TranscriptLogger":
        return self

    def __exit__(self, *_exc: object) -> None:
        self._fh.close()

    def write_header(self, user_prompt: str, workspace: Path, cfg: Config) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        fh = self._fh
        fh.write(f"=== vibedev run started {ts} ===\n")
        fh.write(f"workspace: {workspace}\n")
        fh.write(f"model: {cfg['model']}  (main agent)\n")
        fh.write(f"permissions: {cfg['permission_mode']}\n")
        if cfg["team"]:
            parts = [f"{role}({model or cfg['model']})" for role, model in cfg["team"]]
            fh.write(f"team: {', '.join(parts)}\n")
        else:
            fh.write("team: (none — single orchestrator)\n")
        fh.write("prompt:\n")
        for line in user_prompt.splitlines() or [""]:
            fh.write(f"  {line}\n")
        fh.write("=" * 60 + "\n\n")
        fh.flush()

    def write_footer(self) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._fh.write(f"\n=== vibedev run ended {ts} ===\n")
        self._fh.flush()

    def log_message(self, message: Any) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        msg_type = type(message).__name__
        self._fh.write(f"[{ts}] {msg_type}\n")
        content = getattr(message, "content", None)
        if content:
            for block in content:
                self._log_block(block)
        else:
            for attr in ("subtype", "is_error", "session_id", "duration_ms", "num_turns"):
                val = getattr(message, attr, None)
                if val is not None:
                    self._fh.write(f"  {attr}: {val}\n")
        self._fh.write("\n")
        self._fh.flush()

    def _log_block(self, block: Any) -> None:
        block_type = type(block).__name__
        text = getattr(block, "text", None)
        thinking = getattr(block, "thinking", None)
        tool_name = getattr(block, "name", None)
        tool_input = getattr(block, "input", None)
        tool_use_id = getattr(block, "tool_use_id", None)

        if text is not None:
            self._write_indented("text:", str(text))
        elif thinking is not None:
            self._write_indented("thinking:", str(thinking))
        elif tool_name is not None and tool_input is not None:
            self._fh.write(f"  tool_use: {tool_name}\n")
            try:
                rendered = json.dumps(tool_input, indent=2, default=str)
            except (TypeError, ValueError):
                rendered = repr(tool_input)
            for line in rendered.splitlines():
                self._fh.write(f"    {line}\n")
        elif tool_use_id is not None:
            # ToolResultBlock — content is either a string or a list of
            # nested content blocks (text/image), depending on SDK version.
            result_content = getattr(block, "content", None)
            self._fh.write(f"  tool_result (id={tool_use_id}):\n")
            for line in _render_tool_result(result_content).splitlines() or [""]:
                self._fh.write(f"    {line}\n")
        else:
            self._fh.write(f"  [{block_type}]\n")

    def _write_indented(self, header: str, body: str) -> None:
        self._fh.write(f"  {header}\n")
        for line in body.splitlines() or [""]:
            self._fh.write(f"    {line}\n")


def _render_tool_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            t = getattr(item, "text", None)
            if t is not None:
                parts.append(str(t))
            else:
                parts.append(repr(item))
        return "\n".join(parts)
    return repr(result)


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
