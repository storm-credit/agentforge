"""Validate harness example instances against their JSON Schemas.

Bounded harness-enforcement tooling (schema validation only). Not product
feature code. Discovers example/schema pairs from an explicit mapping below
rather than guessing from filenames, loads each YAML example, and validates
it against the corresponding schema with `jsonschema`.

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
]


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


def main() -> int:
    if not PAIRS:
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

    if checked == 0:
        print("ERROR: zero example files were actually checked -- refusing to pass vacuously.")
        return 1

    if all_errors:
        print(f"FAILED: {len(all_errors)} violation(s) across {checked} example file(s):")
        for message in all_errors:
            print(f"  - {message}")
        return 1

    print(f"OK: {checked} harness example file(s) validated against their schemas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
