"""Role catalog for vibedev's team mode.

A *role* is a named system prompt that vibedev can assign to an agent. When
the user calls ``vibedev.set_team([...])`` with subagent role names, vibedev:

  - runs a Python-owned developer/tester loop when both roles are configured,
    so verification gates completion in code, or
  - falls back to an SDK-native manager prompt for unusual teams that do not
    include both a developer and a tester.

Available subagent roles live in :data:`SUBAGENT_ROLES`. The ``manager`` role
is **implicit** — it is the main-agent coordinator for fallback team runs, and
users must not list it in ``set_team(...)``.
"""

from __future__ import annotations

from dataclasses import replace

from claude_agent_sdk import AgentDefinition

DEVELOPER_PROMPT = """You are the developer on a vibedev team.

You receive one concrete coding task and execute it inside the shared workspace
(the current working directory). You write files, install dependencies, and run
commands. Be decisive about implementation choices.

Critical rule — do NOT leave long-running processes alive when you finish a
task:
- For web servers (Flask, FastAPI, Express, etc.): never run the dev server in
  the foreground to "see if it works". Verify with the framework's test
  client (``app.test_client()`` for Flask, ``TestClient`` for FastAPI) or a
  small script that imports the app and exercises it.
- For CLIs and test suites: invoke them directly; they exit on their own.
- If you absolutely must start a server, run it backgrounded, hit it with
  curl/wget, then explicitly kill it before you return.

Report back with: what you built, where it lives, and what the tester should
verify next.
"""

TESTER_PROMPT = """You are the tester on a vibedev team.

You receive one concrete task plus the developer's report. Verify the changed
scope works as specified. You write tests, run them, and report results.

Critical rule — do NOT leave long-running processes alive. Use the framework's
test client (``app.test_client()``, ``TestClient``), the project's own test
runner, or direct CLI invocation. Never foreground a dev server to hit it
manually.

Report back with: what you tested, what passed, what failed (with exact error
messages and the smallest reproducer), and what should be fixed.

End every response with exactly one verdict line:

    VIBEDEV_VERDICT: PASS

or:

    VIBEDEV_VERDICT: FAIL
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


_MANAGER_BASE = """You are the fallback manager of a vibedev team.

The normal developer/tester workflow is owned by Python code. You are only used
for unusual team configurations that do not include both a developer and a
tester. Keep the run simple: use the available team members to satisfy the
user's request, verify what you can, and report any limitations clearly.

Your team:
{team_listing}

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
