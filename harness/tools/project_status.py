"""Print a compact, factual "where are we / what can I do next" report.

Bounded harness-enforcement tooling (read-only inspection), not product
feature code — see current-state.md section 7 item 11.

This command exists so a human does not have to reconstruct project state
from a conversation, six documents, and PR history. It gathers FACTS by
shelling out to git/gh and parsing docs/40-delivery/current-state.md as
data (never hardcoding its table contents), and prints UNKNOWN rather than
guessing whenever a fact cannot be determined.

Usage:
    python harness/tools/project_status.py [--strict]

Exit code is always 0, UNLESS --strict is passed AND at least one
wiring/drift check fails, in which case it exits 1. --strict is not wired
into CI by this change.

Read-only: this script must never mutate git state, move files, run tests,
or perform network writes. Reading CI status via `gh` is a network read
and is fine.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT_STATE_PATH = REPO_ROOT / "docs" / "40-delivery" / "current-state.md"

UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path = REPO_ROOT, timeout: int = 15) -> tuple[int, str, str]:
    """Run a command, never raising. Returns (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", f"command not found: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", "command timed out"
    except OSError as exc:
        return 1, "", str(exc)


def _hr(title: str) -> str:
    return f"\n== {title} ==" if title else ""


# ---------------------------------------------------------------------------
# 1. GIT
# ---------------------------------------------------------------------------


def collect_git_facts() -> dict:
    facts: dict = {}

    rc, out, err = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    facts["branch"] = out if rc == 0 and out else UNKNOWN
    if rc != 0:
        facts["branch_reason"] = err or "git rev-parse failed"

    rc, out, err = _run(["git", "status", "--porcelain"])
    if rc == 0:
        facts["working_tree_clean"] = out == ""
        facts["dirty_entries"] = out.splitlines() if out else []
    else:
        facts["working_tree_clean"] = UNKNOWN
        facts["dirty_entries"] = []
        facts["working_tree_reason"] = err or "git status failed"

    rc, head_sha, err = _run(["git", "rev-parse", "HEAD"])
    facts["head_sha"] = head_sha if rc == 0 and head_sha else UNKNOWN

    # Compare against the locally-known origin/main ref. Deliberately does
    # NOT `git fetch` first (that would be a network write to local refs) --
    # this reflects the last time origin/main was fetched, and says so.
    rc, origin_sha, err = _run(["git", "rev-parse", "origin/main"])
    if rc != 0 or not origin_sha:
        facts["origin_main_sha"] = UNKNOWN
        facts["origin_main_reason"] = err or "no local origin/main ref (never fetched?)"
        facts["local_matches_origin_main"] = UNKNOWN
    else:
        facts["origin_main_sha"] = origin_sha
        rc, current_main_sha, _ = _run(["git", "rev-parse", "main"])
        if rc == 0 and current_main_sha:
            facts["local_matches_origin_main"] = current_main_sha == origin_sha
            facts["local_main_sha"] = current_main_sha
        else:
            facts["local_matches_origin_main"] = UNKNOWN
            facts["local_main_reason"] = "no local main branch found"

    return facts


def render_git(facts: dict) -> list[str]:
    lines = [_hr("1. GIT")]
    lines.append(f"branch: {facts['branch']}")
    if facts.get("branch_reason"):
        lines.append(f"  (reason: {facts['branch_reason']})")

    clean = facts["working_tree_clean"]
    if clean is UNKNOWN:
        lines.append(f"working tree clean: {UNKNOWN} ({facts.get('working_tree_reason')})")
    elif clean:
        lines.append("working tree clean: yes")
    else:
        lines.append(f"working tree clean: NO ({len(facts['dirty_entries'])} changed path(s))")
        for entry in facts["dirty_entries"][:10]:
            lines.append(f"    {entry}")

    lines.append(f"HEAD: {facts['head_sha']}")

    match = facts.get("local_matches_origin_main")
    if match is UNKNOWN:
        lines.append(
            f"local main vs origin/main: {UNKNOWN} "
            f"({facts.get('origin_main_reason') or facts.get('local_main_reason')})"
        )
    elif match:
        lines.append(f"local main matches known origin/main: yes ({facts['origin_main_sha'][:12]})")
    else:
        lines.append(
            "local main matches known origin/main: NO "
            f"(local {facts.get('local_main_sha', UNKNOWN)[:12]} vs "
            f"origin {facts['origin_main_sha'][:12]})"
        )
    lines.append(
        "  (note: compares against the last-fetched origin/main ref; this command "
        "never runs `git fetch`, so this can be stale.)"
    )
    return lines


# ---------------------------------------------------------------------------
# 2. CI
# ---------------------------------------------------------------------------


def collect_ci_facts() -> dict:
    rc, out, err = _run(
        [
            "gh",
            "run",
            "list",
            "--branch",
            "main",
            "--limit",
            "1",
            "--json",
            "conclusion,status,headSha,createdAt,name,url",
        ]
    )
    if rc == 127:
        return {"available": False, "reason": "gh CLI not found on PATH"}
    if rc != 0:
        reason = err or out or f"gh exited {rc}"
        if "auth" in reason.lower() or "credential" in reason.lower():
            reason = f"gh appears unauthenticated: {reason}"
        return {"available": False, "reason": reason}

    try:
        runs = json.loads(out) if out else []
    except json.JSONDecodeError as exc:
        return {"available": False, "reason": f"could not parse gh output: {exc}"}

    if not runs:
        return {"available": False, "reason": "no workflow runs found on main"}

    run = runs[0]
    return {
        "available": True,
        "name": run.get("name", UNKNOWN),
        "conclusion": run.get("conclusion") or "(in progress)",
        "status": run.get("status", UNKNOWN),
        "head_sha": run.get("headSha", UNKNOWN),
        "created_at": run.get("createdAt", UNKNOWN),
        "url": run.get("url", UNKNOWN),
    }


def render_ci(facts: dict) -> list[str]:
    lines = [_hr("2. CI (most recent run on main)")]
    if not facts.get("available"):
        lines.append(f"status: {UNKNOWN} ({facts.get('reason')})")
        lines.append("  (never assume green when this is UNKNOWN.)")
        return lines
    lines.append(f"workflow: {facts['name']}")
    lines.append(f"status: {facts['status']}  conclusion: {facts['conclusion']}")
    lines.append(f"commit: {facts['head_sha'][:12] if facts['head_sha'] != UNKNOWN else UNKNOWN}")
    lines.append(f"created: {facts['created_at']}")
    lines.append(f"url: {facts['url']}")
    return lines


# ---------------------------------------------------------------------------
# markdown parsing helpers shared by sections 3/4/6
# ---------------------------------------------------------------------------


def _read_current_state() -> str | None:
    if not CURRENT_STATE_PATH.exists():
        return None
    try:
        return CURRENT_STATE_PATH.read_text(encoding="utf-8")
    except OSError:
        return None


def _extract_section(text: str, heading_number: str) -> str | None:
    """Return the body text of a top-level `## <heading_number>. ...` section."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading_number)}\.\s.*$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    next_heading = re.search(r"^##\s+\d+\.\s", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def _parse_markdown_table(section_text: str) -> list[dict[str, str]]:
    """Parse the first markdown table found in section_text into row dicts."""
    lines = [ln for ln in section_text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []

    def split_row(line: str) -> list[str]:
        cells = line.strip().strip("|").split("|")
        return [c.strip() for c in cells]

    header = split_row(lines[0])
    # lines[1] is expected to be the --- separator row; skip it.
    rows = []
    for line in lines[2:]:
        cells = split_row(line)
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _parse_numbered_list(section_text: str) -> list[str]:
    items = []
    for line in section_text.splitlines():
        m = re.match(r"^\s*(\d+)\.\s+(.*\S)\s*$", line)
        if m:
            items.append(m.group(2))
    return items


# ---------------------------------------------------------------------------
# 3. GOVERNANCE STATE (current-state.md section 2)
# ---------------------------------------------------------------------------


def collect_governance_facts() -> dict:
    text = _read_current_state()
    if text is None:
        return {"available": False, "reason": f"{CURRENT_STATE_PATH} not found or unreadable"}

    section = _extract_section(text, "2")
    if section is None:
        return {"available": False, "reason": "could not find '## 2.' section heading"}

    rows = _parse_markdown_table(section)
    if not rows:
        return {"available": False, "reason": "found section 2 but no markdown table inside it"}

    return {"available": True, "rows": rows}


def render_governance(facts: dict) -> list[str]:
    lines = [_hr("3. GOVERNANCE STATE (parsed from current-state.md section 2)")]
    if not facts.get("available"):
        lines.append(f"{UNKNOWN} ({facts.get('reason')})")
        return lines
    for row in facts["rows"]:
        values = list(row.values())
        if len(values) < 2:
            continue
        area, status = values[0], values[1]
        lines.append(f"- {area}: {status}")
    return lines


# ---------------------------------------------------------------------------
# 4. OPEN PILOT DECISIONS (current-state.md section 6)
# ---------------------------------------------------------------------------


def collect_pilot_decision_facts() -> dict:
    text = _read_current_state()
    if text is None:
        return {"available": False, "reason": f"{CURRENT_STATE_PATH} not found or unreadable"}

    section = _extract_section(text, "6")
    if section is None:
        return {"available": False, "reason": "could not find '## 6.' section heading"}

    rows = _parse_markdown_table(section)
    if not rows:
        return {"available": False, "reason": "found section 6 but no markdown table inside it"}

    status_key = next((k for k in rows[0] if k.strip().lower() == "status"), None)
    adr_key = next((k for k in rows[0] if k.strip().lower() == "adr"), None)
    owner_key = next(
        (k for k in rows[0] if "owner" in k.strip().lower()), None
    )
    if status_key is None or adr_key is None:
        return {
            "available": False,
            "reason": f"table found but missing expected columns (got: {list(rows[0])})",
        }

    open_rows = [r for r in rows if r.get(status_key, "").strip().upper() == "OPEN"]
    return {
        "available": True,
        "total": len(rows),
        "open": [
            {"adr": r.get(adr_key, UNKNOWN), "owner": r.get(owner_key, UNKNOWN) if owner_key else UNKNOWN}
            for r in open_rows
        ],
    }


def render_pilot_decisions(facts: dict) -> list[str]:
    lines = [_hr("4. OPEN PILOT DECISIONS (parsed from current-state.md section 6)")]
    if not facts.get("available"):
        lines.append(f"{UNKNOWN} ({facts.get('reason')})")
        return lines
    lines.append(f"{len(facts['open'])} of {facts['total']} decision row(s) are OPEN:")
    for item in facts["open"]:
        lines.append(f"  - {item['adr']}: owner = {item['owner']}")
    if not facts["open"]:
        lines.append("  (none open)")
    return lines


# ---------------------------------------------------------------------------
# 5. WIRING/DRIFT CHECKS
# ---------------------------------------------------------------------------

SCAN_ROOTS = ["apps/api/app", "apps/web/app", "eval/harness"]
SCAN_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".yaml", ".yml", ".json",
}
SCAN_EXCLUDE_DIRS = {
    ".venv", "node_modules", "__pycache__", ".next", "dist", "build", ".git",
    "worktrees",
}
TODO_MARKER_RE = re.compile(r"\b(TODO|FIXME)\b")


def _scan_todo_fixme() -> list[str]:
    hits: list[str] = []
    for root_rel in SCAN_ROOTS:
        root = REPO_ROOT / root_rel
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
                continue
            if path.suffix not in SCAN_EXTENSIONS:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if TODO_MARKER_RE.search(line):
                    rel = path.relative_to(REPO_ROOT)
                    hits.append(f"{rel}:{lineno}: {line.strip()[:100]}")
    return hits


def _check_agents_dir() -> tuple[bool, str]:
    agents_dir = REPO_ROOT / ".claude" / "agents"
    if not agents_dir.is_dir():
        return False, "no .claude/agents/ directory: agent definitions are ad-hoc, not version-controlled"
    entries = [p for p in agents_dir.iterdir() if p.is_file()]
    if not entries:
        return False, ".claude/agents/ exists but is empty: agent definitions are ad-hoc, not version-controlled"
    return True, f"{len(entries)} agent definition file(s) version-controlled under .claude/agents/"


def _check_hooks_configured() -> tuple[bool, str]:
    found: list[str] = []
    for name in ("settings.json", "settings.local.json"):
        path = REPO_ROOT / ".claude" / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        hooks = data.get("hooks")
        if hooks:
            found.append(name)
    if found:
        return True, f"hooks configured in: {', '.join(found)}"
    return False, "no non-empty 'hooks' key in .claude/settings.json or settings.local.json: no automated gating"


def _check_harness_examples() -> tuple[bool, str]:
    validator = REPO_ROOT / "harness" / "tools" / "validate_examples.py"
    if not validator.exists():
        return False, f"{validator} not found"

    venv_python = REPO_ROOT / "apps" / "api" / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = REPO_ROOT / "apps" / "api" / ".venv" / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    rc, out, err = _run([python_exe, str(validator)], cwd=REPO_ROOT, timeout=60)
    summary = (out or err or "").strip().splitlines()
    last_line = summary[-1] if summary else f"exit {rc}"
    return rc == 0, last_line


def _registered_worktree_paths() -> set[Path] | None:
    """Parse `git worktree list --porcelain` into a set of resolved worktree paths.

    Returns None if the command could not be run/parsed at all (e.g. not a
    git checkout), so callers can tell "no worktrees registered" apart from
    "could not determine registration".
    """
    rc, out, _err = _run(["git", "worktree", "list", "--porcelain"])
    if rc != 0:
        return None
    paths: set[Path] = set()
    for line in out.splitlines():
        if line.startswith("worktree "):
            raw = line[len("worktree ") :].strip()
            if raw:
                paths.add(Path(raw).resolve())
    return paths


def _check_stale_worktrees(
    worktrees_dir: Path | None = None, registered_paths: set[Path] | None = None
) -> tuple[bool, str]:
    """Flag `.claude/worktrees/` directories that are NOT a registered git
    worktree but still contain files.

    Why this matters: this repo's agents are told to find files by NAME
    (Grep with glob:, or `find` excluding worktrees/node_modules/.venv)
    precisely because a stale, unregistered worktree directory shadows the
    live tree -- a name-based `find` (without exclusions) returns files
    under an abandoned worktree BEFORE the real path, so an edit can land
    in the abandoned copy and still look like it succeeded. A directory
    that IS a registered worktree is not stale -- an agent may legitimately
    be working in it right now.

    `registered_paths`, when given, is used verbatim instead of shelling out
    to `git worktree list --porcelain` -- this is the seam tests use to
    exercise registered/unregistered scenarios against a `tmp_path` fixture
    without creating a real git worktree.

    Report-only: this never deletes, moves, prunes, or junctions anything.
    """
    root = worktrees_dir if worktrees_dir is not None else (REPO_ROOT / ".claude" / "worktrees")
    if not root.is_dir():
        return True, f"no {root} directory: nothing to check"

    entries = sorted(p for p in root.iterdir() if p.is_dir())
    if not entries:
        return True, f"{root} exists but is empty: no worktree copies present"

    registered = registered_paths if registered_paths is not None else _registered_worktree_paths()
    if registered is None:
        return False, f"could not run 'git worktree list --porcelain' to check {root} for stale copies"

    def _label(entry: Path) -> str:
        try:
            return str(entry.relative_to(REPO_ROOT))
        except ValueError:
            return str(entry)

    stale_populated: list[Path] = []
    stale_empty: list[Path] = []
    registered_entries: list[Path] = []
    for entry in entries:
        if entry.resolve() in registered:
            registered_entries.append(entry)
            continue
        has_files = any(p.is_file() for p in entry.rglob("*"))
        if has_files:
            stale_populated.append(entry)
        else:
            stale_empty.append(entry)

    if stale_populated:
        names = ", ".join(_label(p) for p in stale_populated)
        return False, (
            f"unregistered worktree director{'y' if len(stale_populated) == 1 else 'ies'} with files "
            f"present: {names} -- this shadows live files (a name-based `find` returns them BEFORE the "
            "real path, so an edit can silently land in the abandoned copy and still look successful); "
            "not deleted by this check -- confirm no agent is using it before removing manually"
        )

    parts = [f"{len(registered_entries)} registered worktree(s), 0 stale-populated director(ies) under {root}"]
    if registered_entries:
        names = ", ".join(_label(p) for p in registered_entries)
        parts.append(f"registered (expected only while an agent is actively working in it): {names}")
    if stale_empty:
        names = ", ".join(_label(p) for p in stale_empty)
        parts.append(f"unregistered but empty (harmless, listed for visibility): {names}")
    return True, "; ".join(parts)


def collect_drift_facts() -> dict:
    agents_ok, agents_msg = _check_agents_dir()
    hooks_ok, hooks_msg = _check_hooks_configured()
    harness_ok, harness_msg = _check_harness_examples()
    worktrees_ok, worktrees_msg = _check_stale_worktrees()
    todo_hits = _scan_todo_fixme()

    return {
        "agents_dir": {"ok": agents_ok, "message": agents_msg},
        "hooks": {"ok": hooks_ok, "message": hooks_msg},
        "harness_examples": {"ok": harness_ok, "message": harness_msg},
        "stale_worktrees": {"ok": worktrees_ok, "message": worktrees_msg},
        "todo_fixme": {
            "ok": len(todo_hits) == 0,
            "message": f"{len(todo_hits)} TODO/FIXME marker(s) found" if todo_hits else "no TODO/FIXME markers found",
            "hits": todo_hits,
        },
    }


def render_drift(facts: dict) -> list[str]:
    lines = [_hr("5. WIRING/DRIFT CHECKS")]

    a = facts["agents_dir"]
    lines.append(f"[{'PASS' if a['ok'] else 'FAIL'}] .claude/agents/ version-controlled: {a['message']}")

    h = facts["hooks"]
    lines.append(f"[{'PASS' if h['ok'] else 'FAIL'}] hooks configured: {h['message']}")

    he = facts["harness_examples"]
    lines.append(f"[{'PASS' if he['ok'] else 'FAIL'}] harness examples validate: {he['message']}")

    w = facts["stale_worktrees"]
    lines.append(f"[{'PASS' if w['ok'] else 'FAIL'}] .claude/worktrees/ stale-copy check: {w['message']}")

    t = facts["todo_fixme"]
    lines.append(f"[{'PASS' if t['ok'] else 'FAIL'}] TODO/FIXME sweep: {t['message']}")
    for hit in t["hits"][:20]:
        lines.append(f"    {hit}")
    if len(t["hits"]) > 20:
        lines.append(f"    ... and {len(t['hits']) - 20} more")

    return lines


# ---------------------------------------------------------------------------
# 6. HARNESS DECLARED VS WIRED
# ---------------------------------------------------------------------------
#
# The harness (harness/agents, harness/skills, harness/schemas, harness/hooks,
# harness/registries) declares a large surface. Declaring an asset is not the
# same as it being dispatchable/loadable/enforced. This section computes the
# gap instead of hardcoding a fraction anywhere -- any hardcoded "N of M"
# becomes a lie the moment one more thing gets wired.

SPECIALISTS_YAML = REPO_ROOT / "harness" / "agents" / "specialists.yaml"
CLAUDE_AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
HARNESS_SKILLS_DIR = REPO_ROOT / "harness" / "skills"
CLAUDE_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
HARNESS_SCHEMAS_DIR = REPO_ROOT / "harness" / "schemas"
VALIDATE_EXAMPLES_PY = REPO_ROOT / "harness" / "tools" / "validate_examples.py"
HOOKS_POLICY_YAML = REPO_ROOT / "harness" / "hooks" / "policy.yaml"
CLAUDE_HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
HARNESS_REGISTRIES_DIR = REPO_ROOT / "harness" / "registries"
EVIDENCE_PACKAGE_SCHEMA_VERSION_PREFIX = "agentforge.evidence_package/"
EVIDENCE_PACKAGE_EXAMPLE = REPO_ROOT / "harness" / "examples" / "evidence-package.yaml"
REGISTRY_CONSUMER_CANDIDATE_DIRS = [".claude", "apps", "eval", ".github", "harness/tools"]

AGENT_ROLE_ID_RE = re.compile(r"agent_role_id:\s*`?([a-z0-9\-]+)`?")


def _load_yaml(path: Path) -> tuple[object | None, str | None]:
    """Best-effort YAML load. Returns (data, error_reason_or_None); never raises."""
    try:
        import yaml
    except ImportError as exc:
        return None, f"PyYAML not importable ({exc}); try apps/api/.venv/Scripts/python.exe"
    if not path.exists():
        return None, f"{path} not found"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"could not read {path}: {exc}"
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return None, f"could not parse {path} as YAML: {exc}"
    return data, None


def _collect_specialist_wiring() -> dict:
    data, err = _load_yaml(SPECIALISTS_YAML)
    if err:
        return {"ok": False, "reason": err}
    roles = data.get("agents") if isinstance(data, dict) else None
    if not isinstance(roles, list) or not roles:
        return {"ok": False, "reason": f"no 'agents' list found in {SPECIALISTS_YAML}"}
    declared_ids = [r.get("agent_role_id") for r in roles if isinstance(r, dict) and r.get("agent_role_id")]
    if not declared_ids:
        return {"ok": False, "reason": "'agents' list present but no agent_role_id fields found"}

    wired_ids: list[str] = []
    wired_files: dict[str, str] = {}
    if CLAUDE_AGENTS_DIR.is_dir():
        for md_file in sorted(CLAUDE_AGENTS_DIR.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m = AGENT_ROLE_ID_RE.search(text)
            if m and m.group(1) in declared_ids:
                wired_ids.append(m.group(1))
                wired_files[m.group(1)] = md_file.name

    return {
        "ok": True,
        "declared_count": len(declared_ids),
        "declared_ids": declared_ids,
        "wired_ids": wired_ids,
        "wired_files": wired_files,
    }


def _collect_skill_wiring() -> dict:
    if not HARNESS_SKILLS_DIR.is_dir():
        return {"ok": False, "reason": f"{HARNESS_SKILLS_DIR} not found"}
    declared = sorted(p.name for p in HARNESS_SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
    if not declared:
        return {"ok": False, "reason": f"no SKILL.md-containing directories found under {HARNESS_SKILLS_DIR}"}
    wired = (
        sorted(p.name for p in CLAUDE_SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists())
        if CLAUDE_SKILLS_DIR.is_dir()
        else []
    )
    missing = [d for d in declared if d not in wired]
    return {"ok": True, "declared": declared, "wired": [d for d in declared if d in wired], "missing": missing}


def _collect_schema_wiring() -> dict:
    if not HARNESS_SCHEMAS_DIR.is_dir():
        return {"ok": False, "reason": f"{HARNESS_SCHEMAS_DIR} not found"}
    declared = sorted(p.name for p in HARNESS_SCHEMAS_DIR.glob("*.schema.json"))
    if not declared:
        return {"ok": False, "reason": f"no *.schema.json files found under {HARNESS_SCHEMAS_DIR}"}
    if not VALIDATE_EXAMPLES_PY.exists():
        return {"ok": False, "reason": f"{VALIDATE_EXAMPLES_PY} not found -- cannot determine schema consumers"}
    try:
        text = VALIDATE_EXAMPLES_PY.read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "reason": f"could not read {VALIDATE_EXAMPLES_PY}: {exc}"}
    # Parses the schema filenames actually referenced by the PAIRS list in
    # validate_examples.py -- not a hardcoded list, so it tracks that file.
    referenced = set(re.findall(r'"schemas"\s*/\s*"([A-Za-z0-9\-.]+\.schema\.json)"', text))
    wired = sorted(n for n in declared if n in referenced)
    missing = sorted(n for n in declared if n not in referenced)
    return {"ok": True, "declared": declared, "wired": wired, "missing": missing}


def _collect_hook_wiring() -> dict:
    data, err = _load_yaml(HOOKS_POLICY_YAML)
    if err:
        return {"ok": False, "reason": err}
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        return {"ok": False, "reason": f"no 'rules' list found in {HOOKS_POLICY_YAML}"}
    rule_ids = [r.get("rule_id") for r in rules if isinstance(r, dict) and r.get("rule_id")]
    if not rule_ids:
        return {"ok": False, "reason": "'rules' list present but no rule_id fields found"}

    scripts: list[str] = []
    traceable_matches: list[str] = []
    if CLAUDE_HOOKS_DIR.is_dir():
        scripts = sorted(p.name for p in CLAUDE_HOOKS_DIR.glob("*.mjs"))
        for script in scripts:
            try:
                text = (CLAUDE_HOOKS_DIR / script).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for rid in rule_ids:
                if rid in text:
                    traceable_matches.append(f"{rid} -> {script}")

    return {
        "ok": True,
        "declared_count": len(rule_ids),
        "script_count": len(scripts),
        "scripts": scripts,
        "traceable_matches": traceable_matches,
    }


def _collect_registry_wiring() -> dict:
    if not HARNESS_REGISTRIES_DIR.is_dir():
        return {"ok": False, "reason": f"{HARNESS_REGISTRIES_DIR} not found"}
    files = sorted(HARNESS_REGISTRIES_DIR.glob("*.yaml"))
    if not files:
        return {"ok": False, "reason": f"no *.yaml files found under {HARNESS_REGISTRIES_DIR}"}

    results = []
    for f in files:
        data, err = _load_yaml(f)
        empty_note = None
        if err is None and isinstance(data, dict):
            empty_lists = [k for k, v in data.items() if isinstance(v, list) and len(v) == 0]
            if empty_lists:
                empty_note = f"empty list field(s): {', '.join(empty_lists)}"

        consumers: list[str] = []
        for root_rel in REGISTRY_CONSUMER_CANDIDATE_DIRS:
            root = REPO_ROOT / root_rel
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix not in SCAN_EXTENSIONS:
                    continue
                if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if f.name in text:
                    consumers.append(str(path.relative_to(REPO_ROOT)))

        results.append(
            {"file": f.name, "empty_note": empty_note, "consumer_count": len(consumers), "consumers": consumers}
        )
    return {"ok": True, "results": results, "scanned_dirs": REGISTRY_CONSUMER_CANDIDATE_DIRS}


def _collect_evidence_package_instances() -> dict:
    try:
        import yaml
    except ImportError as exc:
        return {"ok": False, "reason": f"PyYAML not importable ({exc}); try apps/api/.venv/Scripts/python.exe"}

    real_instances: list[str] = []
    scanned = 0
    example_resolved = EVIDENCE_PACKAGE_EXAMPLE.resolve() if EVIDENCE_PACKAGE_EXAMPLE.exists() else None
    for path in REPO_ROOT.rglob("*.y*ml"):
        if not path.is_file():
            continue
        if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        scanned += 1
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 -- best-effort scan, any bad file is just skipped
            continue
        if not isinstance(data, dict):
            continue
        schema_version = data.get("schema_version")
        if not isinstance(schema_version, str) or not schema_version.startswith(
            EVIDENCE_PACKAGE_SCHEMA_VERSION_PREFIX
        ):
            continue
        if example_resolved is not None and path.resolve() == example_resolved:
            continue
        real_instances.append(str(path.relative_to(REPO_ROOT)))

    return {"ok": True, "scanned_file_count": scanned, "real_instances": sorted(real_instances)}


def collect_harness_wiring_facts() -> dict:
    return {
        "specialists": _collect_specialist_wiring(),
        "skills": _collect_skill_wiring(),
        "schemas": _collect_schema_wiring(),
        "hooks": _collect_hook_wiring(),
        "registries": _collect_registry_wiring(),
        "evidence_packages": _collect_evidence_package_instances(),
    }


def render_harness_wiring(facts: dict) -> list[str]:
    lines = [
        _hr(
            "6. HARNESS DECLARED VS WIRED (declared = version-controlled and "
            "parseable; wired = has a real dispatch/load/validation/enforcement "
            "consumer, computed below, never hardcoded)"
        )
    ]

    s = facts["specialists"]
    if not s.get("ok"):
        lines.append(f"specialist roles: {UNKNOWN} ({s.get('reason')})")
    else:
        lines.append(
            f"specialist roles: {len(s['wired_ids'])} of {s['declared_count']} wired "
            "(has a dispatchable .claude/agents/*.md definition)"
        )
        missing = [rid for rid in s["declared_ids"] if rid not in s["wired_ids"]]
        if missing:
            lines.append(f"  not wired: {', '.join(missing)}")
        if s["wired_files"]:
            mapping = ", ".join(f"{rid} <- {fname}" for rid, fname in sorted(s["wired_files"].items()))
            lines.append(f"  wired via: {mapping}")

    sk = facts["skills"]
    if not sk.get("ok"):
        lines.append(f"skills: {UNKNOWN} ({sk.get('reason')})")
    else:
        lines.append(f"skills: {len(sk['wired'])} of {len(sk['declared'])} mirrored into .claude/skills/ (loadable)")
        if sk["missing"]:
            lines.append(f"  not mirrored: {', '.join(sk['missing'])}")

    sc = facts["schemas"]
    if not sc.get("ok"):
        lines.append(f"schemas: {UNKNOWN} ({sc.get('reason')})")
    else:
        lines.append(
            f"schemas: {len(sc['wired'])} of {len(sc['declared'])} have a "
            "validate_examples.py PAIRS consumer"
        )
        if sc["missing"]:
            lines.append(f"  never validated by anything: {', '.join(sc['missing'])}")

    h = facts["hooks"]
    if not h.get("ok"):
        lines.append(f"hook rules: {UNKNOWN} ({h.get('reason')})")
    else:
        lines.append(
            f"hook rules: {h['declared_count']} declared in harness/hooks/policy.yaml vs "
            f"{h['script_count']} real script(s) under .claude/hooks/ "
            f"({', '.join(h['scripts']) if h['scripts'] else 'none'})"
        )
        if h["traceable_matches"]:
            lines.append(f"  traceable rule_id -> script match(es): {', '.join(h['traceable_matches'])}")
        else:
            lines.append(
                "  0 rule_id string(s) found verbatim inside those scripts -- any "
                "correspondence between the two counts is coincidental, not a "
                "verified/traceable mapping."
            )

    r = facts["registries"]
    if not r.get("ok"):
        lines.append(f"registries: {UNKNOWN} ({r.get('reason')})")
    else:
        lines.append(
            f"registries: {len(r['results'])} file(s) under harness/registries/, "
            f"consumer scan of [{', '.join(r['scanned_dirs'])}]:"
        )
        for item in r["results"]:
            note = f" ({item['empty_note']})" if item["empty_note"] else ""
            lines.append(f"  - {item['file']}: {item['consumer_count']} referencing file(s) found{note}")
            for c in item["consumers"][:5]:
                lines.append(f"      {c}")

    e = facts["evidence_packages"]
    if not e.get("ok"):
        lines.append(f"evidence package instances: {UNKNOWN} ({e.get('reason')})")
    else:
        lines.append(
            f"evidence package instances: {len(e['real_instances'])} real instance(s) found "
            f"(schema_version starts with '{EVIDENCE_PACKAGE_SCHEMA_VERSION_PREFIX}', excluding "
            f"the example; scanned {e['scanned_file_count']} YAML file(s) repo-wide)"
        )
        for inst in e["real_instances"]:
            lines.append(f"  - {inst}")
        if not e["real_instances"]:
            lines.append(
                "  0 of the accepted Work Orders under harness/work-orders/ have a "
                "matching Evidence Package instance."
            )

    return lines


# ---------------------------------------------------------------------------
# 7. NEXT VALID ACTION (current-state.md section 11)
# ---------------------------------------------------------------------------


def collect_next_action_facts() -> dict:
    text = _read_current_state()
    if text is None:
        return {"available": False, "reason": f"{CURRENT_STATE_PATH} not found or unreadable"}

    section = _extract_section(text, "11")
    if section is None:
        return {"available": False, "reason": "could not find '## 11.' section heading"}

    items = _parse_numbered_list(section)
    if not items:
        return {"available": False, "reason": "found section 11 but no numbered list inside it"}

    # Capture any trailing bolded "safe state" sentence as a bonus fact, best
    # effort only -- absence of it is not an error.
    safe_state_match = re.search(r"safe state is:\s*(.+?)\.?\s*$", section, re.MULTILINE)
    safe_state = safe_state_match.group(1).strip().strip("*") if safe_state_match else None

    return {"available": True, "items": items, "safe_state": safe_state}


def render_next_action(facts: dict) -> list[str]:
    lines = [_hr("7. NEXT VALID ACTION (parsed from current-state.md section 11)")]
    if not facts.get("available"):
        lines.append(f"{UNKNOWN} ({facts.get('reason')})")
        return lines
    for i, item in enumerate(facts["items"], start=1):
        lines.append(f"  {i}. {item}")
    if facts.get("safe_state"):
        lines.append(f"until step 1 begins, safe state: {facts['safe_state']}")
    return lines


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _make_stdout_utf8_safe() -> None:
    """Best-effort: avoid UnicodeEncodeError on legacy code-page consoles
    (e.g. Windows cp949/cp1252) when current-state.md content contains
    characters like em dashes. Never raises."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def main(argv: list[str]) -> int:
    _make_stdout_utf8_safe()
    strict = "--strict" in argv

    git_facts = collect_git_facts()
    ci_facts = collect_ci_facts()
    gov_facts = collect_governance_facts()
    pilot_facts = collect_pilot_decision_facts()
    drift_facts = collect_drift_facts()
    harness_wiring_facts = collect_harness_wiring_facts()
    next_facts = collect_next_action_facts()

    output: list[str] = ["AGENTFORGE PROJECT STATUS", "=" * 26]
    output += render_git(git_facts)
    output += render_ci(ci_facts)
    output += render_governance(gov_facts)
    output += render_pilot_decisions(pilot_facts)
    output += render_drift(drift_facts)
    output += render_harness_wiring(harness_wiring_facts)
    output += render_next_action(next_facts)
    output.append("")

    print("\n".join(output))

    if strict:
        drift_failed = any(not check["ok"] for check in drift_facts.values())
        if drift_failed:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
