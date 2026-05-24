"""Module-level configuration for vibedev.

Configuration lives on a single private dict and is mutated via the public
``set_*`` setters. This keeps the user-facing surface tiny:

    vibedev.set_permissions("acceptEdits")
    vibedev.set_model("claude-sonnet-4-6")
    vibedev.set_workspace_root("~/projects/vibedev-runs")
"""

from __future__ import annotations

from typing import Literal, TypedDict

PermissionMode = Literal["bypassPermissions", "acceptEdits", "default", "plan"]

_VALID_PERMISSIONS: frozenset[str] = frozenset(
    {"bypassPermissions", "acceptEdits", "default", "plan"}
)


class Config(TypedDict):
    permission_mode: PermissionMode
    model: str
    workspace_root: str


_config: Config = {
    "permission_mode": "bypassPermissions",
    "model": "claude-opus-4-7",
    "workspace_root": "./vibedev-output",
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


def get_config() -> Config:
    return dict(_config)  # type: ignore[return-value]
