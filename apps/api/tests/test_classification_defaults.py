"""Source-level classification defaults: inheritance, monotonicity, provenance, group shape.

WO-2026-08-13-SOURCE-ACL-DEFAULTS-001 -- AC-01 .. AC-05.

The centre of this file is ``TestMonotonicity``, which is a PROOF, not a smoke test: it
enumerates every combination of source default and document value and compares the set of
principals who can actually READ the resulting document against the set who could read the
document today's code would have produced. Effective access, computed by the real
``app.domain.acl`` predicates -- not stored field values -- because "who can read this" is a
calculation and the security panel's condition was stated about the calculation
(docs/10-architecture/ingestion-normalization-design.md section 4).
"""

from __future__ import annotations

import importlib.util
import itertools
from collections.abc import Iterator
from pathlib import Path

import pytest

RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.domain import models  # noqa: F401
    from app.main import create_app

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
        # Exposed for the audit-trail assertions.
        test_client.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session_factory():
    """A second handle on the same schema, for asserting against tables directly."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base
    from app.domain import models  # noqa: F401

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(bind=engine)


_KM = {"X-Agent-Forge-User": "km", "X-Agent-Forge-Roles": "knowledge-manager"}


def _create_source(client, **overrides) -> dict:
    body = {"name": "Src", "description": "", "owner_department": "Operations"}
    body.update(overrides)
    response = client.post("/api/v1/knowledge/sources", headers=_KM, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _register(client, source_id: str, **overrides):
    body = {
        "knowledge_source_id": source_id,
        "title": overrides.pop("title", "Doc"),
        "object_uri": "object://doc.md",
        "checksum": "sha256-doc",
        "mime_type": "text/markdown",
    }
    body.update(overrides)
    return client.post("/api/v1/knowledge/documents", headers=_KM, json=body)


def _upload(client, source_id: str, **form):
    data = {"knowledge_source_id": source_id, "title": form.pop("title", "Uploaded")}
    data.update(form)
    return client.post(
        "/api/v1/knowledge/documents/upload",
        headers=_KM,
        data=data,
        files={"file": ("doc.md", b"# Doc\n\nbody line.", "text/markdown")},
    )


# =======================================================================================
# AC-04 (part 2): the shape rule must not reject group strings that ALREADY EXIST
# =======================================================================================
#
# Enumerated by grepping the whole repository for access-group literals, not from memory:
#
#   grep -rhoE '"(all-employees|department:[^"]*|role:[^"]*|user:[^"]*|...)"' \
#        --include=*.py --include=*.ts --include=*.tsx --include=*.json --include=*.md .
#
# Every value below is a group string that a fixture, a seed script, the eval corpus, a
# frontend default or an existing test actually stores or matches on. If the shape rule
# rejected any of them, the Work Order's escalation clause applies: STOP and report the string
# and the rule -- do not loosen the rule silently and do not rewrite existing data. It did not
# happen; all of these pass. This list is the evidence for that claim.
EXISTING_GROUP_STRINGS: tuple[tuple[str, str], ...] = (
    ("all-employees", "app/seed_demo.py; upload endpoint fallback; eval corpora; frontend"),
    ("department:Operations", "app/seed_demo_rich.py restricted ops document"),
    ("department:HR", "tests/test_acl_update_contracts.py, tests/test_metadata_contracts.py"),
    ("department:hr", "docs/10-architecture role examples (lower-case variant)"),
    ("department:Finance", "eval/synthetic-corpus/cases-live-v0.1.json payroll case"),
    ("department:Security", "eval/synthetic-corpus/cases-live-v0.1.json sec-export case"),
    ("department:Audit", "eval/synthetic-corpus multi-department corpora"),
    ("department:Legal", "eval/synthetic-corpus multi-department corpora"),
    ("hr-team", "eval/synthetic-corpus/cases-pilot-hr-v1.json restricted HR cases"),
    ("hr-restricted", "apps/web/app/lib/demoRole.ts; apps/web/tests/demo-role.spec.ts"),
    ("executive-only", "eval/synthetic-corpus/cases-v0.1.json"),
    ("public", "tests/test_metadata_contracts.py ACL-patch RBAC case"),
    ("role:developer", "docs role examples / principal_acl_subjects output shape"),
    ("role:hr_manager", "docs role examples (underscore in the role name)"),
)


class TestGroupShapeRule:
    def test_rule_accepts_every_group_string_already_present_in_the_repository(self):
        """AC-04. The escalation clause was not triggered: nothing existing is rejected."""
        from app.domain.classification import access_group_shape_error

        rejected = {
            group: (access_group_shape_error(group), provenance)
            for group, provenance in EXISTING_GROUP_STRINGS
            if access_group_shape_error(group) is not None
        }
        assert not rejected, (
            "The shape rule rejects group strings that already exist in this repository: "
            f"{rejected}. Per WO-2026-08-13-SOURCE-ACL-DEFAULTS's escalation clause, report "
            "the string and the rule -- do not loosen the rule silently and do not rewrite "
            "existing data."
        )

    def test_rule_accepts_non_ascii_and_internal_spaces(self):
        """Korean department names and multi-word departments are legitimate groups."""
        from app.domain.classification import access_group_shape_error

        for group in ("department:인사팀", "department:Operations Team", "부서:영업"):
            assert access_group_shape_error(group) is None, group

    @pytest.mark.parametrize(
        ("group", "expected_fragment"),
        [
            ("all-employees ", "trailing whitespace"),
            (" all-employees", "trailing whitespace"),
            ("", "empty"),
            ("   ", "trailing whitespace"),
            ("hr,team", "comma"),
            ("hr\tteam", "control characters"),
            ("hr\nteam", "control characters"),
            ("hr\x00team", "control characters"),
            ("a" * 121, "at most"),
            ("department:", "reserved prefix"),
            ("role:", "reserved prefix"),
            ("user:", "reserved prefix"),
            ("role: admin", "reserved prefix"),
        ],
    )
    def test_rule_rejects_malformed_group_strings(self, group, expected_fragment):
        from app.domain.classification import access_group_shape_error

        reason = access_group_shape_error(group)
        assert reason is not None, f"{group!r} should be rejected"
        assert expected_fragment in reason, f"{group!r}: {reason!r}"

    def test_rule_rejects_non_strings(self):
        from app.domain.classification import access_group_shape_error

        assert access_group_shape_error(None) is not None
        assert access_group_shape_error(7) is not None

    def test_empty_group_list_is_a_shape_pass(self):
        """Emptiness is an ACL question (deny-all), not a shape question -- see acl._acl_permits."""
        from app.domain.classification import access_group_shape_errors

        assert access_group_shape_errors([]) == []

    def test_padding_is_rejected_not_silently_stripped(self):
        """Stripping ' all-employees ' would turn an unreadable document into a readable one.

        That is a WIDENING, so the rule refuses the value instead of repairing it.
        """
        from app.domain.classification import access_group_shape_error

        assert access_group_shape_error(" all-employees ") is not None


# =======================================================================================
# AC-04 (part 1): rejected at write time on EVERY path that stores group strings
# =======================================================================================
class TestGroupShapeRejectionAtWriteTime:
    def test_source_default_access_groups_rejected(self, client):
        response = client.post(
            "/api/v1/knowledge/sources",
            headers=_KM,
            json={
                "name": "Bad Defaults",
                "description": "",
                "owner_department": "Operations",
                "default_access_groups": ["hr-team "],
            },
        )
        assert response.status_code == 422
        assert "default_access_groups" in response.json()["detail"]

    def test_source_with_malformed_default_is_not_stored(self, client):
        client.post(
            "/api/v1/knowledge/sources",
            headers=_KM,
            json={
                "name": "Bad Defaults",
                "description": "",
                "owner_department": "Operations",
                "default_access_groups": ["hr,team"],
            },
        )
        assert client.get("/api/v1/knowledge/sources", headers=_KM).json() == []

    def test_register_rejects_malformed_explicit_group(self, client):
        source = _create_source(client)
        response = _register(client, source["id"], access_groups=["department:HR "])
        assert response.status_code == 422
        assert "access_groups" in response.json()["detail"]
        assert client.get("/api/v1/knowledge/documents", headers=_KM).json() == []

    def test_upload_rejects_malformed_explicit_group(self, client):
        source = _create_source(client)
        # A tab inside a comma-delimited token survives the split, so the shape rule is what
        # catches it.
        response = _upload(client, source["id"], access_groups="hr\tteam")
        assert response.status_code == 422
        assert client.get("/api/v1/knowledge/documents", headers=_KM).json() == []

    def test_acl_patch_rejects_malformed_group(self, client):
        source = _create_source(client)
        document = _register(client, source["id"], access_groups=["all-employees"]).json()
        response = client.patch(
            f"/api/v1/knowledge/documents/{document['id']}/acl",
            headers=_KM,
            json={
                "access_groups": ["hr,team"],
                "confidentiality_level": "internal",
                "reason": "typo",
            },
        )
        assert response.status_code == 422
        # The document keeps its previous ACL: a rejected relabel must not partially apply.
        current = client.get("/api/v1/knowledge/documents", headers=_KM).json()[0]
        assert current["access_groups"] == ["all-employees"]

    def test_authorization_still_precedes_group_validation(self, client):
        """A malformed group must not turn a 403 into a 422 (identity loses last)."""
        source = _create_source(client)
        response = _register(
            client,
            source["id"],
            access_groups=["hr,team"],
        )
        assert response.status_code == 422  # privileged caller: validation speaks
        unprivileged = client.post(
            "/api/v1/knowledge/documents",
            headers={"X-Agent-Forge-User": "nobody", "X-Agent-Forge-Roles": "developer"},
            json={
                "knowledge_source_id": source["id"],
                "title": "Doc",
                "object_uri": "object://doc.md",
                "checksum": "sha256-doc",
                "mime_type": "text/markdown",
                "access_groups": ["hr,team"],
            },
        )
        assert unprivileged.status_code == 403


# =======================================================================================
# AC-01: inheritance when unspecified, exact retention when specified
# =======================================================================================
class TestInheritanceAndExplicitOverride:
    def test_register_inherits_both_halves_from_the_source(self, client):
        source = _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["department:HR", "hr-team"],
        )
        document = _register(client, source["id"]).json()
        assert document["confidentiality_level"] == "restricted"
        assert document["access_groups"] == ["department:HR", "hr-team"]

    def test_register_keeps_an_explicit_value_exactly(self, client):
        source = _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["department:HR"],
        )
        document = _register(
            client,
            source["id"],
            confidentiality_level="public",
            access_groups=["all-employees"],
        ).json()
        # Explicit wins in BOTH directions, including less restrictive than the default: the
        # administrator typing a value on the document is the authority, and the source default
        # is only consulted in its absence.
        assert document["confidentiality_level"] == "public"
        assert document["access_groups"] == ["all-employees"]

    def test_upload_inherits_both_halves_from_the_source(self, client):
        source = _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["hr-team"],
        )
        body = _upload(client, source["id"]).json()
        assert body["document"]["confidentiality_level"] == "restricted"
        assert body["document"]["access_groups"] == ["hr-team"]

    def test_upload_keeps_an_explicit_value_exactly(self, client):
        source = _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["hr-team"],
        )
        body = _upload(
            client,
            source["id"],
            confidentiality_level="internal",
            access_groups="all-employees,department:Finance",
        ).json()
        assert body["document"]["confidentiality_level"] == "internal"
        assert body["document"]["access_groups"] == ["all-employees", "department:Finance"]

    def test_explicit_empty_group_list_is_a_value_not_an_absence(self, client):
        """A JSON `[]` is deny-all and is kept exactly -- the narrowest request stays available."""
        source = _create_source(client, default_access_groups=["department:HR"])
        document = _register(client, source["id"], access_groups=[]).json()
        assert document["access_groups"] == []
        assert document["access_groups_source"] == "explicit"

    def test_blank_upload_group_field_expresses_no_intent(self, client):
        """A blank form field inherits; the old code also discarded it (falling back to
        all-employees inside the parser), so the only change is which fallback applies."""
        source = _create_source(client, default_access_groups=["hr-team"])
        body = _upload(client, source["id"], access_groups="  ,  ").json()
        assert body["document"]["access_groups"] == ["hr-team"]
        assert body["document"]["access_groups_source"] == "source_default"

    def test_a_source_without_defaults_reproduces_todays_behaviour(self, client):
        """AC-02, second sentence. Both endpoints, both halves."""
        source = _create_source(client)
        assert source["default_access_groups"] == []
        assert source["default_confidentiality_level"] == "internal"

        registered = _register(client, source["id"]).json()
        # register's pre-existing fallback: "internal" + NO groups (deny-all, unindexable).
        assert registered["confidentiality_level"] == "internal"
        assert registered["access_groups"] == []

        uploaded = _upload(client, source["id"]).json()["document"]
        # upload's pre-existing fallback: "internal" + ["all-employees"].
        assert uploaded["confidentiality_level"] == "internal"
        assert uploaded["access_groups"] == ["all-employees"]

    def test_inheritance_deduplicates_only_values_it_chose_itself(self, client):
        source = _create_source(client, default_access_groups=["hr-team", "hr-team"])
        # create_source stores what it was given; the resolver de-duplicates on the way out.
        assert source["default_access_groups"] == ["hr-team", "hr-team"]
        assert _register(client, source["id"]).json()["access_groups"] == ["hr-team"]
        # ...but an explicit list is stored verbatim ("keeps it exactly").
        explicit = _register(
            client, source["id"], title="Explicit", access_groups=["hr-team", "hr-team"]
        ).json()
        assert explicit["access_groups"] == ["hr-team", "hr-team"]


# =======================================================================================
# AC-02: THE MONOTONICITY PROOF
# =======================================================================================
#: A panel of synthetic principals spanning clearance x department x groups x roles, including
#: the fail-closed edge cases (unknown clearance, padded clearance, empty department). The
#: proof below is stated over the READER SET each candidate classification produces for this
#: panel, so it is about effective access rather than about stored strings.
def _principal_panel():
    from app.core.principal import Principal

    clearances = ("public", "internal", "restricted", "confidential", "typo-xyz", "internal ", "")
    identities = (
        ("hr-user", "HR", ("all-employees", "hr-team"), ("developer",)),
        ("fin-user", "Finance", ("all-employees",), ("developer",)),
        ("ops-user", "Operations", ("all-employees", "department:Operations"), ("developer",)),
        ("no-groups", "", (), ()),
        ("km-user", "Operations", ("all-employees",), ("knowledge-manager",)),
        ("exec-user", "Executive", ("all-employees", "executive-only"), ("admin",)),
    )
    return tuple(
        Principal(
            user_id=user_id,
            department=department,
            roles=roles,
            groups=groups,
            clearance_level=clearance,
        )
        for clearance in clearances
        for user_id, department, groups, roles in identities
    )


class _CandidateDocument:
    """The minimum surface ``app.domain.acl`` reads. Status is fixed to a searchable one so
    the comparison isolates the CLASSIFICATION and never the lifecycle."""

    def __init__(self, confidentiality_level: str, access_groups):
        self.status = "registered"
        self.confidentiality_level = confidentiality_level
        self.access_groups = list(access_groups)


def _readers(confidentiality_level: str, access_groups) -> frozenset[str]:
    """Which panel principals can actually read a document with this classification."""
    from app.domain.acl import principal_can_access_document

    document = _CandidateDocument(confidentiality_level, access_groups)
    return frozenset(
        principal.user_id + "@" + principal.clearance_level
        for principal in _principal_panel()
        if principal_can_access_document(principal, document)
    )


#: Every source-default configuration worth distinguishing, including a level LESS restrictive
#: than the platform floor ("public") and an unrecognised one (fail-closed path).
SOURCE_DEFAULT_LEVELS = ("internal", "public", "restricted", "confidential", "not-a-level")
SOURCE_DEFAULT_GROUPS = (
    (),  # not configured
    ("all-employees",),  # configured as broadly as the platform's own upload fallback
    ("department:HR",),  # narrower
    ("hr-team", "department:HR"),  # narrower, multiple
    ("all-employees", "hr-team"),  # contains the universal group plus another
)
#: What the request itself expresses. None = expresses nothing (the inheritance case).
REQUESTED_LEVELS = (None, "public", "internal", "restricted", "confidential")
REQUESTED_GROUPS = (None, [], ["all-employees"], ["department:HR"])

#: Each ingestion endpoint's pre-existing fallback = the baseline the proof compares against.
ENDPOINT_BASELINES = {
    "register": ("internal", ()),
    "upload": ("internal", ("all-employees",)),
}


def _all_combinations():
    return itertools.product(
        sorted(ENDPOINT_BASELINES),
        SOURCE_DEFAULT_LEVELS,
        SOURCE_DEFAULT_GROUPS,
        REQUESTED_LEVELS,
        REQUESTED_GROUPS,
    )


def _resolve(endpoint, source_level, source_groups, requested_level, requested_groups):
    from app.domain.classification import resolve_document_classification

    fallback_level, fallback_groups = ENDPOINT_BASELINES[endpoint]
    return resolve_document_classification(
        requested_confidentiality_level=requested_level,
        requested_access_groups=requested_groups,
        source_id="src-1",
        source_default_confidentiality_level=source_level,
        source_default_access_groups=source_groups,
        platform_fallback_confidentiality_level=fallback_level,
        platform_fallback_access_groups=fallback_groups,
    )


def _baseline_today(endpoint, requested_level, requested_groups):
    """What the CURRENT (pre-change) code would have stored for the same request.

    Verified against the code being replaced, not assumed:
      * register: ``confidentiality_level: str = "internal"``,
        ``access_groups: list[str] = Field(default_factory=list)`` -> omitted means [].
      * upload:   ``Form("internal")`` / ``Form("all-employees")`` -> omitted means
        ``_parse_access_groups("all-employees") == ["all-employees"]``.
    """
    fallback_level, fallback_groups = ENDPOINT_BASELINES[endpoint]
    level = fallback_level if requested_level is None else requested_level
    groups = list(fallback_groups) if requested_groups is None else list(requested_groups)
    return level, groups


class TestMonotonicity:
    """AC-02. No combination of source default and document value yields broader access."""

    def test_the_table_is_not_vacuous(self):
        combinations = list(_all_combinations())
        # 2 endpoints x 5 source levels x 5 source group sets x 5 requested levels
        # x 4 requested group sets
        assert len(combinations) == 2 * 5 * 5 * 5 * 4 == 1000

    def test_an_explicitly_requested_value_is_never_touched_by_a_source_default(self):
        """The explicit path is bit-identical to today for EVERY source configuration."""
        for endpoint, s_level, s_groups, r_level, r_groups in _all_combinations():
            if r_level is None and r_groups is None:
                continue
            resolved = _resolve(endpoint, s_level, s_groups, r_level, r_groups)
            if r_level is not None:
                assert resolved.confidentiality_level == r_level
                assert resolved.confidentiality_source == "explicit"
            if r_groups is not None:
                assert resolved.access_groups == list(r_groups)
                assert resolved.access_groups_source == "explicit"

    def test_an_inherited_level_is_never_ranked_below_the_platform_fallback(self):
        """SEC-010, the 'raise, never lower' half. Includes the ``public`` source default,
        which MUST be clamped up, and the unrecognised one, which must fail closed."""
        from app.domain.acl import confidentiality_rank

        for endpoint, s_level, s_groups, r_level, r_groups in _all_combinations():
            if r_level is not None:
                continue
            resolved = _resolve(endpoint, s_level, s_groups, r_level, r_groups)
            baseline_level, _ = ENDPOINT_BASELINES[endpoint]
            assert confidentiality_rank(resolved.confidentiality_level) >= confidentiality_rank(
                baseline_level
            ), (endpoint, s_level, resolved.confidentiality_level)

    def test_a_source_level_below_the_floor_is_raised_and_flagged_for_audit(self):
        resolved = _resolve("register", "public", (), None, None)
        assert resolved.confidentiality_level == "internal"
        assert resolved.confidentiality_floor_applied is True

    def test_an_unrecognised_source_level_fails_closed_to_the_most_restrictive(self):
        resolved = _resolve("register", "not-a-level", (), None, None)
        assert resolved.confidentiality_level == "confidential"
        assert resolved.confidentiality_floor_applied is False

    def test_a_mixed_case_source_level_is_normalised_before_it_is_inherited(self):
        """acl.EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS is a case-SENSITIVE membership test, so an
        inherited 'Confidential' would slip past the blanket 'never index confidential content'
        rule. Inherited values are canonicalised so this path cannot produce that."""
        assert _resolve("register", "Confidential", (), None, None).confidentiality_level == (
            "confidential"
        )
        assert _resolve("upload", "  ReStricted ", (), None, None).confidentiality_level == (
            "restricted"
        )

    def test_a_source_with_no_configured_defaults_is_byte_identical_to_today(self):
        """AC-02, second sentence, over every request shape and both endpoints."""
        for endpoint in sorted(ENDPOINT_BASELINES):
            for r_level, r_groups in itertools.product(REQUESTED_LEVELS, REQUESTED_GROUPS):
                resolved = _resolve(endpoint, "internal", (), r_level, r_groups)
                today_level, today_groups = _baseline_today(endpoint, r_level, r_groups)
                assert resolved.confidentiality_level == today_level, (endpoint, r_level)
                assert resolved.access_groups == today_groups, (endpoint, r_groups)

    def test_no_combination_widens_effective_access_except_one_documented_cell(self):
        """THE PROOF. For every combination, compare the set of principals who can READ the
        resolved document against the set who could read the document today's code produces.

        The single documented exception -- and it is documented rather than hidden because the
        Work Order mandates both halves of it -- is:

            register path + document omits access_groups + source HAS a configured group default

        Today that request yields ``access_groups = []``, which is deny-all AND unindexable, so
        its reader set is EMPTY and any non-empty inheritance is formally broader. The
        widening is bounded exactly: the resulting reader set equals the reader set of the
        administrator having typed the source's configured groups ON the document, which the
        same PRIVILEGED_ROLES caller could always do. No artifact-controlled input influences
        it, nothing a non-privileged principal can reach influences it, and the confidentiality
        floor still applies. Recorded here as an assertion so it can never silently grow.
        """
        widened: list[tuple] = []
        for endpoint, s_level, s_groups, r_level, r_groups in _all_combinations():
            resolved = _resolve(endpoint, s_level, s_groups, r_level, r_groups)
            new_readers = _readers(resolved.confidentiality_level, resolved.access_groups)
            today_readers = _readers(*_baseline_today(endpoint, r_level, r_groups))
            if new_readers <= today_readers:
                continue
            is_documented_cell = (
                endpoint == "register" and r_groups is None and bool(s_groups)
            )
            if not is_documented_cell:
                widened.append((endpoint, s_level, s_groups, r_level, r_groups))
                continue
            # Bound the documented widening: it is exactly "as if the administrator had typed
            # the source's configured groups on the document".
            as_if_typed = _resolve(endpoint, s_level, s_groups, r_level, list(s_groups))
            assert new_readers == _readers(
                as_if_typed.confidentiality_level, as_if_typed.access_groups
            ), (endpoint, s_level, s_groups, r_level)
            assert today_readers == frozenset(), (
                "The documented exception assumes today's register fallback grants access to "
                f"nobody; it granted {today_readers}."
            )

        assert not widened, (
            "These combinations grant access to principals that today's code would not, "
            f"outside the one documented cell: {widened}"
        )

    def test_the_upload_path_never_widens_at_all(self):
        """Stated separately because it is the stronger claim: upload's own fallback is
        ``all-employees``, which every principal holds unconditionally, so every inherited or
        explicit group set is a subset in effective-access terms."""
        for _, s_level, s_groups, r_level, r_groups in _all_combinations():
            resolved = _resolve("upload", s_level, s_groups, r_level, r_groups)
            new_readers = _readers(resolved.confidentiality_level, resolved.access_groups)
            today_readers = _readers(*_baseline_today("upload", r_level, r_groups))
            assert new_readers <= today_readers, (s_level, s_groups, r_level, r_groups)

    def test_inheritance_reads_nothing_from_the_artifact(self):
        """SEC-010's prohibition, enforced structurally: the resolver's signature has no
        filename, path, mime type, checksum or content parameter, so no future caller can pass
        artifact-controlled input into a classification decision without changing this test."""
        import inspect

        from app.domain.classification import resolve_document_classification

        parameters = set(inspect.signature(resolve_document_classification).parameters)
        forbidden = {
            "filename",
            "file_name",
            "path",
            "folder",
            "object_uri",
            "title",
            "mime_type",
            "content",
            "source_text",
            "source_bytes",
            "checksum",
            "raw",
        }
        assert not parameters & forbidden, (
            "resolve_document_classification accepts artifact-controlled input "
            f"{sorted(parameters & forbidden)}. Deriving classification from filename, folder "
            "or content is a prohibited action under WO-2026-08-13-SOURCE-ACL-DEFAULTS."
        )
        assert parameters == {
            "requested_confidentiality_level",
            "requested_access_groups",
            "source_id",
            "source_default_confidentiality_level",
            "source_default_access_groups",
            "platform_fallback_confidentiality_level",
            "platform_fallback_access_groups",
        }


# =======================================================================================
# AC-03: provenance recorded for both paths
# =======================================================================================
class TestProvenance:
    def test_register_records_inherited_provenance_and_the_source(self, client):
        source = _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["hr-team"],
        )
        document = _register(client, source["id"]).json()
        assert document["confidentiality_source"] == "source_default"
        assert document["access_groups_source"] == "source_default"
        assert document["classification_source_id"] == source["id"]

    def test_register_records_explicit_provenance_and_no_source(self, client):
        source = _create_source(
            client, default_confidentiality_level="restricted", default_access_groups=["hr-team"]
        )
        document = _register(
            client,
            source["id"],
            confidentiality_level="internal",
            access_groups=["all-employees"],
        ).json()
        assert document["confidentiality_source"] == "explicit"
        assert document["access_groups_source"] == "explicit"
        assert document["classification_source_id"] is None

    def test_upload_records_inherited_provenance_and_the_source(self, client):
        source = _create_source(
            client, default_confidentiality_level="restricted", default_access_groups=["hr-team"]
        )
        document = _upload(client, source["id"]).json()["document"]
        assert document["confidentiality_source"] == "source_default"
        assert document["access_groups_source"] == "source_default"
        assert document["classification_source_id"] == source["id"]

    def test_upload_records_explicit_provenance(self, client):
        source = _create_source(client, default_access_groups=["hr-team"])
        document = _upload(
            client,
            source["id"],
            confidentiality_level="restricted",
            access_groups="department:HR",
        ).json()["document"]
        assert document["confidentiality_source"] == "explicit"
        assert document["access_groups_source"] == "explicit"
        assert document["classification_source_id"] is None

    def test_the_two_halves_are_recorded_independently(self, client):
        """The queryable question an incident asks is about the GROUP default specifically."""
        source = _create_source(
            client, default_confidentiality_level="restricted", default_access_groups=["hr-team"]
        )
        document = _register(client, source["id"], confidentiality_level="confidential").json()
        assert document["confidentiality_source"] == "explicit"
        assert document["access_groups_source"] == "source_default"
        assert document["classification_source_id"] == source["id"]

    def test_platform_default_is_distinguishable_from_a_source_default(self, client):
        source = _create_source(client)
        document = _upload(client, source["id"]).json()["document"]
        assert document["access_groups"] == ["all-employees"]
        assert document["access_groups_source"] == "platform_default"
        # Confidentiality always comes off the source row -- the column is NOT NULL and has
        # existed since 0001, so the schema cannot distinguish an administrator-chosen
        # "internal" from the column default, and this change does not invent that
        # distinction.
        assert document["confidentiality_source"] == "source_default"

    def test_an_acl_patch_makes_the_classification_explicit_again(self, client):
        """Stale 'source_default' provenance would poison the one query this feature exists
        for: a corrected document must stop appearing in 'touched by the broken default'."""
        source = _create_source(client, default_access_groups=["hr-team"])
        document = _register(client, source["id"]).json()
        assert document["access_groups_source"] == "source_default"

        patched = client.patch(
            f"/api/v1/knowledge/documents/{document['id']}/acl",
            headers=_KM,
            json={
                "access_groups": ["department:HR"],
                "confidentiality_level": "restricted",
                "reason": "corrected a wrong source default",
            },
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["access_groups_source"] == "explicit"
        assert body["confidentiality_source"] == "explicit"
        assert body["classification_source_id"] is None

    def test_a_document_built_through_the_orm_records_unknown_not_explicit(
        self, session_factory
    ):
        """Seed scripts and any future direct-ORM path must not falsely assert a decision.

        This is the same "the backfill invents nothing" rule applied to live inserts: a code
        path that never made a classification DECISION must record that, not claim one.
        """
        from app.domain.models import Document, KnowledgeSource

        with session_factory() as session:
            source = KnowledgeSource(name="Seeded", owner_department="Ops")
            session.add(source)
            session.flush()
            document = Document(
                knowledge_source_id=source.id,
                title="Seeded Doc",
                object_uri="seed://doc.md",
                checksum="sha256-seed",
                mime_type="text/markdown",
                confidentiality_level="internal",
                access_groups=["all-employees"],
            )
            session.add(document)
            session.flush()
            assert document.confidentiality_source == "unknown"
            assert document.access_groups_source == "unknown"
            assert document.classification_source_id is None
            # ...and the source's own group default defaults to "not configured".
            assert source.default_access_groups == []


# =======================================================================================
# The audit trail records the decision AND its provenance (the detective control)
# =======================================================================================
class TestAuditTrail:
    def _events(self, client, event_type):
        from sqlalchemy import select

        from app.domain.models import AuditEvent

        # Reach through the app's own session override so we read the same in-memory DB.
        generator = client.app.dependency_overrides[
            __import__("app.core.database", fromlist=["get_db"]).get_db
        ]()
        session = next(generator)
        try:
            return list(
                session.scalars(
                    select(AuditEvent).where(AuditEvent.event_type == event_type)
                )
            )
        finally:
            generator.close()

    def test_registration_audit_records_groups_and_provenance(self, client):
        source = _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["hr-team"],
        )
        _register(client, source["id"])
        (event,) = self._events(client, "document.registered")
        assert event.payload["access_groups"] == ["hr-team"]
        assert event.payload["confidentiality_level"] == "restricted"
        assert event.payload["confidentiality_source"] == "source_default"
        assert event.payload["access_groups_source"] == "source_default"
        assert event.payload["classification_source_id"] == source["id"]
        assert event.payload["confidentiality_floor_applied"] is False

    def test_a_silently_raised_level_is_flagged_in_the_audit_payload(self, client):
        source = _create_source(client, default_confidentiality_level="public")
        _register(client, source["id"])
        (event,) = self._events(client, "document.registered")
        assert event.payload["confidentiality_level"] == "internal"
        assert event.payload["confidentiality_floor_applied"] is True

    def test_source_creation_audit_records_the_configured_defaults(self, client):
        _create_source(
            client,
            default_confidentiality_level="restricted",
            default_access_groups=["hr-team"],
        )
        (event,) = self._events(client, "knowledge_source.created")
        assert event.payload["default_confidentiality_level"] == "restricted"
        assert event.payload["default_access_groups"] == ["hr-team"]

    def test_acl_patch_audit_keeps_the_pre_patch_provenance(self, client):
        source = _create_source(client, default_access_groups=["hr-team"])
        document = _register(client, source["id"]).json()
        client.patch(
            f"/api/v1/knowledge/documents/{document['id']}/acl",
            headers=_KM,
            json={
                "access_groups": ["department:HR"],
                "confidentiality_level": "restricted",
                "reason": "correction",
            },
        )
        (event,) = self._events(client, "document.acl_changed")
        assert event.payload["before"]["access_groups_source"] == "source_default"
        assert event.payload["before"]["classification_source_id"] == source["id"]
        assert event.payload["after"]["access_groups_source"] == "explicit"
        assert event.payload["after"]["classification_source_id"] is None


# =======================================================================================
# AC-05: the migration matches the model (tests build the schema with create_all, never
# Alembic, so nothing else in this suite would notice a divergence)
# =======================================================================================
class TestMigrationParity:
    REVISION = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0006_source_classification_defaults.py"
    )

    def test_revision_file_exists_and_chains_to_0005(self):
        text = self.REVISION.read_text(encoding="utf-8")
        assert 'revision: str = "0006_source_classification_defaults"' in text
        assert 'down_revision: str | None = "0005_document_has_been_indexed"' in text

    def test_every_new_model_column_is_added_and_dropped_by_the_revision(self):
        from app.domain.models import Document, KnowledgeSource

        text = self.REVISION.read_text(encoding="utf-8")
        upgrade_body, _, downgrade_body = text.partition("def downgrade()")
        new_columns = {
            "knowledge_sources": ("default_access_groups",),
            "documents": (
                "confidentiality_source",
                "access_groups_source",
                "classification_source_id",
            ),
        }
        for table, columns in new_columns.items():
            for column in columns:
                assert column in upgrade_body, f"{table}.{column} is not added by 0006"
                assert column in downgrade_body, f"{table}.{column} is not dropped by 0006"

        # ...and the model really declares them, so this test cannot pass vacuously.
        assert "default_access_groups" in KnowledgeSource.__table__.columns
        for column in new_columns["documents"]:
            assert column in Document.__table__.columns

    def test_the_revision_contains_no_backfill_that_invents_provenance(self):
        """AC-05. 'unknown' is the whole backfill: an UPDATE claiming otherwise is the failure
        mode this criterion exists to prevent."""
        text = self.REVISION.read_text(encoding="utf-8")
        assert "op.execute" not in text
        assert 'server_default=UNKNOWN_PROVENANCE' in text
        assert 'UNKNOWN_PROVENANCE = "unknown"' in text
