"""Subject-side clearance resolution must fail CLOSED (WO-2026-08-13-CLEARANCE-FAIL-OPEN).

Context: ``confidentiality_rank`` resolves an unrecognised level to the HIGHEST rank.
That is correct for an OBJECT (an unclassified document is treated as maximally
sensitive) and inverted for a SUBJECT (an unrecognised clearance claim became maximum
clearance). ``principal_clearance_rank`` is the subject-side resolver and must resolve
unknown/empty/whitespace input to the LOWEST rank while preserving every well-formed
clearance, including padded and mixed-case spellings.

These tests are deliberately asymmetric: AC-03 pins the object side to the highest
rank so the two directions cannot silently drift back together.
"""

import importlib.util
from collections.abc import Iterator

import pytest

from app.core.principal import Principal
from app.domain.acl import (
    CONFIDENTIALITY_RANK,
    confidentiality_rank,
    principal_can_access_document,
    principal_clearance_rank,
)

RUNTIME_DEPS = ("fastapi", "pydantic_settings", "sqlalchemy")
_RUNTIME_AVAILABLE = all(importlib.util.find_spec(p) for p in RUNTIME_DEPS)

# Values a principal may supply that do NOT name a level in the vocabulary even after
# whitespace/case normalisation. Each must resolve to the lowest rank; none may widen access.
UNKNOWN_CLEARANCES = [
    "typo-xyz",  # unknown vocabulary term
    "",  # empty header
    "   ",  # whitespace only
    "\t",  # tab only
    "restricted-ish",  # near-miss on a real level
    "internal-plus",  # prefix of a real level plus a suffix
    "confidential ,internal",  # comma-injection attempt
    "конфиденциально",  # non-ASCII unknown term
]

# Values that DO name a level once normalised. Their rank must be preserved exactly:
# whitespace padding and casing must NOT cost a legitimate principal any access.
WELL_FORMED_CLEARANCES = [
    ("public", 0),
    ("internal", 1),
    ("restricted", 2),
    ("confidential", 3),
    ("INTERNAL", 1),
    ("Internal", 1),
    ("internal ", 1),
    (" internal", 1),
    ("  RESTRICTED  ", 2),
    ("internal\t", 1),
]


def _principal(clearance: str, *, groups=("all-employees",), roles=("employee",)) -> Principal:
    return Principal(
        user_id="u1",
        department="Finance",
        roles=roles,
        groups=groups,
        clearance_level=clearance,
    )


class _Doc:
    """Minimal stand-in for domain.models.Document for ACL evaluation."""

    def __init__(self, *, confidentiality_level: str, access_groups=("all-employees",)):
        self.id = "doc-1"
        self.status = "indexed"
        self.confidentiality_level = confidentiality_level
        self.access_groups = list(access_groups)


# --- AC-01: subject side fails closed -----------------------------------------------


@pytest.mark.parametrize("value", UNKNOWN_CLEARANCES)
def test_unknown_principal_clearance_resolves_to_lowest_rank(value):
    # Anything that does not normalise to a known level -> lowest rank, never highest.
    assert principal_clearance_rank(value) == min(CONFIDENTIALITY_RANK.values())
    assert principal_clearance_rank(value) != max(CONFIDENTIALITY_RANK.values())


def test_none_principal_clearance_resolves_to_lowest_rank():
    assert principal_clearance_rank(None) == min(CONFIDENTIALITY_RANK.values())


@pytest.mark.parametrize("value", UNKNOWN_CLEARANCES)
def test_malformed_clearance_cannot_read_above_public(value):
    principal = _principal(value)
    for level in ("internal", "restricted", "confidential"):
        assert principal_can_access_document(principal, _Doc(confidentiality_level=level)) is False
    # Public material stays reachable: failing closed lands at the lowest rank, not at deny-all.
    assert principal_can_access_document(principal, _Doc(confidentiality_level="public")) is True


# --- AC-02: no well-formed clearance loses access -----------------------------------


@pytest.mark.parametrize(("value", "expected"), WELL_FORMED_CLEARANCES)
def test_well_formed_clearance_keeps_its_rank(value, expected):
    assert principal_clearance_rank(value) == expected


@pytest.mark.parametrize(("value", "expected"), WELL_FORMED_CLEARANCES)
def test_well_formed_clearance_keeps_document_access(value, expected):
    principal = _principal(value)
    for level, level_rank in CONFIDENTIALITY_RANK.items():
        if level == "confidential":
            continue  # globally excluded regardless of clearance; asserted separately
        allowed = principal_can_access_document(principal, _Doc(confidentiality_level=level))
        assert allowed is (expected >= level_rank)


def test_confidential_documents_stay_globally_excluded():
    principal = _principal("confidential")
    doc = _Doc(confidentiality_level="confidential")
    assert principal_can_access_document(principal, doc) is False


# --- AC-03: object side is unchanged and still fails closed -------------------------


@pytest.mark.parametrize(
    "level",
    ["typo-xyz", "", "   ", "internal ", " internal", "secret", "конфиденциально"],
)
def test_unknown_document_level_still_resolves_to_highest_rank(level):
    # Object-side resolution is deliberately NOT symmetric with the subject side and is
    # deliberately NOT whitespace-normalised: object levels are validated on write, so an
    # unrecognised value means "unclassified", which must read as maximally sensitive.
    assert confidentiality_rank(level) == max(CONFIDENTIALITY_RANK.values())
    assert confidentiality_rank(level) == CONFIDENTIALITY_RANK["confidential"]


@pytest.mark.parametrize(("level", "expected"), sorted(CONFIDENTIALITY_RANK.items()))
def test_known_document_level_ranks_unchanged(level, expected):
    assert confidentiality_rank(level) == expected
    assert confidentiality_rank(level.upper()) == expected


def test_document_with_unknown_level_is_denied_to_internal_principal():
    principal = _principal("internal")
    assert principal_can_access_document(principal, _Doc(confidentiality_level="typo-xyz")) is False


# --- AC-04: vector path (Qdrant range filter + payload re-check) --------------------


@pytest.mark.skipif(not _RUNTIME_AVAILABLE, reason="Runtime dependencies are not installed")
@pytest.mark.parametrize("value", UNKNOWN_CLEARANCES)
def test_qdrant_range_filter_uses_lowest_rank_for_malformed_clearance(value):
    from app.domain.vector import build_acl_filter
    from app.infra.qdrant_store import build_qdrant_acl_filter

    acl = build_acl_filter(_principal(value))
    flt = build_qdrant_acl_filter(acl, knowledge_source_ids=())
    ranges = [c.range.lte for c in flt.must if c.key == "confidentiality_rank"]
    assert ranges == [min(CONFIDENTIALITY_RANK.values())]


@pytest.mark.skipif(not _RUNTIME_AVAILABLE, reason="Runtime dependencies are not installed")
@pytest.mark.parametrize(("value", "expected"), WELL_FORMED_CLEARANCES)
def test_qdrant_range_filter_preserves_well_formed_clearance(value, expected):
    from app.domain.vector import build_acl_filter
    from app.infra.qdrant_store import build_qdrant_acl_filter

    acl = build_acl_filter(_principal(value))
    flt = build_qdrant_acl_filter(acl, knowledge_source_ids=())
    ranges = [c.range.lte for c in flt.must if c.key == "confidentiality_rank"]
    assert ranges == [expected]


@pytest.mark.skipif(not _RUNTIME_AVAILABLE, reason="Runtime dependencies are not installed")
@pytest.mark.parametrize("value", UNKNOWN_CLEARANCES)
def test_payload_allows_denies_internal_chunk_for_malformed_clearance(value):
    from app.domain.vector import build_acl_filter
    from app.infra.qdrant_store import payload_allows

    acl = build_acl_filter(_principal(value))
    internal_chunk = {
        "status": "indexed",
        "confidentiality_rank": CONFIDENTIALITY_RANK["internal"],
        "access_groups": ["all-employees"],
    }
    assert payload_allows(internal_chunk, acl) is False
    public_chunk = {**internal_chunk, "confidentiality_rank": CONFIDENTIALITY_RANK["public"]}
    assert payload_allows(public_chunk, acl) is True


# --- AC-01/AC-04 at the HTTP boundary: the reproduced live defect --------------------


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
    Base.metadata.drop_all(bind=engine)


def _seed_corpus(client) -> dict[str, str]:
    """One public, one internal, one restricted document, all group-visible."""
    source = client.post(
        "/api/v1/knowledge/sources",
        headers={"X-Agent-Forge-User": "clearance-setup", "X-Agent-Forge-Roles": "knowledge-manager"},
        json={
            "name": "Clearance Corpus",
            "description": "Fixture for clearance fail-closed tests.",
            "owner_department": "Operations",
            "default_confidentiality_level": "public",
        },
    )
    assert source.status_code == 201
    source_id = source.json()["id"]

    ids: dict[str, str] = {}
    for level in ("public", "internal", "restricted"):
        response = client.post(
            "/api/v1/knowledge/documents",
            headers={
                "X-Agent-Forge-User": "seed-indexer",
                "X-Agent-Forge-Roles": "knowledge-manager",
            },
            json={
                "knowledge_source_id": source_id,
                "title": f"{level.title()} Handbook",
                "object_uri": f"object://synthetic/clearance/{level}.md",
                "checksum": f"sha256-clearance-{level}",
                "mime_type": "text/markdown",
                "confidentiality_level": level,
                "access_groups": ["all-employees"],
                "effective_date": "2026-05-10",
            },
        )
        assert response.status_code == 201, response.text
        ids[level] = response.json()["id"]
    return ids


def _list_document_ids(client, clearance: str) -> set[str]:
    response = client.get(
        "/api/v1/knowledge/documents",
        headers={
            "X-Agent-Forge-User": "alice",
            "X-Agent-Forge-Department": "Finance",
            "X-Agent-Forge-Roles": "employee",
            "X-Agent-Forge-Groups": "all-employees",
            "X-Agent-Forge-Clearance": clearance,
        },
    )
    assert response.status_code == 200
    return {d["id"] for d in response.json()}


@pytest.mark.skipif(not _RUNTIME_AVAILABLE, reason="Runtime dependencies are not installed")
@pytest.mark.parametrize("value", ["typo-xyz", "", "   ", "restricted-ish"])
def test_document_list_denies_above_public_for_malformed_clearance(client, value):
    # This is the reproduced live defect: identical user and groups, only the clearance
    # header varies. Before the fix these variants disclosed MORE than "internal".
    ids = _seed_corpus(client)
    visible = _list_document_ids(client, value)
    baseline = _list_document_ids(client, "internal")

    assert ids["public"] in visible
    assert ids["internal"] not in visible
    assert ids["restricted"] not in visible
    assert visible < baseline  # strictly less than the well-formed case


@pytest.mark.skipif(not _RUNTIME_AVAILABLE, reason="Runtime dependencies are not installed")
@pytest.mark.parametrize("value", ["internal", "internal ", " internal", "INTERNAL"])
def test_document_list_preserves_well_formed_internal_clearance(client, value):
    ids = _seed_corpus(client)
    visible = _list_document_ids(client, value)

    assert ids["public"] in visible
    assert ids["internal"] in visible
    assert ids["restricted"] not in visible


@pytest.mark.skipif(not _RUNTIME_AVAILABLE, reason="Runtime dependencies are not installed")
def test_source_list_clearance_filter_fails_closed(client):
    internal_source = client.post(
        "/api/v1/knowledge/sources",
        headers={"X-Agent-Forge-User": "clearance-setup", "X-Agent-Forge-Roles": "knowledge-manager"},
        json={
            "name": "Internal Source",
            "description": "Internal-default source.",
            "owner_department": "Operations",
            "default_confidentiality_level": "internal",
        },
    )
    assert internal_source.status_code == 201
    internal_id = internal_source.json()["id"]

    def source_ids(clearance: str) -> set[str]:
        response = client.get(
            "/api/v1/knowledge/sources",
            headers={
                "X-Agent-Forge-User": "alice",
                "X-Agent-Forge-Roles": "employee",
                "X-Agent-Forge-Clearance": clearance,
            },
        )
        assert response.status_code == 200
        return {s["id"] for s in response.json()}

    assert internal_id in source_ids("internal")
    assert internal_id in source_ids("internal ")  # well-formed once normalised
    assert internal_id not in source_ids("typo-xyz")
    assert internal_id not in source_ids("")
