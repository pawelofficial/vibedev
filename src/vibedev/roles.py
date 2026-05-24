"""Role catalog for vibedev's team mode.

A *role* is a named system prompt that vibedev can assign to an agent. When
the user calls ``vibedev.set_team([...])`` with subagent role names, vibedev:

  - sets the *main* agent's system prompt to a manager prompt that lists the
    exact subagents on the team, and
  - exposes each named subagent via ``ClaudeAgentOptions.agents`` so the
    manager can delegate work via the Task tool.

Available subagent roles live in :data:`SUBAGENT_ROLES`. The ``manager`` role
is **implicit** — it is always the main agent when a team is configured, and
users must not list it in ``set_team(...)``.
"""

from __future__ import annotations

from dataclasses import replace

from claude_agent_sdk import AgentDefinition

DEVELOPER_PROMPT = """You are the developer on a vibedev team.

You receive concrete coding tasks from the manager and execute them inside the
shared workspace (the current working directory). You write files, install
dependencies, and run commands. Be decisive about implementation choices.

Critical rule — do NOT leave long-running processes alive when you finish a
task:
- For web servers (Flask, FastAPI, Express, etc.): never run the dev server in
  the foreground to "see if it works". Verify with the framework's test
  client (``app.test_client()`` for Flask, ``TestClient`` for FastAPI) or a
  small script that imports the app and exercises it.
- For CLIs and test suites: invoke them directly; they exit on their own.
- If you absolutely must start a server, run it backgrounded, hit it with
  curl/wget, then explicitly kill it before you return.

Report back with: what you built, where it lives, and what the manager or
tester should verify next.
"""

TESTER_PROMPT = """You are the tester on a vibedev team.

You receive a built artifact from the manager and verify it works as specified.
You write tests, run them, and report results.

Critical rule — do NOT leave long-running processes alive. Use the framework's
test client (``app.test_client()``, ``TestClient``), the project's own test
runner, or direct CLI invocation. Never foreground a dev server to hit it
manually.

Report back with: what you tested, what passed, what failed (with exact error
messages and the smallest reproducer), and what should be fixed.
"""

SUBAGENT_ROLES: dict[str, AgentDefinition] = {
    "developer": AgentDefinition(
        description=(
            "Writes code, edits files, installs dependencies, runs commands. "
            "Delegate concrete coding tasks to this agent."
        ),
        prompt=DEVELOPER_PROMPT,
    ),
    "tester": AgentDefinition(
        description=(
            "Writes and runs tests against built artifacts. Reports pass/fail "
            "with specifics. Delegate verification to this agent."
        ),
        prompt=TESTER_PROMPT,
    ),
}

VALID_SUBAGENT_ROLES: frozenset[str] = frozenset(SUBAGENT_ROLES)


_MANAGER_BASE = """You are the manager of a vibedev team.

You receive a high-level project description from the user and your job is to
*coordinate*, not to write code yourself. You plan the work, delegate to your
team via the Task tool, integrate their output, and decide when the
deliverable is done.

Your team:
{team_listing}

How to work:
1. Plan briefly — pick a tech stack and sketch the file layout in your head.
   Do not write a plan document; start delegating.
2. Hand the developer atomic, well-scoped tasks (e.g. "create app.py with a
   single /hello route returning JSON"). Wait for the result, then issue the
   next task.
3. Once the developer reports a build is ready, delegate verification to the
   tester. If the tester reports failures, hand the fixes back to the
   developer with the exact error and a clear ask.
4. When verification is clean, write a short README.md in the workspace
   summarising what was built and how to run it. One paragraph + code block.

You may read files to inspect what the developer produced, but do not write
code yourself unless no developer is on the team.

Final sweep before signaling done: confirm no backgrounded jobs, dev servers,
or file watchers are still running. The user's terminal must return to a
prompt the moment your run is done.
"""

_MANAGER_SOLO_LISTING = (
    "(no subagents configured — you must do the work yourself: act as the "
    "developer and tester in addition to the manager role)"
)


Team = list[tuple[str, str | None]]


def _assign_instance_keys(team: Team) -> list[str]:
    """Map a team list (which may contain duplicates) to unique SDK keys.

    The first occurrence of a role keeps the bare role name; subsequent
    occurrences get a ``-2``, ``-3``, ... suffix. This means the common
    single-instance case looks identical to before, and multi-instance teams
    get readable names like ``developer-2``.
    """
    counts: dict[str, int] = {}
    keys: list[str] = []
    for role, _model in team:
        counts[role] = counts.get(role, 0) + 1
        keys.append(role if counts[role] == 1 else f"{role}-{counts[role]}")
    return keys


def build_manager_prompt(team: Team, default_model: str) -> str:
    """Render the manager's system prompt with the team listing baked in.

    Each team entry is ``(role, model_override_or_None)``; the role is
    expanded into a unique instance key (``developer``, ``developer-2``, ...)
    and its resolved model is shown parenthetically only when the team is
    heterogeneous (i.e. at least one subagent runs a different model from
    the manager's ``default_model``). Homogeneous teams keep the prompt
    clean.
    """
    if not team:
        return _MANAGER_BASE.format(team_listing=_MANAGER_SOLO_LISTING)

    instance_keys = _assign_instance_keys(team)
    resolved = [
        (key, role, model or default_model)
        for key, (role, model) in zip(instance_keys, team)
    ]
    heterogeneous = any(m != default_model for _, _, m in resolved)

    lines = []
    for key, role, model in resolved:
        suffix = f" *(model: `{model}`)*" if heterogeneous else ""
        lines.append(f"- **{key}** — {SUBAGENT_ROLES[role].description}{suffix}")
    listing = "\n".join(lines)
    if heterogeneous:
        listing += (
            f"\n\nYour own model is `{default_model}`. Subagents listed with a "
            f"different model are running on cheaper or stronger tiers — keep "
            f"that in mind when delegating (don't give a deep-reasoning task "
            f"to a Haiku subagent, etc)."
        )

    parallelism_note = ""
    if len(team) > 1:
        parallelism_note = (
            "\n\nWhen the team has more than one member, you may dispatch "
            "multiple Task calls in a single assistant message to run them "
            "in parallel on independent subtasks (e.g. split frontend / "
            "backend, or split unrelated files). Only do this when the "
            "subtasks truly don't depend on each other — serialise when in "
            "doubt."
        )
    return _MANAGER_BASE.format(team_listing=listing) + parallelism_note


def subagents_for(team: Team, default_model: str) -> dict[str, AgentDefinition]:
    """Return the dict to pass to ``ClaudeAgentOptions(agents=...)``.

    Each instance gets a fresh ``AgentDefinition`` copy with its model field
    populated — either the explicit override from the team entry, or the
    main-agent default. Duplicates in ``team`` produce multiple SDK entries
    keyed by the :func:`_assign_instance_keys` scheme.
    """
    instance_keys = _assign_instance_keys(team)
    return {
        key: replace(SUBAGENT_ROLES[role], model=model or default_model)
        for key, (role, model) in zip(instance_keys, team)
    }
