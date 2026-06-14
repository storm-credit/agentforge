import importlib.util
from collections.abc import Iterator

import pytest

RUNTIME_DEPS = ("fastapi", "pydantic_settings", "sqlalchemy")
pytestmark = pytest.mark.skipif(
    not all(importlib.util.find_spec(p) for p in RUNTIME_DEPS),
    reason="Runtime dependencies are not installed",
)


def test_acl_update_schema_rejects_empty_groups():
    from pydantic import ValidationError

    from app.domain.schemas import DocumentAclUpdate

    with pytest.raises(ValidationError):
        DocumentAclUpdate(access_groups=[], confidentiality_level="internal", reason="x")


def test_acl_update_schema_requires_reason():
    from pydantic import ValidationError

    from app.domain.schemas import DocumentAclUpdate

    with pytest.raises(ValidationError):
        DocumentAclUpdate(
            access_groups=["all-employees"], confidentiality_level="internal", reason=""
        )


def test_acl_update_schema_accepts_valid():
    from app.domain.schemas import DocumentAclUpdate

    payload = DocumentAclUpdate(
        access_groups=["department:HR"], confidentiality_level="restricted", reason="reorg"
    )
    assert payload.access_groups == ["department:HR"]
    assert payload.confidentiality_level == "restricted"
