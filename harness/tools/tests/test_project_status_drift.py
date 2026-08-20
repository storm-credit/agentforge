"""Tests for project_status.py drift/wiring checks: the `.claude/worktrees/`
stale-copy check and the specialist-role wiring dedupe.

harness/tools/ has no package __init__.py and is not installed anywhere, so
this test loads project_status.py directly by file path (importlib) rather
than assuming it is importable as a module. All fixtures are built under
pytest's `tmp_path` -- this test never creates a real git worktree and never
touches this repo's own `.claude/worktrees/`.

Run from the repo root with the venv interpreter:
    apps/api/.venv/Scripts/python.exe -m pytest harness/tools/tests -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "project_status.py"


def _load_project_status():
    spec = importlib.util.spec_from_file_location("project_status_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


project_status = _load_project_status()


def test_registered_and_populated_is_pass(tmp_path: Path) -> None:
    """A directory that IS a registered git worktree is fine even with files
    in it -- an agent may legitimately be working there right now. It must
    still be named in the PASS message (not just counted) so a human running
    the check can see it and judge -- registration alone doesn't prove the
    worktree isn't an abandoned, still-registered leftover (the gap this
    check cannot close: abandonment isn't detectable from the script without
    false-positiving every live agent run)."""
    worktrees_dir = tmp_path / "worktrees"
    active = worktrees_dir / "wf_active"
    active.mkdir(parents=True)
    (active / "some_file.py").write_text("content", encoding="utf-8")

    ok, message = project_status._check_stale_worktrees(
        worktrees_dir=worktrees_dir,
        registered_paths={active.resolve()},
    )

    assert ok is True
    assert "1 registered worktree" in message
    assert "0 stale-populated" in message
    assert "wf_active" in message
    assert "actively working" in message


def test_registered_and_locked_is_still_pass_but_reports_lock(tmp_path: Path) -> None:
    """A registered worktree that is also LOCKED is still reported PASS --
    lock state alone is not proof of abandonment, and this check must never
    false-positive on a worktree an agent could legitimately still be using.
    But this project's own incident record shows a failed worktree dispatch
    leaves a locked registration behind, so the lock state (and reason, if
    git recorded one) must be surfaced in the message for a human to judge."""
    worktrees_dir = tmp_path / "worktrees"
    locked = worktrees_dir / "wf_locked"
    locked.mkdir(parents=True)
    (locked / "some_file.py").write_text("content", encoding="utf-8")

    ok, message = project_status._check_stale_worktrees(
        worktrees_dir=worktrees_dir,
        registered_paths={locked.resolve()},
        lock_reasons={locked.resolve(): "dispatch failed: agent process exited"},
    )

    assert ok is True
    assert "wf_locked" in message
    assert "LOCKED" in message
    assert "dispatch failed: agent process exited" in message


def test_registered_and_locked_with_no_reason_still_reports_locked(tmp_path: Path) -> None:
    """`git worktree lock` without `--reason` still yields a `locked` line
    with no reason text -- the message must say LOCKED without inventing a
    reason that was never given."""
    worktrees_dir = tmp_path / "worktrees"
    locked = worktrees_dir / "wf_locked_no_reason"
    locked.mkdir(parents=True)

    ok, message = project_status._check_stale_worktrees(
        worktrees_dir=worktrees_dir,
        registered_paths={locked.resolve()},
        lock_reasons={locked.resolve(): ""},
    )

    assert ok is True
    assert "wf_locked_no_reason" in message
    assert "LOCKED" in message


def test_unregistered_and_populated_is_fail_and_names_dir(tmp_path: Path) -> None:
    """A directory that is NOT a registered worktree but contains files is a
    real hazard: name-based `find` returns it before the live file."""
    worktrees_dir = tmp_path / "worktrees"
    stale = worktrees_dir / "wf_abandoned"
    stale.mkdir(parents=True)
    (stale / "page.tsx").write_text("stale copy", encoding="utf-8")

    ok, message = project_status._check_stale_worktrees(
        worktrees_dir=worktrees_dir,
        registered_paths=set(),
    )

    assert ok is False
    assert "wf_abandoned" in message
    assert "shadow" in message.lower()


def test_unregistered_and_empty_is_pass_but_mentioned(tmp_path: Path) -> None:
    """An unregistered but empty directory is harmless -- pass -- but should
    still be named in the message so it stays visible."""
    worktrees_dir = tmp_path / "worktrees"
    empty_dir = worktrees_dir / "wf_empty"
    empty_dir.mkdir(parents=True)

    ok, message = project_status._check_stale_worktrees(
        worktrees_dir=worktrees_dir,
        registered_paths=set(),
    )

    assert ok is True
    assert "wf_empty" in message


def test_no_worktrees_directory_at_all_is_pass(tmp_path: Path) -> None:
    """No `.claude/worktrees/` directory at all (fresh clone / CI checkout)
    is a pass -- there is nothing to check."""
    worktrees_dir = tmp_path / "worktrees_does_not_exist"

    ok, message = project_status._check_stale_worktrees(
        worktrees_dir=worktrees_dir,
        registered_paths=set(),
    )

    assert ok is True
    assert "nothing to check" in message


def test_real_repo_worktrees_dir_currently_passes() -> None:
    """Guard against silently changing behaviour against this repo's actual
    .claude/worktrees/ state: as of this slice it holds exactly one
    unregistered, empty directory (wf_f67d5ada-ed4-3), which must PASS while
    still being mentioned for visibility. This uses the real default path
    and real `git worktree list --porcelain` -- it is allowed to be
    environment-sensitive; if the fixture directory is ever populated with a
    real stale copy, this test should start failing loudly rather than
    silently, which is the point of the check.
    """
    ok, message = project_status._check_stale_worktrees()

    assert ok is True
    assert "wf_f67d5ada-ed4-3" in message or "no" in message.lower()


def _valid_agent_md(name: str, agent_role_id: str) -> str:
    """A minimal but STRUCTURALLY VALID .claude/agents/*.md file: parseable
    frontmatter with the required name/tools fields, plus a body line
    carrying the agent_role_id reference that _collect_specialist_wiring's
    AGENT_ROLE_ID_RE matches against (mirroring the real files' "Authoritative
    contract: ... agent_role_id: <id>" line)."""
    return (
        "---\n"
        f"name: {name}\n"
        "description: test fixture agent\n"
        "tools: Read, Grep, Bash\n"
        "model: inherit\n"
        "---\n"
        "\n"
        f"Authoritative contract: `agent_role_id: {agent_role_id}`.\n"
    )


def test_specialist_wiring_dedupes_one_role_carried_by_two_files(tmp_path: Path) -> None:
    """A single declared role id that is carried by TWO .claude/agents/*.md
    files (e.g. security-trust-architect <- security-reviewer.md +
    security-implementer.md) must count as ONE wired role, not two -- and
    both filenames must show up in the mapping. Regression test for a bug
    where wired_ids was a list (so len() double-counted) and wired_files was
    a dict[str, str] (so the second file silently overwrote the first)."""
    yaml_path = tmp_path / "specialists.yaml"
    yaml_path.write_text(
        "agents:\n"
        "  - agent_role_id: shared-role\n"
        "  - agent_role_id: lonely-role\n",
        encoding="utf-8",
    )
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "reviewer.md").write_text(
        _valid_agent_md("reviewer", "shared-role"), encoding="utf-8"
    )
    (agents_dir / "implementer.md").write_text(
        _valid_agent_md("implementer", "shared-role"), encoding="utf-8"
    )

    result = project_status._collect_specialist_wiring(
        specialists_yaml=yaml_path,
        claude_agents_dir=agents_dir,
    )

    assert result["ok"] is True
    assert result["declared_count"] == 2
    assert result["wired_ids"] == ["shared-role"]
    assert len(result["wired_ids"]) == 1
    assert sorted(result["wired_files"]["shared-role"]) == ["implementer.md", "reviewer.md"]
    assert "lonely-role" not in result["wired_ids"]


def test_specialist_wiring_counts_distinct_roles_separately(tmp_path: Path) -> None:
    """Two DIFFERENT declared role ids, each carried by its own file, must
    both count as wired -- the dedupe fix must not collapse distinct roles
    together."""
    yaml_path = tmp_path / "specialists.yaml"
    yaml_path.write_text(
        "agents:\n"
        "  - agent_role_id: role-a\n"
        "  - agent_role_id: role-b\n",
        encoding="utf-8",
    )
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "a.md").write_text(_valid_agent_md("a", "role-a"), encoding="utf-8")
    (agents_dir / "b.md").write_text(_valid_agent_md("b", "role-b"), encoding="utf-8")

    result = project_status._collect_specialist_wiring(
        specialists_yaml=yaml_path,
        claude_agents_dir=agents_dir,
    )

    assert result["ok"] is True
    assert result["declared_count"] == 2
    assert sorted(result["wired_ids"]) == ["role-a", "role-b"]
    assert result["wired_files"]["role-a"] == ["a.md"]
    assert result["wired_files"]["role-b"] == ["b.md"]


def test_specialist_wiring_skips_role_whose_only_file_has_invalid_frontmatter(
    tmp_path: Path,
) -> None:
    """A role whose ONLY carrying file has invalid frontmatter (e.g. an
    unquoted ": " sequence, mirroring the real security-reviewer.md defect)
    must show as NOT wired -- counting it would certify a role the
    dispatcher actually rejects, which is the exact defect this test
    guards against."""
    yaml_path = tmp_path / "specialists.yaml"
    yaml_path.write_text("agents:\n  - agent_role_id: broken-role\n", encoding="utf-8")
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    # ": " inside an unquoted scalar -- invalid YAML, same shape as the real defect.
    (agents_dir / "broken.md").write_text(
        "---\n"
        "name: broken\n"
        "description: this role is read-only: it breaks the frontmatter\n"
        "tools: Read, Grep, Bash\n"
        "model: inherit\n"
        "---\n"
        "\n"
        "Authoritative contract: `agent_role_id: broken-role`.\n",
        encoding="utf-8",
    )

    result = project_status._collect_specialist_wiring(
        specialists_yaml=yaml_path,
        claude_agents_dir=agents_dir,
    )

    assert result["ok"] is True
    assert result["declared_count"] == 1
    assert result["wired_ids"] == []
    assert "broken-role" not in result["wired_files"]


def test_check_agents_dir_passes_on_valid_definitions(tmp_path: Path) -> None:
    """A directory containing only structurally valid frontmatter must PASS."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "one.md").write_text(_valid_agent_md("one", "role-one"), encoding="utf-8")
    (agents_dir / "two.md").write_text(_valid_agent_md("two", "role-two"), encoding="utf-8")

    ok, message = project_status._check_agents_dir(agents_dir=agents_dir)

    assert ok is True
    assert "2 agent definition file(s)" in message


def test_check_agents_dir_fails_on_unquoted_colon_and_names_file(tmp_path: Path) -> None:
    """A frontmatter description containing an unquoted ': ' sequence is
    invalid YAML (mapping values are not allowed here) -- this is the exact
    shape of the real security-reviewer.md defect that made the dispatcher
    report 'Agent type not found' while this command still said PASS. The
    check must FAIL and name the offending file."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "good.md").write_text(_valid_agent_md("good", "role-good"), encoding="utf-8")
    (agents_dir / "broken.md").write_text(
        "---\n"
        "name: broken\n"
        "description: this role is read-only: it does not implement fixes\n"
        "tools: Read, Grep, Bash\n"
        "model: inherit\n"
        "---\n"
        "\n"
        "body\n",
        encoding="utf-8",
    )

    ok, message = project_status._check_agents_dir(agents_dir=agents_dir)

    assert ok is False
    assert "broken.md" in message
    assert "1 invalid definition" in message


def test_check_agents_dir_fails_when_tools_field_missing(tmp_path: Path) -> None:
    """A frontmatter block that parses fine as YAML but is missing the
    required `tools` field must still FAIL -- parsing is necessary but not
    sufficient for "dispatchable"."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "no_tools.md").write_text(
        "---\n"
        "name: no-tools\n"
        "description: valid YAML, missing a required field\n"
        "model: inherit\n"
        "---\n"
        "\n"
        "body\n",
        encoding="utf-8",
    )

    ok, message = project_status._check_agents_dir(agents_dir=agents_dir)

    assert ok is False
    assert "no_tools.md" in message
    assert "tools" in message


def test_check_agents_dir_fails_when_name_field_missing(tmp_path: Path) -> None:
    """Same as above but for the `name` field -- this is the field the
    dispatcher was confirmed to key registration failure on."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "no_name.md").write_text(
        "---\n"
        "description: valid YAML, missing a required field\n"
        "tools: Read, Grep, Bash\n"
        "model: inherit\n"
        "---\n"
        "\n"
        "body\n",
        encoding="utf-8",
    )

    ok, message = project_status._check_agents_dir(agents_dir=agents_dir)

    assert ok is False
    assert "no_name.md" in message
    assert "name" in message


def test_check_agents_dir_removing_validation_would_be_caught_by_mutation(tmp_path: Path) -> None:
    """Belt-and-braces: directly assert _parse_agent_frontmatter itself
    rejects the real defect shape, independent of _check_agents_dir's
    message wording, so a future refactor of the message string can't
    accidentally make this suite pass while the gate is gone."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    broken = agents_dir / "broken.md"
    broken.write_text(
        "---\n"
        "name: broken\n"
        "description: this role is read-only: it does not implement fixes\n"
        "tools: Read, Grep, Bash\n"
        "model: inherit\n"
        "---\n"
        "\n"
        "body\n",
        encoding="utf-8",
    )

    data, reason = project_status._parse_agent_frontmatter(broken)

    assert data is None
    assert reason is not None
    assert "broken.md" in reason
