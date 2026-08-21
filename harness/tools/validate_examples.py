"""Validate harness example instances against their JSON Schemas.

Bounded harness-enforcement tooling (schema validation only). Not product
feature code. Discovers example/schema pairs from an explicit mapping below
rather than guessing from filenames, loads each YAML example, and validates
it against the corresponding schema with `jsonschema`.

Two shapes of pair are supported: PAIRS (one file = one instance) and
EMBEDDED_LIST_PAIRS (one file holds a list of instances under a top-level
key, each item validated individually).

Usage:
    python harness/tools/validate_examples.py

Exits non-zero (with a message naming the file, the JSON path, and the
violation) on any validation failure. Exits non-zero if it finds zero
pairs to check, so a vacuous "pass" cannot be mistaken for a real one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HARNESS_DIR = Path(__file__).resolve().parent.parent

# Explicit example -> schema pairs. Add a line here whenever a new example
# instance is added under harness/examples/ -- deliberately not inferred from
# filenames so an example without a matching schema (or vice versa) can never
# be silently skipped.
PAIRS: list[tuple[Path, Path]] = [
    (
        HARNESS_DIR / "examples" / "work-order.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "examples" / "evidence-package.yaml",
        HARNESS_DIR / "schemas" / "evidence-package.schema.json",
    ),
    # Real (non-example) work orders live under harness/work-orders/ and are
    # registered here individually for the same reason: a glob would pass
    # vacuously the moment a file is renamed or the directory is emptied.
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-12-GROUNDING-CLAIMS.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-12-UPLOAD-ROLE-GATE.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-12-FIRST-INDEX-GATE.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-13-KOREAN-UI.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-13-CLEARANCE-FAIL-OPEN.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-13-ROLE-READ-COHERENCE.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-13-MUTATION-GATE-SWEEP.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-13-SOURCE-ACL-DEFAULTS.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-14-INGESTION-INSTRUMENTATION.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-14-EVAL-FORMAT-COVERAGE.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-14-LINEAGE-VISIBILITY.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    (
        HARNESS_DIR / "work-orders" / "WO-2026-08-14-LINEAGE-VISIBILITY-002.yaml",
        HARNESS_DIR / "schemas" / "work-order.schema.json",
    ),
    # Real (non-example) Evidence Package instances live under harness/evidence/
    # and are registered here individually for the same reason: a glob would
    # pass vacuously the moment a file is renamed or the directory is emptied.
    (
        HARNESS_DIR / "evidence" / "EP-2026-08-20-AGENT-DEFINITION-INTEGRITY.yaml",
        HARNESS_DIR / "schemas" / "evidence-package.schema.json",
    ),
    (
        HARNESS_DIR / "policies" / "model-routing.yaml",
        HARNESS_DIR / "schemas" / "model-routing-policy.schema.json",
    ),
]

# review-result.schema.json and tool-contract.schema.json are deliberately NOT
# registered anywhere in this file: there is no instance of either anywhere in
# the repository (no agentforge.review_result/ or agentforge.tool_contract/
# document exists). Validating a schema with zero instances would pass
# vacuously, which is the exact anti-pattern PAIRS/EMBEDDED_LIST_PAIRS exist to
# prevent -- do not "fix" this gap by inventing a placeholder instance just to
# have something to point a pair at. Register them here once a real instance
# exists.

# Some schemas describe one entry in a list embedded under a key inside a
# single file, rather than a whole file being one instance (e.g.
# harness/agents/specialists.yaml holds ten specialist contracts under its
# top-level `agents:` key). Each (file, key, schema) triple here validates
# every item in file[key] against schema individually. Explicit, not a glob
# over every *.yaml file, for the same reason PAIRS above is explicit.
EMBEDDED_LIST_PAIRS: list[tuple[Path, str, Path]] = [
    (
        HARNESS_DIR / "agents" / "specialists.yaml",
        "agents",
        HARNESS_DIR / "schemas" / "agent-contract.schema.json",
    ),
]

# harness/policies/model-routing.yaml -> model-routing-policy.schema.json is
# registered above (as of 2026-08-21). It was previously left out: the
# schema's top-level additionalProperties: false rejected two fields the
# instance has carried since PR #119 (`schema_ref`, `activation_blockers`).
# The product owner resolved that design gap by adding both as optional,
# typed properties on the schema (self-pointer + open activation blockers
# tied to ADR-104, which current-state.md still lists OPEN) rather than
# stripping the fields from the instance.


def _format_path(abs_path) -> str:
    """Render a jsonschema deque path like $.limitations[0].classification."""
    parts = ["$"]
    for element in abs_path:
        if isinstance(element, int):
            parts[-1] = f"{parts[-1]}[{element}]"
        else:
            parts.append(str(element))
    return ".".join(p for p in parts if p != "$") or "$"


def validate_pair(example_path: Path, schema_path: Path) -> list[str]:
    """Return a list of human-readable error messages (empty if valid)."""
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    instance = yaml.safe_load(example_path.read_text(encoding="utf-8"))

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))

    messages = []
    for error in errors:
        json_path = _format_path(error.absolute_path)
        messages.append(
            f"{example_path}: at {json_path}: {error.message} "
            f"(schema: {schema_path})"
        )
    return messages


def validate_embedded_list_pair(file_path: Path, list_key: str, schema_path: Path) -> list[str]:
    """Return error messages for each item under file_path[list_key] vs schema_path.

    Fails loudly (returns a non-empty error list) if list_key is missing or
    empty, rather than reporting success over zero contracts.
    """
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    document = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    items = document.get(list_key) if isinstance(document, dict) else None

    if not isinstance(items, list) or not items:
        return [
            f"{file_path}: '{list_key}' key is missing or empty -- "
            "refusing to pass vacuously over zero embedded instances"
        ]

    validator = Draft202012Validator(schema)
    messages: list[str] = []
    for index, item in enumerate(items):
        role_id = item.get("agent_role_id") if isinstance(item, dict) else None
        label = role_id or f"{list_key}[{index}]"
        errors = sorted(validator.iter_errors(item), key=lambda e: list(e.absolute_path))
        for error in errors:
            json_path = _format_path(error.absolute_path)
            messages.append(
                f"{file_path}: {list_key}[{index}] ({label}): at {json_path}: {error.message} "
                f"(schema: {schema_path})"
            )
    return messages


def main() -> int:
    if not PAIRS and not EMBEDDED_LIST_PAIRS:
        print("ERROR: no example/schema pairs registered -- refusing to pass vacuously.")
        return 1

    checked = 0
    all_errors: list[str] = []
    for example_path, schema_path in PAIRS:
        if not example_path.exists():
            all_errors.append(f"{example_path}: example file not found")
            continue
        if not schema_path.exists():
            all_errors.append(f"{schema_path}: schema file not found (for {example_path})")
            continue
        checked += 1
        all_errors.extend(validate_pair(example_path, schema_path))

    embedded_checked = 0
    for file_path, list_key, schema_path in EMBEDDED_LIST_PAIRS:
        if not file_path.exists():
            all_errors.append(f"{file_path}: example file not found")
            continue
        if not schema_path.exists():
            all_errors.append(f"{schema_path}: schema file not found (for {file_path})")
            continue
        embedded_checked += 1
        all_errors.extend(validate_embedded_list_pair(file_path, list_key, schema_path))

    if checked == 0 and embedded_checked == 0:
        print("ERROR: zero example files were actually checked -- refusing to pass vacuously.")
        return 1

    total_checked = checked + embedded_checked
    if all_errors:
        print(f"FAILED: {len(all_errors)} violation(s) across {total_checked} example file(s):")
        for message in all_errors:
            print(f"  - {message}")
        return 1

    print(
        f"OK: {checked} harness example file(s) and {embedded_checked} embedded-list "
        f"file(s) validated against their schemas ({total_checked} file(s) total)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
