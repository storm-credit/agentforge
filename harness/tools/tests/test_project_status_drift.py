"""Tests for the `.claude/worktrees/` stale-copy check in project_status.py.

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
    in it -- an agent may legitimately be working there right now."""
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
