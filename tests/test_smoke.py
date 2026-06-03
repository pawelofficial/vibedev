"""Smoke tests — no network or API calls."""

from __future__ import annotations

import pytest

import vibedev
import vibedev.core as core
from vibedev.core import (
    _apply_analyst_review,
    _build_business_analyst_prompt,
    _build_common_knowledge,
    _build_developer_prompt,
    _build_knowledge_curator_prompt,
    _build_readme_update_prompt,
    _build_tester_prompt,
    _conversation_log_path,
    _ConversationLogger,
    _current_request_task_index,
    _extract_verdict,
    _extract_proposed_tasks,
    _first_role_model,
    _load_or_create_team_plan,
    _mark_plan_task_done,
    _next_pending_task_index,
    _parse_team_plan,
    _record_plan_blocker,
    _restore_plan_if_changed,
    _summarize_goal,
    _summarize_history_entry,
    _summarize_task,
    _supports_coded_team_workflow,
    _write_common_knowledge,
)
from vibedev.config import (
    get_config,
    set_common_knowledge,
    set_model,
    set_permissions,
    set_team,
    set_workspace_root,
)
from vibedev.roles import build_manager_prompt
from vibedev.workspace import ensure_workspace


class _DummyConversationLogger:
    def __init__(self) -> None:
        self.turns: list[tuple[str, str, str]] = []

    def log_turn(self, label: str, prompt: str, response: str) -> None:
        self.turns.append((label, prompt, response))


def test_public_api_exports():
    assert callable(vibedev.prompt)
    assert callable(vibedev.set_permissions)
    assert callable(vibedev.set_model)
    assert callable(vibedev.set_workspace_root)
    assert callable(vibedev.set_team)
    assert callable(vibedev.set_common_knowledge)


def test_default_config():
    cfg = get_config()
    assert cfg["permission_mode"] == "bypassPermissions"
    assert cfg["model"].startswith("claude-")
    assert cfg["workspace_root"]
    assert cfg["common_knowledge"] is True
    assert cfg["team"] == [("developer", None)]


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


def test_conversation_log_path_sits_next_to_transcript(tmp_path):
    transcript_path = tmp_path / "20260524T123456Z.log"

    assert _conversation_log_path(transcript_path) == (
        tmp_path / "20260524T123456Z.conversation.md"
    )


def test_conversation_logger_writes_prompt_response_without_tool_details(tmp_path):
    path = tmp_path / "run.conversation.md"
    cfg = {
        "permission_mode": "bypassPermissions",
        "model": "claude-opus-4-7",
        "workspace_root": str(tmp_path),
        "common_knowledge": True,
        "team": [("developer", None), ("tester", "sonnet")],
    }

    with _ConversationLogger(path) as logger:
        logger.write_header("build app", tmp_path, cfg, tmp_path / "run.log")
        logger.log_turn(
            "Developer Attempt 1",
            "Task:\nBuild app",
            "Changed `app.py`.",
        )
        logger.write_footer()

    content = path.read_text(encoding="utf-8")

    assert "# vibedev Conversation Log" in content
    assert "## User Prompt" in content
    assert "## Developer Attempt 1" in content
    assert "### Prompt" in content
    assert "Task:\nBuild app" in content
    assert "### Response" in content
    assert "Changed `app.py`." in content
    assert "tool_result" not in content


def test_set_workspace_root_roundtrip():
    original = get_config()["workspace_root"]
    try:
        set_workspace_root("/tmp/vibedev-test")
        assert get_config()["workspace_root"] == "/tmp/vibedev-test"
    finally:
        set_workspace_root(original)


def test_set_common_knowledge_roundtrip():
    original = get_config()["common_knowledge"]
    try:
        set_common_knowledge(False)
        assert get_config()["common_knowledge"] is False
        set_common_knowledge(True)
        assert get_config()["common_knowledge"] is True
    finally:
        set_common_knowledge(original)


def test_set_common_knowledge_rejects_non_bool():
    with pytest.raises(ValueError):
        set_common_knowledge("false")  # type: ignore[arg-type]


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
                ("business_analyst", "claude-opus-4-6"),
                ("developer", "claude-haiku-4-5"),
                ("developer", "claude-haiku-4-5"),
                ("tester", "claude-sonnet-4-6"),
            ]
        )
        assert get_config()["team"] == [
            ("business_analyst", "claude-opus-4-6"),
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


def test_set_team_accepts_quality_assurance_role():
    original = get_config()["team"]
    try:
        set_team(["quality_assurance"])
        assert get_config()["team"] == [("quality_assurance", None)]
    finally:
        set_team(original)


def test_set_team_rejects_empty_team():
    with pytest.raises(ValueError, match="at least one role"):
        set_team([])


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


def test_fallback_manager_prompt_does_not_own_normal_workflow():
    prompt = build_manager_prompt(
        [("developer", None), ("tester", None)],
        default_model="claude-opus-4-7",
    )

    assert "fallback manager" in prompt
    assert "Read the plan first" not in prompt
    assert "Integrate the current prompt" not in prompt
    assert "Delegate one task at a time" not in prompt
    assert "Verify before checkoff" not in prompt


def test_coded_team_workflow_requires_developer_and_tester():
    assert _supports_coded_team_workflow([("developer", None), ("tester", None)])
    assert _supports_coded_team_workflow(
        [
            ("business_analyst", "opus"),
            ("developer", "haiku"),
            ("developer", "haiku"),
            ("tester", "sonnet"),
        ]
    )
    assert not _supports_coded_team_workflow([])
    assert not _supports_coded_team_workflow([("business_analyst", None)])
    assert not _supports_coded_team_workflow([("developer", None)])
    assert not _supports_coded_team_workflow([("tester", None)])


def test_first_role_model_uses_first_matching_role_and_default():
    team = [
        ("business_analyst", "opus"),
        ("developer", None),
        ("developer", "haiku"),
        ("tester", "sonnet"),
    ]

    assert _first_role_model(team, "business_analyst", "opus-4-7") == "opus"
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


def test_coded_workflow_prompts_leave_plan_to_python():
    common_knowledge = "# Common Knowledge\n- Tests: `tests/test_app.py`"
    developer_prompt = _build_developer_prompt(
        "add /goodbye",
        attempt=1,
        tester_report="",
        analyst_brief="## Acceptance Criteria\n- The /goodbye route returns JSON.",
        common_knowledge=common_knowledge,
    )
    tester_prompt = _build_tester_prompt(
        "add /goodbye",
        attempt=1,
        developer_report="changed app.py",
        analyst_brief="## Acceptance Criteria\n- The /goodbye route returns JSON.",
        common_knowledge=common_knowledge,
    )
    readme_prompt = _build_readme_update_prompt(
        "add /goodbye",
        developer_report="changed app.py",
        tester_report="VIBEDEV_VERDICT: PASS",
        common_knowledge=common_knowledge,
    )

    assert "Python owns the plan file" in developer_prompt
    assert "Shared project context:" in developer_prompt
    assert "`.vibedev/common_knowledge.md`" in developer_prompt
    assert "`tests/test_app.py`" not in developer_prompt
    assert "# Common Knowledge" not in developer_prompt
    assert "Shared project context:" in tester_prompt
    assert "Business analyst brief and acceptance criteria" in developer_prompt
    assert "The /goodbye route returns JSON." in developer_prompt
    assert "The /goodbye route returns JSON." in tester_prompt
    assert "Shared project context:" in readme_prompt
    assert "Update `README.md`" in readme_prompt
    assert "Do not edit\n`.vibedev/plan.md`" in readme_prompt


def test_business_analyst_prompt_receives_current_plan():
    plan = _parse_team_plan(
        """# vibedev plan

## Goal
Build an app.

## Tasks
- [ ] Build the first feature

## History
- 2026-05-24 - Request: build an app
""",
        fallback_goal="fallback",
    )

    prompt = _build_business_analyst_prompt(
        "build an app",
        plan,
        common_knowledge="# Common Knowledge\nShared docs live in README.md",
    )

    assert "Shared project context:" in prompt
    assert "`.vibedev/common_knowledge.md`" in prompt
    assert "Shared docs live in README.md" not in prompt
    assert "Current Python-owned plan:" in prompt
    assert "- [ ] Build the first feature" in prompt
    assert "## Proposed Tasks" in prompt


def test_knowledge_curator_prompt_receives_plan_and_draft_context():
    plan = _parse_team_plan(
        """# vibedev plan

## Goal
Build an app.

## Tasks
- [ ] Build the first feature

## History
- 2026-05-24 - Request: build an app
""",
        fallback_goal="fallback",
    )

    prompt = _build_knowledge_curator_prompt(
        "build an app with many detailed requirements",
        plan,
        common_knowledge="# Common Knowledge\n## Known Tests\n- `tests/test_app.py`",
    )

    assert "Current Python-owned plan:" in prompt
    assert "- [ ] Build the first feature" in prompt
    assert "Current generated common knowledge draft:" in prompt
    assert "`tests/test_app.py`" in prompt
    assert "summarize only the code structure" in prompt
    assert "Avoid\nproduct requirements" in prompt
    assert "Do not edit" in prompt
    assert "Python will write your report" in prompt


def test_extract_proposed_tasks_from_analyst_brief():
    tasks = _extract_proposed_tasks(
        """## Missing Requirements
- Something else

## Proposed Tasks
- [ ] Add lineage graph search
- Add column detail drawer
* Add export button

## Acceptance Criteria
- Search works
"""
    )

    assert tasks == [
        "Add lineage graph search",
        "Add column detail drawer",
        "Add export button",
    ]


def test_apply_analyst_review_appends_missing_tasks(tmp_path):
    plan = _load_or_create_team_plan(tmp_path, "build lineage app")
    added_indices = _apply_analyst_review(
        tmp_path,
        plan,
        """## Missing Requirements
- Need export

## Proposed Tasks
- [ ] Add lineage graph search
- [ ] build lineage app

## Acceptance Criteria
- Search by model and column

## Risks
- Parser may be too shallow
""",
    )

    plan_text = (tmp_path / ".vibedev" / "plan.md").read_text(encoding="utf-8")
    updated_plan = _parse_team_plan(plan_text, fallback_goal="")
    assert "- [ ] build lineage app" in plan_text
    assert "- [ ] Add lineage graph search" in plan_text
    assert [task.text for task in updated_plan.tasks].count("build lineage app") == 1
    assert "Analyst review:" in plan_text
    assert added_indices == [1]


def test_current_request_task_index_skips_stale_pending_backlog():
    plan = _parse_team_plan(
        """# vibedev plan

## Goal
Build an app.

## Tasks
- [x] Add drag behavior
- [ ] Old analyst subtask for drag
- [ ] Modularize backend

## History
- 2026-05-24 - Completed: Add drag behavior
""",
        fallback_goal="fallback",
    )

    assert _current_request_task_index(plan, "Implement this refactor: Modularize backend") == 2


def test_build_common_knowledge_discovers_docs_tests_and_files(tmp_path):
    (tmp_path / "README.md").write_text("# Demo app\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    plan = _load_or_create_team_plan(tmp_path, "build demo app")

    common_knowledge = _build_common_knowledge(tmp_path, "build demo app", plan)

    assert "# Common Knowledge" in common_knowledge
    assert "build demo app" in common_knowledge
    assert "`README.md`" in common_knowledge
    assert "`tests/test_app.py`" in common_knowledge
    assert "`app.py`" in common_knowledge
    assert "` .vibedev/plan.md`" not in common_knowledge


def test_write_common_knowledge_creates_workspace_file(tmp_path):
    plan = _load_or_create_team_plan(tmp_path, "build demo app")
    content = _write_common_knowledge(tmp_path, "build demo app", plan)
    path = tmp_path / ".vibedev" / "common_knowledge.md"

    assert path.read_text(encoding="utf-8") == content
    assert "## Team Workflow" in content
    assert "Python owns plan parsing" in content


def test_write_common_knowledge_includes_curated_context(tmp_path):
    plan = _load_or_create_team_plan(tmp_path, "build demo app")
    content = _write_common_knowledge(
        tmp_path,
        "build demo app",
        plan,
        curated_context="## Code Structure\n- `app.py` defines the Flask routes.",
    )

    assert "## Curated Project Context" in content
    assert "## Code Structure" in content
    assert "`app.py` defines the Flask routes." in content


def test_coded_team_workflow_runs_knowledge_curator_first(tmp_path, monkeypatch):
    calls: list[str] = []

    async def fake_run_query(prompt, options, logger, quiet):  # noqa: ANN001, ARG001
        calls.append(prompt)
        if "Current generated common knowledge draft:" in prompt:
            return "## Code Structure\n- Curated workspace structure."
        if "Current Python-owned plan:" in prompt:
            return """## Missing Requirements

## Proposed Tasks

## Acceptance Criteria
- Works.

## Risks
"""
        if "End your response with exactly one verdict line:" in prompt:
            return "verified\nVIBEDEV_VERDICT: PASS"
        return "developer or README report"

    class Logger:
        def __init__(self) -> None:
            self.stages: list[str] = []

        def write_stage(self, label: str) -> None:
            self.stages.append(label)

    monkeypatch.setattr(core, "_run_query", fake_run_query)
    cfg = {
        "permission_mode": "bypassPermissions",
        "model": "claude-opus-4-7",
        "workspace_root": str(tmp_path),
        "common_knowledge": True,
        "team": [("business_analyst", None), ("developer", None), ("tester", None)],
    }

    core.anyio.run(
        core._run_coded_team_workflow,
        "build demo app",
        tmp_path,
        cfg,
        True,
        Logger(),
        _DummyConversationLogger(),
    )

    common_knowledge = (tmp_path / ".vibedev" / "common_knowledge.md").read_text(
        encoding="utf-8"
    )

    assert calls[0].startswith("User request:")
    assert "Current generated common knowledge draft:" in calls[0]
    assert "Curated workspace structure." in common_knowledge


def test_coded_team_workflow_can_skip_common_knowledge(tmp_path, monkeypatch):
    calls: list[str] = []

    async def fake_run_query(prompt, options, logger, quiet):  # noqa: ANN001, ARG001
        calls.append(prompt)
        if "Current generated common knowledge draft:" in prompt:
            return "## Code Structure\n- Should not run."
        if "Current Python-owned plan:" in prompt:
            return """## Missing Requirements

## Proposed Tasks

## Acceptance Criteria
- Works.

## Risks
"""
        if "End your response with exactly one verdict line:" in prompt:
            return "verified\nVIBEDEV_VERDICT: PASS"
        return "developer or README report"

    class Logger:
        def write_stage(self, label: str) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(core, "_run_query", fake_run_query)
    cfg = {
        "permission_mode": "bypassPermissions",
        "model": "claude-opus-4-7",
        "workspace_root": str(tmp_path),
        "common_knowledge": False,
        "team": [("business_analyst", None), ("developer", None), ("tester", None)],
    }

    core.anyio.run(
        core._run_coded_team_workflow,
        "build demo app",
        tmp_path,
        cfg,
        True,
        Logger(),
        _DummyConversationLogger(),
    )

    assert not (tmp_path / ".vibedev" / "common_knowledge.md").exists()
    assert all("Current generated common knowledge draft:" not in call for call in calls)
    assert all("Shared project context:" not in call for call in calls)


def test_coded_team_workflow_marks_analyst_subtasks_done_after_parent_pass(
    tmp_path,
    monkeypatch,
):
    async def fake_run_query(prompt, options, logger, quiet):  # noqa: ANN001, ARG001
        if "Current generated common knowledge draft:" in prompt:
            return "## Code Structure\n- Curated workspace structure."
        if "Current Python-owned plan:" in prompt:
            return """## Missing Requirements

## Proposed Tasks
- [ ] Add route module
- [ ] Add schema service module

## Acceptance Criteria
- Backend still serves the same API.

## Risks
"""
        if "End your response with exactly one verdict line:" in prompt:
            return "verified\nVIBEDEV_VERDICT: PASS"
        return "developer or README report"

    class Logger:
        def write_stage(self, label: str) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(core, "_run_query", fake_run_query)
    cfg = {
        "permission_mode": "bypassPermissions",
        "model": "claude-opus-4-7",
        "workspace_root": str(tmp_path),
        "common_knowledge": True,
        "team": [("business_analyst", None), ("developer", None), ("tester", None)],
    }

    core.anyio.run(
        core._run_coded_team_workflow,
        "Implement this refactor: Modularize backend",
        tmp_path,
        cfg,
        True,
        Logger(),
        _DummyConversationLogger(),
    )

    plan_text = (tmp_path / ".vibedev" / "plan.md").read_text(encoding="utf-8")

    assert "- [x] Modularize backend" in plan_text
    assert "- [x] Add route module" in plan_text
    assert "- [x] Add schema service module" in plan_text


def test_coded_team_workflow_prioritizes_current_request_over_old_pending(
    tmp_path,
    monkeypatch,
):
    (tmp_path / ".vibedev").mkdir()
    (tmp_path / ".vibedev" / "plan.md").write_text(
        """# vibedev plan

## Goal
Build an app.

## Tasks
- [x] Add drag behavior
- [ ] Old analyst subtask for drag

## History
- 2026-05-24 - Completed: Add drag behavior
""",
        encoding="utf-8",
    )
    developer_prompts: list[str] = []

    async def fake_run_query(prompt, options, logger, quiet):  # noqa: ANN001, ARG001
        if "Current generated common knowledge draft:" in prompt:
            return "## Code Structure\n- Curated workspace structure."
        if "Current Python-owned plan:" in prompt:
            return """## Missing Requirements

## Proposed Tasks

## Acceptance Criteria
- Backend remains equivalent.

## Risks
"""
        if "End your response with exactly one verdict line:" in prompt:
            return "verified\nVIBEDEV_VERDICT: PASS"
        if prompt.startswith("Task:"):
            developer_prompts.append(prompt)
        return "developer or README report"

    class Logger:
        def write_stage(self, label: str) -> None:  # noqa: ARG002
            return None

    monkeypatch.setattr(core, "_run_query", fake_run_query)
    cfg = {
        "permission_mode": "bypassPermissions",
        "model": "claude-opus-4-7",
        "workspace_root": str(tmp_path),
        "common_knowledge": True,
        "team": [("business_analyst", None), ("developer", None), ("tester", None)],
    }

    core.anyio.run(
        core._run_coded_team_workflow,
        "Implement this refactor: Modularize backend",
        tmp_path,
        cfg,
        True,
        Logger(),
        _DummyConversationLogger(),
    )

    assert developer_prompts
    assert "Modularize backend" in developer_prompts[0]
    assert "Old analyst subtask for drag" not in developer_prompts[0]


def test_prompt_summaries_do_not_copy_full_prompt():
    startup_prompt = """
Build a column-lineage web app for the SQL models in schema.txt.

Core requirements:
- Show SQL tables/views as model nodes.
- Show column-to-column lineage edges.

Implementation guidance:
- Include tests for lineage extraction.
"""
    feature_prompt = """
Continue the existing lineage app in this workspace. Do not rebuild it from scratch.

Implement this feature:
Users should be able to drag and reposition lineage graph nodes.

Requirements:
- Preserve existing parsing behavior.
- Keep edges connected.
"""

    assert _summarize_goal(startup_prompt) == (
        "Build a column-lineage web app for the SQL models in schema.txt."
    )
    assert _summarize_task(feature_prompt) == (
        "Users should be able to drag and reposition lineage graph nodes."
    )
    assert _summarize_task(
        "Continue the existing app. Implement this UI feature: Users should drag nodes. Requirements: keep edges connected."
    ) == "Users should drag nodes."
    assert "Core requirements" not in _summarize_goal(startup_prompt)
    assert "Requirements" not in _summarize_task(feature_prompt)


def test_load_or_create_team_plan_compacts_verbose_prompts(tmp_path):
    verbose_prompt = """
Continue the existing lineage app in this workspace. Do not rebuild it from scratch.

Implement this feature:
Users should be able to drag and reposition lineage graph nodes.

Requirements:
- Preserve existing parsing behavior.
- Keep edges connected.
"""

    plan = _load_or_create_team_plan(tmp_path, verbose_prompt)
    plan_text = (tmp_path / ".vibedev" / "plan.md").read_text(encoding="utf-8")

    assert plan.goal == "Users should be able to drag and reposition lineage graph nodes."
    assert [task.text for task in plan.tasks] == [
        "Users should be able to drag and reposition lineage graph nodes."
    ]
    assert "Do not rebuild it from scratch" not in plan_text
    assert "Requirements:" not in plan_text
    assert "Keep edges connected" not in plan_text


def test_common_knowledge_uses_compact_goal_task_and_history(tmp_path):
    verbose_prompt = """
Build a column-lineage web app for the SQL models in schema.txt.

Core requirements:
- Show SQL tables/views as model nodes.
- Show column-to-column lineage edges.
"""
    plan = _load_or_create_team_plan(tmp_path, verbose_prompt)
    common_knowledge = _build_common_knowledge(tmp_path, verbose_prompt, plan)

    assert "Build a column-lineage web app for the SQL models in schema.txt." in common_knowledge
    assert "Core requirements" not in common_knowledge
    assert "Show SQL tables/views as model nodes" not in common_knowledge
    assert "`.vibedev/plan.md`" in common_knowledge


def test_common_knowledge_discovery_ignores_vibedev_internal_files(tmp_path):
    internal = tmp_path / ".vibedev"
    internal.mkdir()
    (internal / "plan.md").write_text("# plan\n", encoding="utf-8")
    (internal / "common_knowledge.md").write_text("# knowledge\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    plan = _load_or_create_team_plan(tmp_path, "build demo app")

    common_knowledge = _build_common_knowledge(tmp_path, "build demo app", plan)
    known_docs = common_knowledge.split("## Known Documentation", maxsplit=1)[1]

    assert "- `README.md`" in known_docs
    assert "- `.vibedev/plan.md`" not in known_docs
    assert "- `.vibedev/common_knowledge.md`" not in known_docs


def test_summarize_history_entry_preserves_event_prefix():
    entry = (
        "2026-05-24 - Request: Continue the existing lineage app in this workspace. "
        "Do not rebuild it from scratch.\n\nImplement this feature:\n"
        "Users should drag nodes.\n\nRequirements:\n- Keep edges connected."
    )

    assert _summarize_history_entry(entry) == (
        "2026-05-24 - Request: Users should drag nodes."
    )


def test_parse_team_plan_extracts_goal_tasks_and_history():
    plan = _parse_team_plan(
        """# vibedev plan

## Goal
Build an app.

## Tasks
- [x] Existing done task
- [ ] Existing pending task

## History
- 2026-05-24 - Request: build an app
""",
        fallback_goal="fallback",
    )

    assert plan.goal == "Build an app."
    assert [(task.done, task.text) for task in plan.tasks] == [
        (True, "Existing done task"),
        (False, "Existing pending task"),
    ]
    assert plan.history == ["2026-05-24 - Request: build an app"]


def test_load_or_create_team_plan_appends_current_request(tmp_path):
    plan = _load_or_create_team_plan(tmp_path, "add /goodbye")
    plan_path = tmp_path / ".vibedev" / "plan.md"

    assert plan.goal == "add /goodbye"
    assert [(task.done, task.text) for task in plan.tasks] == [(False, "add /goodbye")]
    assert _next_pending_task_index(plan) == 0
    assert "- [ ] add /goodbye" in plan_path.read_text(encoding="utf-8")

    loaded_again = _load_or_create_team_plan(tmp_path, "add /goodbye")
    assert [task.text for task in loaded_again.tasks] == ["add /goodbye"]


def test_mark_done_and_record_blocker_update_plan_file(tmp_path):
    plan = _load_or_create_team_plan(tmp_path, "add /goodbye")
    _mark_plan_task_done(tmp_path, plan, 0)

    plan_text = (tmp_path / ".vibedev" / "plan.md").read_text(encoding="utf-8")
    assert "- [x] add /goodbye" in plan_text
    assert "Completed: add /goodbye" in plan_text

    plan = _load_or_create_team_plan(tmp_path, "add /hello")
    pending = _next_pending_task_index(plan)
    assert pending == 1
    _record_plan_blocker(tmp_path, plan, pending, "pytest failed because route is missing")

    plan_text = (tmp_path / ".vibedev" / "plan.md").read_text(encoding="utf-8")
    assert "- [ ] add /hello" in plan_text
    assert "Blocked: add /hello" in plan_text
    assert "pytest failed because route is missing" in plan_text


def test_restore_plan_if_readme_updater_touches_it(tmp_path):
    plan = _load_or_create_team_plan(tmp_path, "add /goodbye")
    _mark_plan_task_done(tmp_path, plan, 0)
    plan_path = tmp_path / ".vibedev" / "plan.md"
    expected = plan_path.read_text(encoding="utf-8")

    plan_path.write_text("agent changed this unexpectedly\n", encoding="utf-8")
    _restore_plan_if_changed(tmp_path, expected)

    assert plan_path.read_text(encoding="utf-8") == expected
