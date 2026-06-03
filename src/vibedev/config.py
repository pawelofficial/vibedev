"""Module-level configuration for vibedev.

Configuration lives on a single private dict and is mutated via the public
``set_*`` setters. This keeps the user-facing surface tiny:

    vibedev.set_permissions("acceptEdits")
    vibedev.set_model("claude-sonnet-4-6")
    vibedev.set_workspace_root("~/projects/vibedev-runs")
    vibedev.set_team(["developer", "tester"])
    vibedev.set_common_knowledge(False)
"""

from __future__ import annotations

from typing import Literal, TypedDict

PermissionMode = Literal["bypassPermissions", "acceptEdits", "default", "plan"]

_VALID_PERMISSIONS: frozenset[str] = frozenset(
    {"bypassPermissions", "acceptEdits", "default", "plan"}
)

# Role names accepted by ``set_team``. Kept in sync with
# :data:`vibedev.roles.VALID_SUBAGENT_ROLES`; duplicated here so this module
# stays importable without the Claude Agent SDK installed (useful for tests
# and for the CLI's ``--help``).
_VALID_SUBAGENT_ROLES: frozenset[str] = frozenset(
    {"business_analyst", "developer", "quality_assurance", "tester"}
)


class Config(TypedDict):
    permission_mode: PermissionMode
    model: str
    workspace_root: str
    common_knowledge: bool
    # Each entry is (role, model_override). model_override=None means
    # "use the main-agent model from set_model()".
    team: list[tuple[str, str | None]]


_config: Config = {
    "permission_mode": "bypassPermissions",
    "model": "claude-opus-4-7",
    "workspace_root": "./vibedev-output",
    "common_knowledge": True,
    "team": [("developer", None)],
}


def set_permissions(mode: PermissionMode) -> None:
    if mode not in _VALID_PERMISSIONS:
        raise ValueError(
            f"permission_mode must be one of {sorted(_VALID_PERMISSIONS)}, got {mode!r}"
        )
    _config["permission_mode"] = mode


def set_model(model: str) -> None:
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty string")
    _config["model"] = model


def set_workspace_root(path: str) -> None:
    if not isinstance(path, str) or not path:
        raise ValueError("workspace_root must be a non-empty path string")
    _config["workspace_root"] = path


def set_common_knowledge(enabled: bool) -> None:
    """Enable or disable generated common knowledge in coded team mode.

    When enabled (the default), developer+tester team runs write
    ``.vibedev/common_knowledge.md`` and run the internal knowledge curator.
    When disabled, vibedev skips both steps and role prompts omit the common
    knowledge pointer.
    """
    if not isinstance(enabled, bool):
        raise ValueError("common_knowledge must be a boolean")
    _config["common_knowledge"] = enabled


def set_team(roles: list[str | tuple[str, str]]) -> None:
    """Configure which subagents are available to the manager.

    Pass a list of entries; each entry is either:

      - A bare role name (``"developer"``) — that subagent will use the
        main-agent model set via :func:`set_model`.
      - A ``(role, model)`` tuple (``("developer", "claude-haiku-4-5")``) —
        explicit per-role model override. The model string is passed
        straight to the SDK, so aliases like ``"haiku"`` / ``"sonnet"`` /
        ``"opus"`` / ``"inherit"`` work alongside full model IDs.

    Forms can mix freely: ``["developer", ("tester", "claude-sonnet-4-6")]``.

    Currently the valid roles are ``"business_analyst"``, ``"developer"``,
    ``"quality_assurance"``, and ``"tester"``.
    The ``"manager"`` role is implicit (it is always the main agent when a
    team is configured) and must not be included. The manager's model is
    whatever :func:`set_model` was last called with.

    Duplicates are **meaningful**: ``["developer", "developer", "tester"]``
    gives the manager two distinct developer subagents it can dispatch to in
    parallel. Internally they get unique SDK names (``developer``,
    ``developer-2``, ...); the user only ever deals with role names.

    At least one role is required; the default is a single ``"developer"``
    team. The main agent always runs either the coded developer/tester workflow
    or the fallback manager prompt.
    """
    if not isinstance(roles, list):
        raise ValueError(
            "team must be a list of role names and/or (role, model) tuples"
        )
    if not roles:
        raise ValueError("team must include at least one role")

    normalized: list[tuple[str, str | None]] = []
    for i, entry in enumerate(roles):
        if isinstance(entry, str):
            role, model = entry, None
        elif isinstance(entry, tuple) and len(entry) == 2:
            role, model = entry
            if not isinstance(role, str):
                raise ValueError(
                    f"team entry at index {i}: role must be a string, got {role!r}"
                )
            if model is not None and (not isinstance(model, str) or not model):
                raise ValueError(
                    f"team entry at index {i}: model must be a non-empty "
                    f"string or None, got {model!r}"
                )
        else:
            raise ValueError(
                f"team entry at index {i} must be a role name string or a "
                f"(role, model) 2-tuple, got {entry!r}"
            )
        if role == "manager":
            raise ValueError(
                "'manager' is implicit — do not list it in set_team(...). "
                "Its model is whatever set_model(...) was last called with."
            )
        if role not in _VALID_SUBAGENT_ROLES:
            raise ValueError(
                f"unknown team role {role!r}. "
                f"Valid subagent roles: {sorted(_VALID_SUBAGENT_ROLES)}."
            )
        normalized.append((role, model))
    _config["team"] = normalized


def get_config() -> Config:
    cfg = dict(_config)
    cfg["team"] = list(_config["team"])  # defensive copy of the inner list
    return cfg  # type: ignore[return-value]
