from app.core.principal import Principal
from app.domain.vector import build_acl_filter
from app.infra.qdrant_store import build_qdrant_acl_filter, payload_allows


def _principal(clearance="internal", groups=("all-employees",), department="Finance"):
    return Principal(
        user_id="u1", department=department, roles=("employee",),
        groups=groups, clearance_level=clearance,
    )


def test_filter_has_status_clearance_and_group_conditions():
    acl = build_acl_filter(_principal())
    flt = build_qdrant_acl_filter(acl, knowledge_source_ids=("source-1",))
    keys = [c.key for c in flt.must]
    assert "status" in keys
    assert "confidentiality_rank" in keys
    assert "knowledge_source_id" in keys
    assert "access_groups" in keys


def test_payload_allows_matches_acl_semantics():
    acl = build_acl_filter(_principal())
    ok = {
        "status": "indexed", "confidentiality_rank": 1,
        "access_groups": ["all-employees"], "knowledge_source_id": "source-1",
    }
    assert payload_allows(ok, acl) is True

    # group mismatch -> deny
    assert payload_allows({**ok, "access_groups": ["department:HR"]}, acl) is False
    # empty groups -> deny-by-default
    assert payload_allows({**ok, "access_groups": []}, acl) is False
    # clearance too low -> deny
    assert payload_allows({**ok, "confidentiality_rank": 2}, acl) is False
    # not indexed -> deny
    assert payload_allows({**ok, "status": "registered"}, acl) is False
