"""Smoke tests — no network or API calls."""

from __future__ import annotations

import pytest

import vibedev
from vibedev.core import (
    _build_developer_prompt,
    _build_finalizer_prompt,
    _build_tester_prompt,
    _extract_verdict,
    _first_role_model,
    _supports_coded_team_workflow,
)
from vibedev.config import (
    get_config,
    set_model,
    set_permissions,
    set_team,
    set_workspace_root,
)
from vibedev.roles import build_manager_prompt
from vibedev.workspace import ensure_workspace


def test_public_api_exports():
    assert callable(vibedev.prompt)
    assert callable(vibedev.set_permissions)
    assert callable(vibedev.set_model)
    assert callable(vibedev.set_workspace_root)
    assert callable(vibedev.set_team)


def test_default_config():
    cfg = get_config()
    assert cfg["permission_mode"] == "bypassPermissions"
    assert cfg["model"].startswith("claude-")
    assert cfg["workspace_root"]
    assert cfg["team"] == []


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


def test_set_team_roundtrip_bare_strings():
    original = get_config()["team"]
    try:
        set_team(["developer", "tester"])
        assert get_config()["team"] == [("developer", None), ("tester", None)]
    finally:
        set_team(original)


def test_set_team_preserves_duplicates():
    original = get_config()["team"]
    try:
        set_team(["developer", "developer", "tester"])
        assert get_config()["team"] == [
            ("developer", None),
            ("developer", None),
            ("tester", None),
        ]
    finally:
        set_team(original)


def test_set_team_with_model_overrides():
    original = get_config()["team"]
    try:
        set_team(
            [
                ("developer", "claude-haiku-4-5"),
                ("developer", "claude-haiku-4-5"),
                ("tester", "claude-sonnet-4-6"),
            ]
        )
        assert get_config()["team"] == [
            ("developer", "claude-haiku-4-5"),
            ("developer", "claude-haiku-4-5"),
            ("tester", "claude-sonnet-4-6"),
        ]
    finally:
        set_team(original)


def test_set_team_mixed_bare_and_tuple_forms():
    original = get_config()["team"]
    try:
        set_team(["developer", ("developer", "claude-haiku-4-5"), "tester"])
        assert get_config()["team"] == [
            ("developer", None),
            ("developer", "claude-haiku-4-5"),
            ("tester", None),
        ]
    finally:
        set_team(original)


def test_set_team_accepts_model_aliases():
    original = get_config()["team"]
    try:
        set_team([("developer", "haiku"), ("tester", "sonnet")])
        assert get_config()["team"] == [("developer", "haiku"), ("tester", "sonnet")]
    finally:
        set_team(original)


def test_set_team_empty_disables_team_mode():
    original = get_config()["team"]
    try:
        set_team(["developer"])
        set_team([])
        assert get_config()["team"] == []
    finally:
        set_team(original)


def test_set_team_rejects_manager_bare():
    with pytest.raises(ValueError, match="manager"):
        set_team(["manager", "developer"])


def test_set_team_rejects_manager_tuple():
    with pytest.raises(ValueError, match="manager"):
        set_team([("manager", "claude-opus-4-7")])


def test_set_team_rejects_unknown_role():
    with pytest.raises(ValueError, match="unknown"):
        set_team(["designer"])


def test_set_team_rejects_empty_model_string():
    with pytest.raises(ValueError, match="model"):
        set_team([("developer", "")])


def test_set_team_rejects_bad_tuple_arity():
    with pytest.raises(ValueError):
        set_team([("developer", "haiku", "extra")])  # type: ignore[list-item]


def test_set_team_rejects_non_list():
    with pytest.raises(ValueError):
        set_team("developer")  # type: ignore[arg-type]


def test_get_config_team_is_copy():
    original = get_config()["team"]
    try:
        set_team(["developer"])
        cfg = get_config()
        cfg["team"].append(("tester", None))
        assert get_config()["team"] == [("developer", None)]  # mutation didn't leak
    finally:
        set_team(original)


def test_fallback_manager_prompt_requires_verify_fix_retest_loop():
    prompt = build_manager_prompt(
        [("developer", None), ("tester", None)],
        default_model="claude-opus-4-7",
    )

    assert "Do not mark the plan item `[x]`\n   yet." in prompt
    assert "Only mark the item `[x]` after the tester reports" in prompt
    assert "After every developer fix,\n   send the changed artifact back to the tester." in prompt
    assert "Do not\n   signal completion with known failing tests." in prompt
    assert "Wait for the result, mark the item" not in prompt


def test_coded_team_workflow_requires_developer_and_tester():
    assert _supports_coded_team_workflow([("developer", None), ("tester", None)])
    assert _supports_coded_team_workflow(
        [("developer", "haiku"), ("developer", "haiku"), ("tester", "sonnet")]
    )
    assert not _supports_coded_team_workflow([])
    assert not _supports_coded_team_workflow([("developer", None)])
    assert not _supports_coded_team_workflow([("tester", None)])


def test_first_role_model_uses_first_matching_role_and_default():
    team = [("developer", None), ("developer", "haiku"), ("tester", "sonnet")]

    assert _first_role_model(team, "developer", "opus") == "opus"
    assert _first_role_model(team, "tester", "opus") == "sonnet"
    assert _first_role_model(team, "designer", "opus") is None


def test_extract_verdict_uses_last_explicit_verdict():
    assert _extract_verdict("looks good\nVIBEDEV_VERDICT: PASS") is True
    assert _extract_verdict("broken\nVIBEDEV_VERDICT: FAIL") is False
    assert _extract_verdict("VIBEDEV_VERDICT: FAIL\nfixed\nVIBEDEV_VERDICT: PASS") is True
    assert _extract_verdict("tests passed") is None


def test_tester_prompt_requires_machine_readable_verdict():
    prompt = _build_tester_prompt(
        "add /goodbye",
        attempt=1,
        developer_report="changed app.py",
    )

    assert "End your response with exactly one verdict line:" in prompt
    assert "VIBEDEV_VERDICT: PASS" in prompt
    assert "VIBEDEV_VERDICT: FAIL" in prompt


def test_coded_workflow_prompts_keep_plan_checkoff_in_finalizer():
    developer_prompt = _build_developer_prompt(
        "add /goodbye",
        attempt=1,
        tester_report="",
    )
    finalizer_prompt = _build_finalizer_prompt(
        "add /goodbye",
        developer_report="changed app.py",
        tester_report="VIBEDEV_VERDICT: PASS",
        passed=True,
    )

    assert "Do not mark the changed scope complete yet" in developer_prompt
    assert "status: passed" in finalizer_prompt
    assert "Update `.vibedev/plan.md` and `README.md`" in finalizer_prompt
