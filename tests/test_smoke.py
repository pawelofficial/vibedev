"""Smoke tests — no network or API calls."""

from __future__ import annotations

import pytest

import vibedev
from vibedev.config import get_config, set_model, set_permissions, set_workspace_root
from vibedev.workspace import ensure_workspace


def test_public_api_exports():
    assert callable(vibedev.prompt)
    assert callable(vibedev.set_permissions)
    assert callable(vibedev.set_model)
    assert callable(vibedev.set_workspace_root)


def test_default_config():
    cfg = get_config()
    assert cfg["permission_mode"] == "bypassPermissions"
    assert cfg["model"].startswith("claude-")
    assert cfg["workspace_root"]


def test_set_permissions_valid():
    original = get_config()["permission_mode"]
    try:
        set_permissions("acceptEdits")
        assert get_config()["permission_mode"] == "acceptEdits"
    finally:
        set_permissions(original)


def test_set_permissions_invalid():
    with pytest.raises(ValueError):
        set_permissions("nope")  # type: ignore[arg-type]


def test_set_model_rejects_empty():
    with pytest.raises(ValueError):
        set_model("")


def test_get_config_returns_copy():
    cfg = get_config()
    cfg["model"] = "tampered"
    assert get_config()["model"] != "tampered"


def test_ensure_workspace_creates_missing_dir(tmp_path):
    target = tmp_path / "new-project"
    ws = ensure_workspace(target)
    assert ws == target.resolve()
    assert ws.is_dir()


def test_ensure_workspace_is_idempotent(tmp_path):
    target = tmp_path / "reused"
    a = ensure_workspace(target)
    b = ensure_workspace(target)
    assert a == b
    assert a.is_dir()


def test_ensure_workspace_creates_parents(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    ws = ensure_workspace(target)
    assert ws.is_dir()


def test_set_workspace_root_roundtrip():
    original = get_config()["workspace_root"]
    try:
        set_workspace_root("/tmp/vibedev-test")
        assert get_config()["workspace_root"] == "/tmp/vibedev-test"
    finally:
        set_workspace_root(original)
