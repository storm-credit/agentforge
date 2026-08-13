"""Document classification resolution: source-level defaults, provenance, group shape.

WO-2026-08-13-SOURCE-ACL-DEFAULTS-001 (SEC-010, SEC-011).

WHY THIS MODULE EXISTS. In the planned pilot one administrator ingests on behalf of several
departments and retypes ``confidentiality_level`` / ``access_groups`` per document. Two
defects made that worse than tedious:

* ``KnowledgeSource.default_confidentiality_level`` existed on the model and in the create
  schema and was **read by nothing** -- ``register_document`` and ``upload_document_and_index``
  both took the caller's value directly. A designed governance feature was dead code.
* ``access_groups`` had **no validation at all**, so a mistyped group produced a document that
  was either silently invisible (availability failure) or scoped more broadly than intended
  (exposure failure), and nothing detected either: audit records the decision without
  evaluating it, and ``denied_count`` counts over-restriction only, never under-restriction.

This module is deliberately PURE (no DB, no HTTP, no request state) so the monotonicity
property below can be proved by a table-driven test over every combination rather than
argued in prose. It is classification RESOLUTION only; it does not touch ACL EVALUATION
(``app/domain/acl.py``), clearance ranking, or group semantics.

THE SECURITY CONTRACT (the security panel's conditions for accepting any classification
automation -- docs/10-architecture/ingestion-normalization-design.md section 4):

1. MONOTONIC TOWARD RESTRICTION. Inheritance may narrow groups and RAISE confidentiality; it
   may never widen or lower. Enforced two ways here: an inherited confidentiality level is
   clamped up to ``platform_fallback_confidentiality_level`` (never below it), and an
   unrecognised stored default resolves to the most restrictive known level rather than to
   the permissive fallback.
2. NEVER DERIVED FROM ARTIFACT-CONTROLLED INPUT. This function's inputs are the request's own
   explicit values and the administrator-configured source row. Filename, folder path, upload
   bytes and document content are NOT parameters and must never become parameters -- they are
   chosen by whoever produced the file, so deriving classification from them would make
   content an authorization input. That is the confused-deputy shape this codebase has already
   fixed three times (PR #66, #83, #92).
3. PROVENANCE IS RECORDED. Every resolution returns where each half of the classification came
   from, so the population affected by a wrong default is queryable as a set rather than
   discovered by accident.

THE PROPERTY THAT IS ACTUALLY PROVED (see tests/test_classification_defaults.py):

  Inheritance is EQUIVALENT TO THE ADMINISTRATOR HAVING TYPED THE SOURCE'S CONFIGURED VALUE
  ON THE DOCUMENT, raised to at least the platform confidentiality floor.

That is the strongest true statement, and it is what makes source defaults acceptable where
inference is not: the resulting classification contains nothing a privileged administrator
could not already have written by hand, and nothing influenced by the artifact.

HONEST LIMITATION -- the group rule below is a SHAPE rule, not a VOCABULARY rule. It rejects
mechanically detectable malformations (padding, control characters, commas, empty reserved
prefixes) but it CANNOT reject ``all-employes``: that is a well-shaped string for an
unintended audience. Rejecting it would require the authoritative group vocabulary, which
lives in SSO/AD and which this Work Order explicitly excludes creating locally (a local
master would reproduce the divergent-identity path removed in PR #135). The typo risk is
addressed here by REMOVING THE RETYPING (source defaults), not by validating the vocabulary.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.acl import CONFIDENTIALITY_RANK, confidentiality_rank

# --------------------------------------------------------------------------------------
# Provenance vocabulary (Document.confidentiality_source / Document.access_groups_source)
# --------------------------------------------------------------------------------------
#: The request expressed this value. No source default was consulted.
CLASSIFICATION_EXPLICIT = "explicit"
#: The request expressed nothing; the value was read from the knowledge source row.
CLASSIFICATION_SOURCE_DEFAULT = "source_default"
#: The request expressed nothing AND the source configured nothing; the platform's built-in
#: fallback for that endpoint applied. This is what every document got before this change.
CLASSIFICATION_PLATFORM_DEFAULT = "platform_default"
#: Provenance was never recorded. The value for rows that predate the 0006 migration and for
#: any Document constructed directly through the ORM (seed scripts). Deliberately NOT
#: back-filled to "explicit": the provenance of existing rows is genuinely unknown, and a
#: record that asserts something was chosen when nobody knows is worse than an honest gap.
CLASSIFICATION_UNKNOWN = "unknown"

CLASSIFICATION_SOURCES = frozenset(
    {
        CLASSIFICATION_EXPLICIT,
        CLASSIFICATION_SOURCE_DEFAULT,
        CLASSIFICATION_PLATFORM_DEFAULT,
        CLASSIFICATION_UNKNOWN,
    }
)

#: OBJECT-side most restrictive level, derived from the rank table so the two cannot drift.
MOST_RESTRICTIVE_CONFIDENTIALITY_LEVEL = max(CONFIDENTIALITY_RANK, key=CONFIDENTIALITY_RANK.get)

#: The confidentiality level an inherited value may never fall below. Both ingestion
#: endpoints already default an unspecified level to "internal", so clamping to it means a
#: source default can only ever RAISE the classification of a document that omits one.
INHERITED_CONFIDENTIALITY_FLOOR = "internal"

# --------------------------------------------------------------------------------------
# Access-group shape rule
# --------------------------------------------------------------------------------------
#: Bound on a single group string. Groups are stored in a JSON column so the database imposes
#: no limit; an unbounded group would ride into the vector-store payload and every audit row.
ACCESS_GROUP_MAX_LENGTH = 120

#: Prefixes that ``app.domain.acl.principal_acl_subjects`` GENERATES from the principal.
#: ``"department:"`` with an empty remainder would match a principal whose department claim is
#: empty, so a reserved prefix must carry a real value.
RESERVED_GROUP_PREFIXES = ("user:", "department:", "role:")

#: Groups are transported as a comma-delimited form field by POST /knowledge/documents/upload,
#: so a comma inside a group is unrepresentable and would silently split one group into two.
GROUP_DELIMITER = ","


def access_group_shape_error(group: object) -> str | None:
    """Return why ``group`` is not a well-shaped access-group string, or None if it is.

    THE STATED SHAPE RULE. A persisted access-group string must:

    1. be a string;
    2. carry no leading or trailing whitespace -- ACL matching is an exact set intersection
       (``principal_acl_subjects().intersection(document.access_groups)``), so ``"hr-team "``
       matches nothing and the document is silently invisible. Padding is REJECTED rather
       than stripped on purpose: silently normalising it would turn a previously
       unreadable document into a readable one, which is a widening;
    3. be non-empty;
    4. be at most ``ACCESS_GROUP_MAX_LENGTH`` characters;
    5. contain no ASCII control characters (tab, newline, NUL, DEL ...);
    6. contain no comma (see ``GROUP_DELIMITER``);
    7. if it starts with a reserved prefix, carry a non-empty, unpadded remainder.

    Case is significant and NOT normalised: real department names carry case
    (``department:Operations``), and lower-casing them would silently change which principals
    match. Non-ASCII is fully allowed -- ``department:인사팀`` is a legitimate group.
    """
    if not isinstance(group, str):
        return "must be a string"
    if group != group.strip():
        return "must not have leading or trailing whitespace"
    if not group:
        return "must not be empty"
    if len(group) > ACCESS_GROUP_MAX_LENGTH:
        return f"must be at most {ACCESS_GROUP_MAX_LENGTH} characters"
    if any(ord(char) < 32 or ord(char) == 127 for char in group):
        return "must not contain control characters"
    if GROUP_DELIMITER in group:
        return "must not contain a comma"
    for prefix in RESERVED_GROUP_PREFIXES:
        if group.startswith(prefix):
            remainder = group[len(prefix) :]
            if not remainder or remainder != remainder.strip():
                return f"reserved prefix {prefix!r} requires a non-empty, unpadded value"
    return None


def access_group_shape_errors(groups: Sequence[object]) -> list[tuple[object, str]]:
    """Every (group, reason) pair that fails the shape rule. Empty list means all valid.

    An empty ``groups`` sequence is VALID here: emptiness is an ACL question (an empty
    ``access_groups`` is deny-all, enforced by ``acl._acl_permits``), not a shape question,
    and the two endpoints differ on whether they accept it. Callers that require non-empty
    say so themselves (see ``update_document_acl``).
    """
    errors: list[tuple[object, str]] = []
    for group in groups:
        reason = access_group_shape_error(group)
        if reason is not None:
            errors.append((group, reason))
    return errors


# --------------------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ResolvedClassification:
    """The classification a new document will carry, plus where each half came from."""

    confidentiality_level: str
    access_groups: list[str]
    confidentiality_source: str
    access_groups_source: str
    #: The knowledge source whose configured defaults were applied, or None when nothing was
    #: inherited. A provenance SNAPSHOT, deliberately not a foreign key: it records what was
    #: applied at creation time and must stay readable as a plain value.
    classification_source_id: str | None
    #: True when an inherited level was raised to the platform floor (i.e. the source's
    #: configured default was LESS restrictive than the endpoint's own fallback). Audited, not
    #: stored: it is a property of one decision, not of the document.
    confidentiality_floor_applied: bool


def resolve_document_classification(
    *,
    requested_confidentiality_level: str | None,
    requested_access_groups: Sequence[str] | None,
    source_id: str,
    source_default_confidentiality_level: str,
    source_default_access_groups: Sequence[str],
    platform_fallback_confidentiality_level: str,
    platform_fallback_access_groups: Sequence[str],
) -> ResolvedClassification:
    """Resolve a new document's classification from the request and the source defaults.

    ``requested_*`` is None when the request expressed NO value for that half. The caller is
    responsible for that distinction, because it differs by transport:

    * ``POST /knowledge/documents`` (JSON): an absent or null field is None. An explicit
      ``[]`` is a value -- deny-all -- and is kept exactly, matching today's behaviour.
    * ``POST /knowledge/documents/upload`` (multipart form): an absent field is None, and so
      is a field that parses to zero groups (``""``, ``" "``, ``","``), because a blank
      form field expresses no intent. Today's code discards it too; the only change is
      WHICH fallback then applies, and the source's is never broader than the platform's.

    ``platform_fallback_*`` is the endpoint's CURRENT behaviour when nothing is specified, and
    it is passed in rather than hardcoded because the two ingestion endpoints genuinely differ
    (register falls back to no groups, upload to ``all-employees``). It is also the floor the
    inherited confidentiality level is clamped to.

    Guarantees, all proved in tests/test_classification_defaults.py:

    * An explicitly requested value is returned EXACTLY, with no source influence.
    * An inherited confidentiality level is normalised to a canonical known level and is never
      ranked below ``platform_fallback_confidentiality_level``.
    * An unrecognised stored source default fails CLOSED to the most restrictive known level.
    * A source that configures no defaults reproduces the endpoint's current behaviour
      byte-for-byte.
    """
    inherited_from_source = False

    # ---- confidentiality: explicit wins; otherwise inherit, normalise, clamp UP -------
    if requested_confidentiality_level is not None:
        confidentiality_level = requested_confidentiality_level
        confidentiality_source = CLASSIFICATION_EXPLICIT
        floor_applied = False
    else:
        # ``create_source`` validates its default case-insensitively but stores the caller's
        # raw casing, so normalise here. This also keeps an inherited value canonical, which
        # matters because acl.EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS is a case-SENSITIVE
        # membership test: an inherited "Confidential" would otherwise slip past the blanket
        # "confidential content never enters the index" rule.
        candidate = (source_default_confidentiality_level or "").strip().lower()
        if candidate not in CONFIDENTIALITY_RANK:
            # Fail closed. A stored default we cannot recognise (direct SQL, a future
            # migration, a seed script) must not fall through to the permissive fallback.
            candidate = MOST_RESTRICTIVE_CONFIDENTIALITY_LEVEL
        floor_applied = confidentiality_rank(candidate) < confidentiality_rank(
            platform_fallback_confidentiality_level
        )
        confidentiality_level = (
            platform_fallback_confidentiality_level if floor_applied else candidate
        )
        confidentiality_source = CLASSIFICATION_SOURCE_DEFAULT
        inherited_from_source = True

    # ---- access groups: explicit wins; then the source default; then the platform's ----
    if requested_access_groups is not None:
        # "keeps it exactly" (AC-01): stored verbatim, not de-duplicated and not stripped,
        # so an explicitly classified document behaves exactly as it does today.
        access_groups = list(requested_access_groups)
        access_groups_source = CLASSIFICATION_EXPLICIT
    elif source_default_access_groups:
        # An empty configured default means NOT CONFIGURED, not "inherit deny-all": a default
        # whose only effect is to make every document unreadable and unindexable is not a
        # governance setting, and treating it as one would give the register path a second,
        # indistinguishable way to produce a broken document.
        access_groups = _deduplicate(source_default_access_groups)
        access_groups_source = CLASSIFICATION_SOURCE_DEFAULT
        inherited_from_source = True
    else:
        access_groups = _deduplicate(platform_fallback_access_groups)
        access_groups_source = CLASSIFICATION_PLATFORM_DEFAULT

    return ResolvedClassification(
        confidentiality_level=confidentiality_level,
        access_groups=access_groups,
        confidentiality_source=confidentiality_source,
        access_groups_source=access_groups_source,
        classification_source_id=source_id if inherited_from_source else None,
        confidentiality_floor_applied=floor_applied,
    )


def _deduplicate(groups: Sequence[str]) -> list[str]:
    """Order-preserving de-duplication, applied only to values this module itself chose."""
    return list(dict.fromkeys(groups))
