"""Core entry point — drives the Claude Agent SDK on behalf of the user."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

import anyio
from claude_agent_sdk import ClaudeAgentOptions, query

from vibedev.config import Config, get_config
from vibedev.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from vibedev.roles import (
    BUSINESS_ANALYST_PROMPT,
    DEVELOPER_PROMPT,
    TESTER_PROMPT,
    build_manager_prompt,
    subagents_for,
)
from vibedev.workspace import ensure_workspace

MAX_TEAM_FIX_ATTEMPTS = 3
PLAN_RELATIVE_PATH = Path(".vibedev") / "plan.md"

README_UPDATER_SYSTEM_PROMPT = """You update README files after a vibedev team run.

Python code outside the model has already coordinated planning, implementation,
testing, and plan checkoff. Your only job is to update `README.md` so it
accurately summarizes the current project and how to run or test it.

Do not edit `.vibedev/plan.md`. Do not implement feature code.
"""


@dataclass
class _PlanTask:
    done: bool
    text: str


@dataclass
class _TeamPlan:
    goal: str
    tasks: list[_PlanTask]
    history: list[str]


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
    with _TranscriptLogger(log_path) as logger:
        logger.write_header(user_prompt, workspace, cfg)
        try:
            if _supports_coded_team_workflow(cfg["team"]):
                await _run_coded_team_workflow(user_prompt, workspace, cfg, quiet, logger)
            else:
                options = _options_for_orchestrator(workspace, cfg)
                await _run_query(user_prompt, options, logger, quiet)
        finally:
            logger.write_footer()


def _options_for_orchestrator(workspace: Path, cfg: Config) -> ClaudeAgentOptions:
    if cfg["team"]:
        return ClaudeAgentOptions(
            cwd=str(workspace),
            permission_mode=cfg["permission_mode"],
            model=cfg["model"],
            system_prompt=build_manager_prompt(cfg["team"], cfg["model"]),
            agents=subagents_for(cfg["team"], cfg["model"]),
        )
    return ClaudeAgentOptions(
        cwd=str(workspace),
        permission_mode=cfg["permission_mode"],
        model=cfg["model"],
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    )


def _options_for_role(
    workspace: Path,
    cfg: Config,
    *,
    model: str,
    system_prompt: str,
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=str(workspace),
        permission_mode=cfg["permission_mode"],
        model=model,
        system_prompt=system_prompt,
    )


async def _run_coded_team_workflow(
    user_prompt: str,
    workspace: Path,
    cfg: Config,
    quiet: bool,
    logger: "_TranscriptLogger",
) -> None:
    developer_model = _first_role_model(cfg["team"], "developer", cfg["model"])
    tester_model = _first_role_model(cfg["team"], "tester", cfg["model"])
    analyst_model = _first_role_model(cfg["team"], "business_analyst", cfg["model"])
    assert developer_model is not None
    assert tester_model is not None

    plan = _load_or_create_team_plan(workspace, user_prompt)
    analyst_brief = ""
    if analyst_model is not None:
        analyst_options = _options_for_role(
            workspace,
            cfg,
            model=analyst_model,
            system_prompt=BUSINESS_ANALYST_PROMPT,
        )
        _announce_stage("business analyst plan review", logger, quiet)
        analyst_brief = await _run_query(
            _build_business_analyst_prompt(user_prompt, plan),
            analyst_options,
            logger,
            quiet,
        )
        _apply_analyst_review(workspace, plan, analyst_brief)

    task_index = _next_pending_task_index(plan)
    if task_index is None:
        return
    task = plan.tasks[task_index].text

    developer_options = _options_for_role(
        workspace,
        cfg,
        model=developer_model,
        system_prompt=DEVELOPER_PROMPT,
    )
    tester_options = _options_for_role(
        workspace,
        cfg,
        model=tester_model,
        system_prompt=TESTER_PROMPT,
    )
    readme_options = _options_for_role(
        workspace,
        cfg,
        model=cfg["model"],
        system_prompt=README_UPDATER_SYSTEM_PROMPT,
    )

    tester_report = ""
    developer_report = ""
    for attempt in range(1, MAX_TEAM_FIX_ATTEMPTS + 1):
        label = f"developer attempt {attempt}: {task}"
        _announce_stage(label, logger, quiet)
        developer_report = await _run_query(
            _build_developer_prompt(task, attempt, tester_report, analyst_brief),
            developer_options,
            logger,
            quiet,
        )

        label = f"tester attempt {attempt}: {task}"
        _announce_stage(label, logger, quiet)
        tester_report = await _run_query(
            _build_tester_prompt(task, attempt, developer_report, analyst_brief),
            tester_options,
            logger,
            quiet,
        )

        verdict = _extract_verdict(tester_report)
        if verdict is True:
            _mark_plan_task_done(workspace, plan, task_index)
            plan_text_after_checkoff = _read_plan_text(workspace)
            _announce_stage("update README after passed team run", logger, quiet)
            await _run_query(
                _build_readme_update_prompt(task, developer_report, tester_report),
                readme_options,
                logger,
                quiet,
            )
            _restore_plan_if_changed(workspace, plan_text_after_checkoff)
            return

        if verdict is None:
            tester_report = (
                "Tester did not provide `VIBEDEV_VERDICT: PASS`; treat this "
                "as a failed or inconclusive verification.\n\n"
                f"{tester_report}"
            )

    _record_plan_blocker(workspace, plan, task_index, tester_report)
    raise RuntimeError(
        "vibedev team workflow stopped with failing or inconclusive tests "
        f"after {MAX_TEAM_FIX_ATTEMPTS} attempt(s)"
    )


async def _run_query(
    prompt_text: str,
    options: ClaudeAgentOptions,
    logger: "_TranscriptLogger",
    quiet: bool,
) -> str:
    text_parts: list[str] = []
    async for message in query(prompt=prompt_text, options=options):
        logger.log_message(message)
        text = _message_text(message)
        if text:
            text_parts.append(text)
        if not quiet:
            _print_message(message)
    return "\n".join(text_parts).strip()


def _supports_coded_team_workflow(team: list[tuple[str, str | None]]) -> bool:
    roles = {role for role, _model in team}
    return "developer" in roles and "tester" in roles


def _first_role_model(
    team: list[tuple[str, str | None]],
    role_name: str,
    default_model: str,
) -> str | None:
    for role, model in team:
        if role == role_name:
            return model or default_model
    return None


def _extract_verdict(text: str) -> bool | None:
    verdict: bool | None = None
    for line in text.splitlines():
        normalized = line.strip().upper()
        if normalized == "VIBEDEV_VERDICT: PASS":
            verdict = True
        elif normalized == "VIBEDEV_VERDICT: FAIL":
            verdict = False
    return verdict


def _message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if not content:
        return ""
    parts = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts)


def _announce_stage(label: str, logger: "_TranscriptLogger", quiet: bool) -> None:
    logger.write_stage(label)
    if not quiet:
        print(f"[vibedev] {label}", file=sys.stderr, flush=True)


def _build_business_analyst_prompt(user_prompt: str, plan: _TeamPlan) -> str:
    return f"""User request:
{user_prompt}

Current Python-owned plan:
{_render_plan_for_prompt(plan)}

Review the request and plan before implementation starts. Challenge the plan:
identify missing requirements, ambiguities, risks, proposed task additions, and
acceptance criteria.

Return structured Markdown with exactly these top-level sections:

## Missing Requirements

## Proposed Tasks

## Acceptance Criteria

## Risks
"""


def _render_plan_for_prompt(plan: _TeamPlan) -> str:
    lines = [
        f"Goal: {plan.goal}",
        "",
        "Tasks:",
    ]
    for task in plan.tasks:
        marker = "x" if task.done else " "
        lines.append(f"- [{marker}] {task.text}")
    if plan.history:
        lines.extend(["", "History:"])
        lines.extend(f"- {entry}" for entry in plan.history[-5:])
    return "\n".join(lines)


def _apply_analyst_review(workspace: Path, plan: _TeamPlan, analyst_brief: str) -> None:
    proposed_tasks = _extract_proposed_tasks(analyst_brief)
    added = False
    for task_text in proposed_tasks:
        if _add_plan_task_if_missing(plan, task_text):
            added = True

    if analyst_brief.strip():
        summary = _one_line(analyst_brief)[:500]
        plan.history.append(f"{_today()} - Analyst review: {summary}")
        added = True

    if added:
        _write_team_plan(workspace, plan)


def _extract_proposed_tasks(analyst_brief: str) -> list[str]:
    lines = analyst_brief.splitlines()
    in_section = False
    tasks: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = stripped.casefold() == "## proposed tasks"
            continue
        if not in_section:
            continue

        task = _task_text_from_markdown_bullet(stripped)
        if task:
            tasks.append(task)

    return tasks


def _task_text_from_markdown_bullet(line: str) -> str | None:
    task = _parse_task_line(line)
    if task is not None:
        return task.text
    for prefix in ("- ", "* "):
        if line.startswith(prefix):
            text = line[len(prefix) :].strip()
            return text or None
    return None


def _load_or_create_team_plan(workspace: Path, user_prompt: str) -> _TeamPlan:
    path = workspace / PLAN_RELATIVE_PATH
    if path.exists():
        plan = _parse_team_plan(path.read_text(encoding="utf-8"), user_prompt)
    else:
        plan = _TeamPlan(goal=_one_line(user_prompt), tasks=[], history=[])

    _add_plan_task_if_missing(plan, user_prompt)
    plan.history.append(f"{_today()} - Request: {_one_line(user_prompt)}")
    _write_team_plan(workspace, plan)
    return plan


def _parse_team_plan(text: str, fallback_goal: str) -> _TeamPlan:
    section = ""
    goal_lines: list[str] = []
    tasks: list[_PlanTask] = []
    history: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped == "## Goal":
            section = "goal"
            continue
        if stripped == "## Tasks":
            section = "tasks"
            continue
        if stripped == "## History":
            section = "history"
            continue
        if stripped.startswith("## "):
            section = ""
            continue

        if section == "goal" and stripped:
            goal_lines.append(stripped)
        elif section == "tasks":
            task = _parse_task_line(stripped)
            if task is not None:
                tasks.append(task)
        elif section == "history" and stripped.startswith("- "):
            history.append(stripped[2:].strip())

    goal = " ".join(goal_lines).strip() or _one_line(fallback_goal)
    return _TeamPlan(goal=goal, tasks=tasks, history=history)


def _parse_task_line(line: str) -> _PlanTask | None:
    if line.startswith("- [x] "):
        return _PlanTask(done=True, text=line[6:].strip())
    if line.startswith("- [X] "):
        return _PlanTask(done=True, text=line[6:].strip())
    if line.startswith("- [ ] "):
        return _PlanTask(done=False, text=line[6:].strip())
    return None


def _add_plan_task_if_missing(plan: _TeamPlan, task_text: str) -> bool:
    task_text = _one_line(task_text)
    if not task_text:
        return False
    existing = {_normalize_task(task.text) for task in plan.tasks}
    if _normalize_task(task_text) not in existing:
        plan.tasks.append(_PlanTask(done=False, text=task_text))
        return True
    return False


def _next_pending_task_index(plan: _TeamPlan) -> int | None:
    for index, task in enumerate(plan.tasks):
        if not task.done:
            return index
    return None


def _mark_plan_task_done(workspace: Path, plan: _TeamPlan, task_index: int) -> None:
    plan.tasks[task_index].done = True
    plan.history.append(f"{_today()} - Completed: {plan.tasks[task_index].text}")
    _write_team_plan(workspace, plan)


def _record_plan_blocker(
    workspace: Path,
    plan: _TeamPlan,
    task_index: int,
    tester_report: str,
) -> None:
    plan.tasks[task_index].done = False
    summary = _one_line(tester_report)[:500] or "tester did not report a passing verdict"
    plan.history.append(
        f"{_today()} - Blocked: {plan.tasks[task_index].text} ({summary})"
    )
    _write_team_plan(workspace, plan)


def _write_team_plan(workspace: Path, plan: _TeamPlan) -> None:
    path = workspace / PLAN_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# vibedev plan",
        "",
        "## Goal",
        plan.goal.strip(),
        "",
        "## Tasks",
    ]
    for task in plan.tasks:
        marker = "x" if task.done else " "
        lines.append(f"- [{marker}] {task.text}")
    lines.extend(["", "## History"])
    for entry in plan.history:
        lines.append(f"- {entry}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _read_plan_text(workspace: Path) -> str:
    return (workspace / PLAN_RELATIVE_PATH).read_text(encoding="utf-8")


def _restore_plan_if_changed(workspace: Path, expected_text: str) -> None:
    path = workspace / PLAN_RELATIVE_PATH
    if path.read_text(encoding="utf-8") != expected_text:
        path.write_text(expected_text, encoding="utf-8")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _one_line(text: str) -> str:
    return " ".join(text.split()).strip()


def _normalize_task(text: str) -> str:
    return _one_line(text).casefold()


def _build_developer_prompt(
    task: str,
    attempt: int,
    tester_report: str,
    analyst_brief: str = "",
) -> str:
    analyst_section = _analyst_context_section(analyst_brief)
    if attempt == 1:
        return f"""Task:
{task}
{analyst_section}

Implement this task inside the current workspace. Python owns the plan file and
will send your work to the tester before marking anything complete.

When you finish, report the files changed, commands run, and what the tester
should verify.
"""

    return f"""Task:
{task}
{analyst_section}

The tester found failures in the previous attempt. Fix the implementation
without weakening the requested behavior or deleting useful tests.

Tester report:
{tester_report}

After the fix, report the files changed, commands run, and what the tester
should re-run.
"""


def _build_tester_prompt(
    task: str,
    attempt: int,
    developer_report: str,
    analyst_brief: str = "",
) -> str:
    analyst_section = _analyst_context_section(analyst_brief)
    return f"""Task:
{task}
{analyst_section}

Developer attempt: {attempt}

Developer report:
{developer_report}

Verify the changed scope. Write or update focused tests when useful, run the
relevant checks, and report exact failures with the failing command and
smallest reproducer.

End your response with exactly one verdict line:
VIBEDEV_VERDICT: PASS
or
VIBEDEV_VERDICT: FAIL
"""


def _analyst_context_section(analyst_brief: str) -> str:
    if not analyst_brief.strip():
        return ""
    return f"""

Business analyst brief and acceptance criteria:
{analyst_brief.strip()}
"""


def _build_readme_update_prompt(
    task: str,
    developer_report: str,
    tester_report: str,
) -> str:
    return f"""Completed task:
{task}

Developer report:
{developer_report}

Tester report:
{tester_report}

Update `README.md` according to your system instructions. Do not edit
`.vibedev/plan.md`.
"""


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

    def write_stage(self, label: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._fh.write(f"[{ts}] stage: {label}\n\n")
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
