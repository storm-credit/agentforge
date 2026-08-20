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
    (agents_dir / "reviewer.md").write_text("agent_role_id: shared-role\n", encoding="utf-8")
    (agents_dir / "implementer.md").write_text("agent_role_id: shared-role\n", encoding="utf-8")

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
    (agents_dir / "a.md").write_text("agent_role_id: role-a\n", encoding="utf-8")
    (agents_dir / "b.md").write_text("agent_role_id: role-b\n", encoding="utf-8")

    result = project_status._collect_specialist_wiring(
        specialists_yaml=yaml_path,
        claude_agents_dir=agents_dir,
    )

    assert result["ok"] is True
    assert result["declared_count"] == 2
    assert sorted(result["wired_ids"]) == ["role-a", "role-b"]
    assert result["wired_files"]["role-a"] == ["a.md"]
    assert result["wired_files"]["role-b"] == ["b.md"]
