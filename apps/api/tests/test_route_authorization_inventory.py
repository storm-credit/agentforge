"""Route-authorization inventory: every state-changing endpoint carries a recorded decision.

WO-2026-08-13-MUTATION-GATE-SWEEP-001 (AC-01, AC-02, AC-04).

WHY THIS FILE EXISTS. Authorization gaps on mutation endpoints were found four separate
times by four unrelated investigations (PR #66 and #83 on index-job authorization, PR #92 on
the reindex trust boundary, WO-2026-08-12-UPLOAD-ROLE-GATE on register/upload, and
``create_source`` found by accident while implementing something else). Each was fixed
alone. The pattern was the defect: the set of ungated mutations was *unknown*, not merely
incomplete, and an oversight looked exactly like an intentional decision in the code.

WHAT IT ENFORCES. The route list is DERIVED FROM THE RUNNING APP -- never hand-written --
and cross-checked against the OpenAPI schema, so a new POST/PUT/PATCH/DELETE endpoint cannot
reach main without an entry in ``MUTATION_AUTHORIZATION`` below. The entry must name one of
four classifications, and each classification is then verified against the endpoint's own
source:

* ``role-gated``       -- must actually call ``enforce_roles``. Catches the regression where
                          the documented gate is deleted but the doc/table still claims it.
* ``acl-gated``        -- authorization derives from the target's ACL; must say so at the site.
* ``deliberately-open``-- must state WHY it is open, at the site (AC-04).
* ``unclosed-gap``     -- a known hole that is NOT closed here because closing it removes an
                          effective capability (a product decision); must point at the
                          Work Order or decision record that owns it.

The point of the last two is that "nobody thought about it" and "we thought about it and
decided" no longer look the same in the code.

HONEST LIMITS of this mechanism:
* It proves a DECISION IS RECORDED, not that the decision is correct. A wrong classification
  passes. The classification is what a reviewer argues with; the absence of one is what this
  file makes impossible.
* ``role-gated`` is verified by the presence of an ``enforce_roles`` call in the endpoint
  source, not by its arguments or its position. A gate placed after a side effect, or one
  passing the wrong role set, still passes here. Endpoint-specific tests cover that
  (``test_source_role_gate.py``, ``test_ingestion_role_gate.py``, ``test_metadata_contracts.py``).
* Enumeration uses ``fastapi.routing.iter_route_contexts``, needed because FastAPI 0.139
  stopped flattening included routers into ``app.routes`` (they appear as a single
  ``_IncludedRouter``). If a future FastAPI removes that helper this module fails to import
  -- loudly red, which is the correct failure direction. The OpenAPI cross-check below is the
  second, independent derivation that catches a walker which silently under-reports.
"""

from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path

import pytest

RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)

STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

ROLE_GATED = "role-gated"
ACL_GATED = "acl-gated"
DELIBERATELY_OPEN = "deliberately-open"
UNCLOSED_GAP = "unclosed-gap"

CLASSIFICATIONS = frozenset({ROLE_GATED, ACL_GATED, DELIBERATELY_OPEN, UNCLOSED_GAP})

ROLES_DOC = Path(__file__).resolve().parents[3] / "docs/10-architecture/roles-and-permissions.md"


@dataclass(frozen=True)
class Decision:
    """One recorded authorization decision for one state-changing route."""

    endpoint: str
    classification: str
    rationale: str
    # Set when a route carries a known, deliberately unclosed authorization gap. The value
    # must name the Work Order / decision record that owns the decision, because "we know and
    # someone owns it" is the only honest alternative to closing it.
    unclosed_gap_ref: str = ""


# ---------------------------------------------------------------------------------------
# THE DECISION MAP. Keys are (method, path) exactly as the app routes them.
#
# Do NOT add an entry to make a failing test pass. The failure means a state-changing
# endpoint reached the app without an authorization decision -- decide first, then record.
# ---------------------------------------------------------------------------------------
MUTATION_AUTHORIZATION: dict[tuple[str, str], Decision] = {
    # ---------------------------------------------------------------- agents
    ("POST", "/api/v1/agents"): Decision(
        endpoint="create_agent",
        classification=UNCLOSED_GAP,
        rationale=(
            "No enforce_roles call: any principal, including the header-stub default "
            "'developer', can create an Agent -- and AgentCreate.status is caller-settable, "
            "so the row can be created directly in 'published' state and becomes visible to "
            "every principal via list_agents/get_agent, bypassing the PRIVILEGED_ROLES gate "
            "on publish_agent_version. Not runnable (create_agent_version IS gated), so the "
            "impact is a spoofable catalog entry. Gating it removes self-service agent "
            "creation, which is a product decision: escalated, not decided."
        ),
        unclosed_gap_ref="WO-2026-08-13-MUTATION-GATE-SWEEP (escalated to pm-orchestrator)",
    ),
    ("PATCH", "/api/v1/agents/{agent_id}"): Decision(
        endpoint="update_agent",
        classification=ROLE_GATED,
        rationale=(
            "PRIVILEGED_ROLES; action agent.update. Note this path also RETURNS the agent "
            "record, so it doubles as a privileged read of an unpublished agent."
        ),
    ),
    ("POST", "/api/v1/agents/versions"): Decision(
        endpoint="create_agent_version",
        classification=ROLE_GATED,
        rationale="PRIVILEGED_ROLES; action agent_version.create (PR #57).",
    ),
    ("POST", "/api/v1/agents/versions/{version_id}/validate"): Decision(
        endpoint="validate_agent_version",
        classification=ROLE_GATED,
        rationale="PRIVILEGED_ROLES; action agent_version.validate.",
    ),
    ("POST", "/api/v1/agents/versions/{version_id}/publish"): Decision(
        endpoint="publish_agent_version",
        classification=ROLE_GATED,
        rationale="PRIVILEGED_ROLES; action agent_version.publish.",
    ),
    # ------------------------------------------------------------- knowledge
    ("POST", "/api/v1/knowledge/sources"): Decision(
        endpoint="create_source",
        classification=ROLE_GATED,
        rationale=(
            "PRIVILEGED_ROLES; action knowledge_source.create. Closed by "
            "WO-2026-08-13-MUTATION-GATE-SWEEP -- it previously had no gate at all, so any "
            "principal could create a source and choose its default_confidentiality_level."
        ),
    ),
    ("POST", "/api/v1/knowledge/documents"): Decision(
        endpoint="register_document",
        classification=ROLE_GATED,
        rationale="PRIVILEGED_ROLES; action document.register (WO-2026-08-12-UPLOAD-ROLE-GATE).",
    ),
    ("POST", "/api/v1/knowledge/documents/upload"): Decision(
        endpoint="upload_document_and_index",
        classification=ROLE_GATED,
        rationale="PRIVILEGED_ROLES; action document.upload (WO-2026-08-12-UPLOAD-ROLE-GATE).",
    ),
    ("DELETE", "/api/v1/knowledge/documents/{document_id}"): Decision(
        endpoint="archive_document",
        classification=ROLE_GATED,
        rationale=(
            "PRIVILEGED_ROLES; action document.archive. Applies NO ACL check on the target "
            "document, so a privileged role can archive a document outside its own ACL if it "
            "obtains the id elsewhere. Reported, not fixed: adding that check SHRINKS what "
            "these roles can do, which is a product decision."
        ),
        unclosed_gap_ref="roles-and-permissions.md section 10 (privileged-mutation ACL blindness)",
    ),
    ("POST", "/api/v1/knowledge/documents/{document_id}/restore"): Decision(
        endpoint="restore_document",
        classification=ROLE_GATED,
        rationale=(
            "PRIVILEGED_ROLES; action document.restore. Same target-ACL blindness as "
            "archive_document -- reported, not fixed (capability-shrinking product decision)."
        ),
        unclosed_gap_ref="roles-and-permissions.md section 10 (privileged-mutation ACL blindness)",
    ),
    ("PATCH", "/api/v1/knowledge/documents/{document_id}/acl"): Decision(
        endpoint="update_document_acl",
        classification=ROLE_GATED,
        rationale=(
            "PRIVILEGED_ROLES; action document.acl_update (PR #21). Same target-ACL blindness "
            "as archive_document -- reported, not fixed."
        ),
        unclosed_gap_ref="roles-and-permissions.md section 10 (privileged-mutation ACL blindness)",
    ),
    ("POST", "/api/v1/knowledge/documents/{document_id}/index-jobs"): Decision(
        endpoint="create_index_job",
        classification=ACL_GATED,
        rationale=(
            "Baseline bar is the target document's read ACL (principal_can_access_document, "
            "PR #66); re-indexing a document that has_been_indexed additionally requires "
            "PRIVILEGED_ROLES (PR #83, PR #92)."
        ),
        unclosed_gap_ref="WO-2026-08-13-FIRST-INDEX-GATE",
    ),
    ("POST", "/api/v1/knowledge/index-jobs/{job_id}/process"): Decision(
        endpoint="process_index_job",
        classification=ACL_GATED,
        rationale="Same two-tier gate as create_index_job (read ACL, plus roles on re-index).",
        unclosed_gap_ref="WO-2026-08-13-FIRST-INDEX-GATE",
    ),
    ("POST", "/api/v1/knowledge/retrieval/preview"): Decision(
        endpoint="preview_retrieval",
        classification=DELIBERATELY_OPEN,
        rationale=(
            "A read in POST clothing: creates no domain state, and results are restricted to "
            "the caller's own ACL by build_acl_filter enforced in the vector store. Its only "
            "persistent effect is one audit event attributed to the caller."
        ),
    ),
    # ------------------------------------------------------------------ runs
    ("POST", "/api/v1/runs"): Decision(
        endpoint="create_run",
        classification=DELIBERATELY_OPEN,
        rationale=(
            "The product's one end-user action. Only a PUBLISHED agent version is runnable, "
            "retrieval is restricted to the caller's own ACL, and every row written is owned "
            "by (and readable only by) the calling principal or an admin. It cannot create, "
            "relabel or reclassify knowledge."
        ),
    ),
    # ------------------------------------------------------------------ eval
    ("POST", "/api/v1/eval/runs"): Decision(
        endpoint="create_eval_run",
        classification=ROLE_GATED,
        rationale=(
            "PRIVILEGED_ROLES; action eval_run.create. Reads of eval history are "
            "deliberately open (aggregate metrics, no PII) -- writes are not, because "
            "go/no-go decisions read this history."
        ),
    ),
}


# ---------------------------------------------------------------------------------------
# Derivation from the app (never a hand-written list)
# ---------------------------------------------------------------------------------------
def _app():
    from app.main import create_app

    return create_app()


def walked_state_changing_routes() -> dict[tuple[str, str], object]:
    """(method, path) -> endpoint function, walked out of the app's real route table."""
    from fastapi.routing import APIRoute, iter_route_contexts

    routes: dict[tuple[str, str], object] = {}
    for context in iter_route_contexts(_app().routes):
        if not isinstance(context.route, APIRoute):
            continue
        for method in context.methods or ():
            if method in STATE_CHANGING_METHODS:
                routes[(method, context.path)] = context.endpoint
    return routes


def openapi_state_changing_routes() -> set[tuple[str, str]]:
    """Second, independent derivation: the published OpenAPI schema."""
    schema = _app().openapi()
    return {
        (method.upper(), path)
        for path, operations in schema.get("paths", {}).items()
        for method in operations
        if method.upper() in STATE_CHANGING_METHODS
    }


def _endpoint_source(endpoint) -> str:
    return inspect.getsource(inspect.unwrap(endpoint))


def _fmt(route: tuple[str, str]) -> str:
    return f"{route[0]} {route[1]}"


# ---------------------------------------------------------------------------------------
# AC-01 / AC-02
# ---------------------------------------------------------------------------------------
def test_route_enumeration_is_not_vacuous():
    """A walker that silently returns nothing would make every test below pass trivially."""
    from_schema = openapi_state_changing_routes()
    assert ("POST", "/api/v1/knowledge/sources") in from_schema
    assert len(from_schema) >= 10, (
        "The OpenAPI schema reports almost no state-changing routes. Enumeration is broken; "
        "do not trust the inventory tests until it is fixed."
    )


def test_openapi_schema_adds_no_route_the_walk_missed():
    """Cross-check the two derivations, so a broken route walk cannot hide a mutation."""
    missed = openapi_state_changing_routes() - set(walked_state_changing_routes())
    assert not missed, (
        "These state-changing routes appear in the OpenAPI schema but were not found by the "
        f"route-table walk: {sorted(map(_fmt, missed))}. The walk in "
        "walked_state_changing_routes() is out of date with this FastAPI version."
    )


def test_every_state_changing_route_has_a_recorded_authorization_decision():
    """AC-02: an unrecorded POST/PUT/PATCH/DELETE route turns the suite red.

    Both directions are checked. Unrecorded routes are the security failure; stale entries
    are how an inventory quietly stops describing the app.
    """
    walked = set(walked_state_changing_routes())
    recorded = set(MUTATION_AUTHORIZATION)

    unrecorded = walked - recorded
    assert not unrecorded, (
        "State-changing route(s) with NO recorded authorization decision: "
        f"{sorted(map(_fmt, unrecorded))}.\n"
        "Decide the authorization for each one, then record it in MUTATION_AUTHORIZATION in "
        "this file (tests/test_route_authorization_inventory.py) as role-gated, acl-gated, "
        "deliberately-open or unclosed-gap, add the matching AUTHZ-DECISION comment at the "
        "endpoint, and add the row to docs/10-architecture/roles-and-permissions.md section 10."
    )

    stale = recorded - walked
    assert not stale, (
        f"MUTATION_AUTHORIZATION records route(s) the app no longer serves: "
        f"{sorted(map(_fmt, stale))}. Remove the stale entries (and the doc rows)."
    )


def test_recorded_decisions_are_well_formed():
    for route, decision in sorted(MUTATION_AUTHORIZATION.items()):
        assert decision.classification in CLASSIFICATIONS, (
            f"{_fmt(route)}: unknown classification {decision.classification!r}"
        )
        assert len(decision.rationale.strip()) >= 40, (
            f"{_fmt(route)}: rationale is too thin to be a decision -- say what authorizes "
            "the call, or why nothing needs to."
        )


def test_recorded_endpoint_names_match_the_app():
    walked = walked_state_changing_routes()
    for route, decision in sorted(MUTATION_AUTHORIZATION.items()):
        actual = getattr(walked[route], "__name__", "")
        assert actual == decision.endpoint, (
            f"{_fmt(route)} is served by {actual!r}, but the inventory records "
            f"{decision.endpoint!r}. The inventory is describing a different endpoint than "
            "the one the app routes."
        )


# ---------------------------------------------------------------------------------------
# AC-04: the classification must be visible at the site, not only in this table
# ---------------------------------------------------------------------------------------
def test_role_gated_routes_actually_call_enforce_roles():
    """Structural, not decorative: if the gate is deleted, the inventory stops agreeing."""
    walked = walked_state_changing_routes()
    for route, decision in sorted(MUTATION_AUTHORIZATION.items()):
        if decision.classification != ROLE_GATED:
            continue
        source = _endpoint_source(walked[route])
        assert "enforce_roles(" in source, (
            f"{_fmt(route)} is recorded as role-gated, but {decision.endpoint} contains no "
            "enforce_roles call. Either the gate was removed (a regression) or the "
            "classification is wrong."
        )


def test_non_role_gated_routes_state_their_decision_at_the_site():
    """AC-04. An ACL-gated, deliberately-open or knowingly-open mutation must SAY SO in code.

    This is the check that makes an oversight distinguishable from a decision: an endpoint
    with no gate and no marker fails, whatever the table says.
    """
    walked = walked_state_changing_routes()
    for route, decision in sorted(MUTATION_AUTHORIZATION.items()):
        if decision.classification == ROLE_GATED:
            continue
        marker = f"AUTHZ-DECISION: {decision.classification}"
        source = _endpoint_source(walked[route])
        assert marker in source, (
            f"{_fmt(route)} is recorded as {decision.classification}, but "
            f"{decision.endpoint} does not carry the marker comment '{marker}' explaining "
            "why. A reader of the code must be able to tell a decision from an oversight."
        )


def test_unclosed_gaps_name_an_owner_at_the_site_and_in_the_record():
    """A known-open hole is acceptable only if something owns the decision to leave it open."""
    walked = walked_state_changing_routes()
    for route, decision in sorted(MUTATION_AUTHORIZATION.items()):
        if decision.classification == UNCLOSED_GAP:
            assert decision.unclosed_gap_ref, (
                f"{_fmt(route)} is recorded as an unclosed gap with no owning Work Order or "
                "decision record."
            )
        if not decision.unclosed_gap_ref:
            continue
        source = _endpoint_source(walked[route])
        # The pointer has to be reachable from the code, not only from this table.
        assert ("WO-" in source) or ("roles-and-permissions.md" in source), (
            f"{_fmt(route)} carries a known unclosed gap ({decision.unclosed_gap_ref}) that "
            f"is invisible at the {decision.endpoint} site. Name the Work Order or the "
            "decision record in a comment there."
        )


# ---------------------------------------------------------------------------------------
# The published inventory must keep describing the app (prose drifts; this makes it fail)
# ---------------------------------------------------------------------------------------
def test_inventory_document_lists_every_state_changing_route():
    assert ROLES_DOC.is_file(), f"Missing role/permission document at {ROLES_DOC}"
    text = ROLES_DOC.read_text(encoding="utf-8")
    missing = [
        _fmt(route) for route in sorted(MUTATION_AUTHORIZATION) if _fmt(route) not in text
    ]
    assert not missing, (
        f"docs/10-architecture/roles-and-permissions.md does not list: {missing}. The "
        "published inventory has drifted from the app."
    )
