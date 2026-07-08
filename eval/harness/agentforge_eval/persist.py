"""Opt-in persistence of live-eval reports to the platform's eval-run history API.

The backend endpoint (POST /api/v1/eval/runs, PR #75) stores one report per row so
/eval in the web UI can show quality history. Persistence is strictly opt-in
(AGENT_FORGE_EVAL_PERSIST) and strictly fail-soft: a broken/unreachable backend must
never turn a completed eval run into a failure — the report is the product, the
history row is a bonus.

Env vars:
- AGENT_FORGE_EVAL_PERSIST: "true"/"1"/"yes"/"on" (case-insensitive) enables the POST.
  Default: disabled — existing behavior and CI are unaffected.
- AGENT_FORGE_EVAL_LABEL: optional label for the persisted run; falls back to the
  corpus filename stem (e.g. "cases-live-v0.2").
"""

from __future__ import annotations

import os
import sys

import httpx

# The write endpoint is gated to PRIVILEGED_ROLES server-side; reuse the same
# operator/admin identity the harness already uses for its other privileged calls.
from agentforge_eval.live_runner import _OPERATOR

_TRUTHY = {"1", "true", "yes", "on"}


def persistence_enabled() -> bool:
    return os.environ.get("AGENT_FORGE_EVAL_PERSIST", "").strip().lower() in _TRUTHY


def resolve_label(corpus_filename: str) -> str:
    """AGENT_FORGE_EVAL_LABEL wins; otherwise derive from the corpus filename."""
    env_label = os.environ.get("AGENT_FORGE_EVAL_LABEL", "").strip()
    if env_label:
        return env_label
    stem = corpus_filename.rsplit(".", 1)[0]
    return stem or corpus_filename


def maybe_persist_report(
    report: dict,
    *,
    base_url: str,
    corpus_filename: str,
    client: httpx.Client | None = None,
) -> str | None:
    """POST the report to {base_url}/eval/runs if persistence is enabled.

    Returns the persisted run id, or None when disabled or on ANY failure.
    Fail-soft by contract: this function never raises — a persistence problem is a
    stderr warning, not an eval failure.
    """
    if not persistence_enabled():
        return None

    payload = {
        # aggregate() stamps corpus_id into the report; fall back to the filename stem.
        "corpus_id": report.get("corpus_id") or resolve_label(corpus_filename),
        "label": resolve_label(corpus_filename),
        "report": report,
    }
    try:
        if client is not None:
            response = client.post("/eval/runs", headers=_OPERATOR, json=payload)
        else:
            with httpx.Client(base_url=base_url, timeout=30.0) as owned:
                response = owned.post("/eval/runs", headers=_OPERATOR, json=payload)
        response.raise_for_status()
        run_id = response.json().get("id")
        print(f"[eval-persist] recorded eval run {run_id}", file=sys.stderr)
        return run_id
    except Exception as exc:  # noqa: BLE001 - fail-soft is the whole point here
        print(
            f"[eval-persist] WARNING: failed to persist eval run ({exc!r}); "
            "the report below is still valid.",
            file=sys.stderr,
        )
        return None
