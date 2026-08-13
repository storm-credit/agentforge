import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.indexing import run_index_job
from app.domain.models import Document, DocumentChunk, IndexJob, KnowledgeSource
from app.domain.parsers import (
    DOCX_MIME_TYPE,
    MAX_EXTRACT_BYTES,
    PDF_MIME_TYPE,
    SUPPORTED_BINARY_MIME_TYPES,
    SUPPORTED_DOCUMENT_MIME_TYPES,
    SUPPORTED_TEXT_MIME_TYPES,
)
from app.domain.acl import (
    CONFIDENTIALITY_RANK,
    confidentiality_rank,
    principal_can_access_document,
    principal_can_discover_archived_document,
    principal_clearance_rank,
)
from app.domain.classification import (
    CLASSIFICATION_EXPLICIT,
    ResolvedClassification,
    access_group_shape_errors,
    resolve_document_classification,
)
from app.domain.vector import FakeVectorStore, VectorQuery, build_acl_filter, get_vector_store
from app.domain.schemas import (
    DocumentAclUpdate,
    DocumentCreate,
    DocumentChunkRead,
    DocumentRead,
    DocumentUploadRead,
    IndexJobCreate,
    IndexJobProcess,
    IndexJobRead,
    KnowledgeSourceCreate,
    KnowledgeSourceRead,
    RetrievalPreviewHit,
    RetrievalPreviewRequest,
    RetrievalPreviewResponse,
)
from app.infra.audit import write_audit_event
from app.infra.authz import PRIVILEGED_ROLES, enforce_roles
from app.infra.object_store import document_object_key, get_object_store

logger = logging.getLogger(__name__)

router = APIRouter()

# --------------------------------------------------------------------------------------
# PLATFORM CLASSIFICATION FALLBACKS -- the behaviour each ingestion endpoint had before
# source-level defaults existed (WO-2026-08-13-SOURCE-ACL-DEFAULTS). They are named
# constants, not literals buried in signatures, because they are the BASELINE the
# monotonicity proof is stated against: a source that configures no defaults must resolve to
# exactly these values, and an inherited confidentiality level may never rank below them.
#
# The two endpoints genuinely differ and are deliberately NOT unified here (that would change
# behaviour for a defaults-free source, which AC-02 forbids):
#   * register falls back to NO groups, which is deny-all and unindexable;
#   * upload falls back to ["all-employees"], which every principal holds unconditionally.
# Unifying them is a product decision about what an omitted ACL should mean, not a wiring one.
# --------------------------------------------------------------------------------------
_REGISTER_FALLBACK_CONFIDENTIALITY = "internal"
_REGISTER_FALLBACK_ACCESS_GROUPS: tuple[str, ...] = ()
_UPLOAD_FALLBACK_CONFIDENTIALITY = "internal"
_UPLOAD_FALLBACK_ACCESS_GROUPS: tuple[str, ...] = ("all-employees",)


@router.get("/sources", response_model=list[KnowledgeSourceRead])
def list_sources(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[KnowledgeSource]:
    sources = list(
        db.scalars(select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc()))
    )
    if "admin" not in principal.roles:
        # PARTIAL access control (NOT full ACL): KnowledgeSource has no per-source
        # access_groups/department ACL the way Document does -- only a
        # default_confidentiality_level. So this is a clearance-RANK filter ONLY: a non-admin
        # sees a source only when their clearance rank >= the source's default confidentiality
        # rank. It deliberately does NOT enforce group/department scoping for sources (none
        # exists in the schema); adding that requires a schema/migration change (out of scope).
        # Do not mistake this for document-style ACL enforcement.
        # Subject side: an unknown/malformed clearance resolves to the LOWEST rank.
        principal_rank = principal_clearance_rank(principal.clearance_level)
        sources = [
            s
            for s in sources
            if principal_rank >= confidentiality_rank(s.default_confidentiality_level)
        ]
    # Pagination is applied in PYTHON, after the clearance filter above -- deliberately
    # NOT as SQL LIMIT/OFFSET. A SQL-level window would be computed against the
    # unfiltered superset, so non-admin pages would shrink and skip unpredictably once
    # the filter ran. The tradeoff: the full filtered set is still materialized
    # server-side per request. Acceptable at this platform's internal data volumes;
    # revisit (push the filter into SQL first) if source counts grow large.
    return sources[offset : offset + limit]


@router.post("/sources", response_model=KnowledgeSourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: KnowledgeSourceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> KnowledgeSource:
    """Create a knowledge source. PRIVILEGED_ROLES only
    (WO-2026-08-13-MUTATION-GATE-SWEEP).

    A KnowledgeSource is the container every Document is registered into, and the caller
    chooses its ``default_confidentiality_level`` — the classification label the source is
    listed under (``list_sources`` filters non-admins by clearance rank against exactly this
    value). Every sibling mutation in this file (register / upload / archive / restore / ACL
    patch) is gated on PRIVILEGED_ROLES; this one had no ``enforce_roles`` call at all, so any
    principal — including the header-stub DEFAULT ``developer`` identity, i.e. a caller that
    sends no identity headers whatsoever — could create a source and pick its label.

    Consequence, deliberately accepted: self-service source creation is now a
    knowledge-manager action, matching ``register_document``. This removes no *usable*
    capability for a non-privileged caller — registering or uploading a document into the
    source it just created has been PRIVILEGED_ROLES-only since
    WO-2026-08-12-UPLOAD-ROLE-GATE, so the only thing an unprivileged creator could do with
    the source was leave an empty, mislabelled row in the catalog.

    Not fixed here (out of this Work Order's scope): a source carries no per-source ACL, only
    this default label, so ``GET /sources`` remains a clearance-rank filter and never a
    group/department check. See ``list_sources``.
    """
    # AUTHORIZE FIRST -- before validation and before any write, matching
    # register_document / upload_document_and_index. Nothing about this decision depends on
    # the body being valid, and an unauthorized caller should not be able to distinguish a
    # rejected classification label (422) from a rejected identity (403).
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="knowledge_source.create", target_type="knowledge_source",
    )

    _validate_confidentiality(payload.default_confidentiality_level)
    # WO-2026-08-13-SOURCE-ACL-DEFAULTS: the source's configured group default is the value
    # every document that omits its own groups will INHERIT, so a malformed group typed here
    # propagates to a whole department's documents. Validate it at the point of entry, not
    # only where it is consumed.
    _validate_access_groups(payload.default_access_groups, field="default_access_groups")
    source = KnowledgeSource(**payload.model_dump())
    db.add(source)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="knowledge_source.created",
        target_type="knowledge_source",
        target_id=source.id,
        payload={
            "name": source.name,
            "owner_department": source.owner_department,
            # The governance defaults chosen here are an authorization-relevant decision:
            # record them so a later "which sources hand out this group" question is
            # answerable from the audit trail and not only from current table state.
            "default_confidentiality_level": source.default_confidentiality_level,
            "default_access_groups": list(source.default_access_groups),
        },
    )
    db.commit()
    db.refresh(source)
    return source


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[Document]:
    # RULE (WO-2026-08-13-ROLE-READ-COHERENCE): this endpoint mixes TWO different
    # authorization questions that used to share one literal "admin" check. They are
    # deliberately kept separate, and only the first was reconciled with mutation rights.
    #
    #   (a) DISCOVERY of archived rows (include_archived) -- scoped to PRIVILEGED_ROLES,
    #       because restore is. It is the lookup step of a mutation these roles already
    #       hold; a permission whose target cannot be found is not a permission.
    #   (b) The general ACL BYPASS ("see every document regardless of authorization") --
    #       still literally "admin", unchanged. Widening this to PRIVILEGED_ROLES would
    #       hand knowledge-manager blanket read of every document's metadata, which no
    #       mutation right implies. Do not fold (b) back into (a).
    is_admin = "admin" in principal.roles
    # Restore (POST /documents/{id}/restore) is gated on PRIVILEGED_ROLES, so archived-row
    # discovery is too -- see (a). Admin is a member of PRIVILEGED_ROLES, so this covers it.
    may_restore = bool(PRIVILEGED_ROLES.intersection(principal.roles))
    show_archived = include_archived and may_restore
    statement = select(Document).order_by(Document.created_at.desc())
    # For callers without the restore right the flag is silently ignored (NOT 403),
    # matching this file's convention that GET list endpoints scope results quietly (ACL
    # filter below, list_sources' clearance filter) rather than reject the request; 403
    # here is reserved for per-resource reads and enforce_roles-gated mutations.
    if not show_archived:
        statement = statement.where(Document.status != "archived")
    documents = list(db.scalars(statement))
    if not is_admin:
        # Non-admins only see document metadata they're authorized to access -- (b) above.
        # The archived branch does NOT relax that: principal_can_discover_archived_document
        # runs the identical ACL body (clearance + groups + confidential exclusion) and only
        # lifts the lifecycle-status gate, so a privileged role sees archived rows strictly
        # inside its own ACL scope and nothing more.
        documents = [
            d
            for d in documents
            if principal_can_access_document(principal, d)
            or (show_archived and principal_can_discover_archived_document(principal, d))
        ]
    # Pagination is applied in PYTHON, after the ACL filter above -- deliberately NOT
    # as SQL LIMIT/OFFSET. A SQL-level window would be computed against the unfiltered
    # superset: a non-admin's page would then be filtered down further, producing
    # short pages, skipped items, and unreachable results. The tradeoff: the full
    # ACL-filtered set is still materialized server-side per request. Acceptable at
    # this platform's internal data volumes; revisit (push the ACL into SQL first)
    # if document counts grow large.
    return documents[offset : offset + limit]


@router.delete("/documents/{document_id}", response_model=DocumentRead)
def archive_document(
    document_id: str,
    reason: str = Query(default="archived via API"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    """Soft-delete a document: mark archived (excluded from search/list) and purge its
    vectors from the store. Admin-gated; audited. Fail-closed: vector purge runs inside
    the request transaction before commit."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # KNOWN UNCLOSED GAP (reported by WO-2026-08-13-MUTATION-GATE-SWEEP, deliberately not
    # fixed there): the role check below is the ONLY check -- the target document's own ACL is
    # not consulted, so a privileged role can archive a document outside its ACL scope if it
    # obtains the id by other means (list_documents will not show it). Closing this SHRINKS
    # what knowledge-manager/platform-admin can do, which is a product decision. See
    # docs/10-architecture/roles-and-permissions.md section 10. Same for restore_document and
    # update_document_acl.
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.archive", target_type="document", target_id=document_id,
    )

    document.status = "archived"
    for chunk in document.chunks:
        chunk.status = "archived"
    db.flush()
    get_vector_store().delete_document(document.id)

    write_audit_event(
        db,
        principal=principal,
        event_type="document.archived",
        target_type="document",
        target_id=document.id,
        reason=reason,
        payload={"knowledge_source_id": document.knowledge_source_id, "title": document.title},
    )
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents/{document_id}/restore", response_model=DocumentRead)
def restore_document(
    document_id: str,
    reason: str = Query(default="restored via API"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    """Restore (unarchive) a soft-deleted document so it reappears in listings and
    ACL-scoped reads. Admin-gated; audited. 409 if the document is not currently
    archived.

    The document goes back to ``registered`` (not ``indexed``): that is the codebase's
    pre-index state — it is in ``SEARCHABLE_DOCUMENT_STATUSES`` (visible to authorized
    non-admins) and passes ``document_can_be_indexed`` so it can be re-indexed. Chunks
    become ``active``: visible in chunk listings, but excluded from retrieval (which
    requires ``indexed``) because their vectors are gone.

    Honest limitation: archiving purged this document's vectors from the store, and
    restore deliberately does NOT re-populate them (no vector-store side effect here,
    so there is nothing to fail-close around, unlike archive). The restored document is
    visible/listed again but not retrievable until a fresh index job runs
    (``POST /documents/{id}/index-jobs`` with ``force_reindex: true`` + ``/process``).
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # KNOWN UNCLOSED GAP: role-only check, target document's ACL not consulted -- see
    # archive_document and docs/10-architecture/roles-and-permissions.md section 10.
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.restore", target_type="document", target_id=document_id,
    )

    if document.status != "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Document is not archived"
        )

    document.status = "registered"
    for chunk in document.chunks:
        # "active" (not "indexed"): the chunk rows are visible again, but their vectors
        # were purged at archive time, so they must not be treated as searchable.
        chunk.status = "active"
    db.flush()

    write_audit_event(
        db,
        principal=principal,
        event_type="document.restored",
        target_type="document",
        target_id=document.id,
        reason=reason,
        payload={"knowledge_source_id": document.knowledge_source_id, "title": document.title},
    )
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def register_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    """Register a document's metadata. PRIVILEGED_ROLES only (WO-2026-08-12-UPLOAD-ROLE-GATE).

    Creating a Document is the entry point of the knowledge-ingestion trust boundary: the
    caller chooses the ``confidentiality_level`` and ``access_groups`` the content will be
    served under, and (via ``POST /documents/{id}/index-jobs``) what text lands in the
    active index. Every other mutating knowledge endpoint (archive / restore / ACL patch)
    is already gated on PRIVILEGED_ROLES; this one was not, so any principal could plant an
    ``all-employees``-readable document. Identity is still a header stub (ADR-103 open), so
    "any principal" meant anyone who could reach the API.

    Consequence, accepted by the product owner on 2026-08-12: self-service departmental
    upload no longer works. Ingestion is a knowledge-manager action.

    This does NOT mitigate prompt injection. It shrinks the attacker set from "anyone
    reaching the API" to "holders of a privileged role"; a privileged uploader can still
    ingest a poisoned document, and a document that merely quotes an injection example
    contaminates the index exactly as before.
    """
    # AUTHORIZE FIRST -- before the knowledge-source lookup, before validation, before any
    # write. Nothing about this decision depends on the request body being valid or the
    # source existing, so there is no reason to touch the database first (and gating after
    # the 404 lookup would leak knowledge-source existence to unauthorized callers).
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.register",
        target_type="knowledge_source",
        # Caller-supplied and unbounded (DocumentCreate.knowledge_source_id has no
        # max_length); audit_events.target_id is String(120), so clamp rather than let an
        # oversized id turn a clean 403 into a write error on a length-checking backend.
        target_id=payload.knowledge_source_id[:120],
    )

    source = db.get(KnowledgeSource, payload.knowledge_source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")
    if payload.confidentiality_level is not None:
        _validate_confidentiality(payload.confidentiality_level)

    # Source-default inheritance (WO-2026-08-13-SOURCE-ACL-DEFAULTS). The platform fallbacks
    # passed here are THIS endpoint's current behaviour for an unspecified value -- "internal"
    # and no groups -- so a source that configures no defaults resolves to exactly what it
    # resolved to before. Nothing about the artifact (title, object_uri, mime_type, checksum,
    # bytes) is passed in: classification must never be derived from content the uploader
    # controls. See domain/classification.py.
    resolved = resolve_document_classification(
        requested_confidentiality_level=payload.confidentiality_level,
        requested_access_groups=payload.access_groups,
        source_id=source.id,
        source_default_confidentiality_level=source.default_confidentiality_level,
        source_default_access_groups=source.default_access_groups,
        platform_fallback_confidentiality_level=_REGISTER_FALLBACK_CONFIDENTIALITY,
        platform_fallback_access_groups=_REGISTER_FALLBACK_ACCESS_GROUPS,
    )
    _validate_access_groups(resolved.access_groups)

    document = Document(
        knowledge_source_id=payload.knowledge_source_id,
        title=payload.title,
        object_uri=payload.object_uri,
        checksum=payload.checksum,
        mime_type=payload.mime_type,
        confidentiality_level=resolved.confidentiality_level,
        access_groups=resolved.access_groups,
        status=payload.status,
        effective_date=payload.effective_date,
        confidentiality_source=resolved.confidentiality_source,
        access_groups_source=resolved.access_groups_source,
        classification_source_id=resolved.classification_source_id,
    )
    db.add(document)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="document.registered",
        target_type="document",
        target_id=document.id,
        payload=_classification_audit_payload(document, resolved),
    )
    db.commit()
    db.refresh(document)
    return document


@router.patch("/documents/{document_id}/acl", response_model=DocumentRead)
def update_document_acl(
    document_id: str,
    payload: DocumentAclUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # KNOWN UNCLOSED GAP: role-only check, target document's ACL not consulted -- see
    # archive_document and docs/10-architecture/roles-and-permissions.md section 10. This is
    # the sharpest of the three: it RELABELS a document the caller may have no access to.
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.acl_update", target_type="document", target_id=document_id,
    )

    if payload.confidentiality_level.lower() not in CONFIDENTIALITY_RANK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown confidentiality_level",
        )

    before = {
        "access_groups": list(document.access_groups),
        "confidentiality_level": document.confidentiality_level,
        # Provenance before the relabel, so the audit trail keeps the fact that this document
        # once carried an inherited classification even though the columns stop saying so.
        "confidentiality_source": document.confidentiality_source,
        "access_groups_source": document.access_groups_source,
        "classification_source_id": document.classification_source_id,
    }
    new_groups = list(dict.fromkeys(g.strip() for g in payload.access_groups if g.strip()))
    if not new_groups:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="access_groups must not be empty",
        )
    # Shape rule applied to the values about to be PERSISTED -- this endpoint has always
    # stripped and de-duplicated its input, and that pre-existing normalisation is preserved
    # (changing it is not this Work Order's business), so what is validated here is the
    # normalised result. Same rule, same point of application, on every write path.
    _validate_access_groups(new_groups)

    document.access_groups = new_groups
    document.confidentiality_level = payload.confidentiality_level.lower()
    # A manual relabel makes the classification EXPLICIT: it is no longer whatever a source
    # default handed out. Leaving stale "source_default" provenance here would poison the one
    # query this feature exists to support -- "which documents did the broken default touch"
    # would keep returning documents an administrator has already corrected.
    document.confidentiality_source = CLASSIFICATION_EXPLICIT
    document.access_groups_source = CLASSIFICATION_EXPLICIT
    document.classification_source_id = None
    rank = confidentiality_rank(document.confidentiality_level)

    for chunk in document.chunks:
        snapshot = dict(chunk.acl_snapshot or {})
        snapshot["access_groups"] = new_groups
        snapshot["confidentiality_level"] = document.confidentiality_level
        chunk.acl_snapshot = snapshot

    db.flush()
    # Fail-closed: if Qdrant sync raises, the whole request rolls back.
    chunks_synced = get_vector_store().set_document_acl(
        document.id, access_groups=tuple(new_groups), confidentiality_rank=rank
    )

    write_audit_event(
        db,
        principal=principal,
        event_type="document.acl_changed",
        target_type="document",
        target_id=document.id,
        reason=payload.reason,
        payload={
            "before": before,
            "after": {
                "access_groups": new_groups,
                "confidentiality_level": document.confidentiality_level,
                "confidentiality_source": document.confidentiality_source,
                "access_groups_source": document.access_groups_source,
                "classification_source_id": document.classification_source_id,
            },
            "chunks_synced": chunks_synced,
        },
    )
    db.commit()
    db.refresh(document)
    return document


@router.post(
    "/documents/upload",
    response_model=DocumentUploadRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_document_and_index(
    knowledge_source_id: str = Form(...),
    title: str = Form(...),
    # Default None, NOT the previous literal "internal" / "all-employees": those literals made
    # an omitted field indistinguishable from a deliberate one, so the source's configured
    # default could never be consulted (WO-2026-08-13-SOURCE-ACL-DEFAULTS). The literals now
    # live in _UPLOAD_FALLBACK_* and are applied by the resolver when the source configures
    # nothing, so an omitting caller under a defaults-free source gets the identical result.
    confidentiality_level: str | None = Form(None),
    access_groups: str | None = Form(None),
    effective_date: str | None = Form(None),
    embedding_model: str = Form("bge-m3"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> dict[str, Document | IndexJob]:
    """Upload a file, register it, and index it inline. PRIVILEGED_ROLES only
    (WO-2026-08-12-UPLOAD-ROLE-GATE).

    This is the strongest ingestion path in the API: one request creates the Document with
    caller-chosen ``confidentiality_level``/``access_groups``, optionally persists the raw
    bytes to the object store, creates the IndexJob, and runs it INLINE -- parse, chunk,
    embed and vector upsert all complete before the response. See ``register_document``
    for the rationale, the accepted self-service consequence, and the explicit statement
    that this does not mitigate prompt injection.
    """
    # AUTHORIZE FIRST -- before the knowledge-source lookup, before the upload bytes are
    # read, and therefore before every side effect this endpoint can have: the Document
    # row, the object-store put, the IndexJob row, the chunk rows, and the vector upsert.
    #
    # Honest limitation of "before": Starlette parses the multipart body into a spooled
    # temp file before this function's first statement runs (that is how FastAPI binds
    # File/Form parameters), so a denied request still costs one body parse. No
    # application-owned state is created, and nothing reaches the vector store or the
    # object store.
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.upload",
        target_type="knowledge_source",
        # Form field, unbounded; audit_events.target_id is String(120) -- see
        # register_document for why this is clamped.
        target_id=knowledge_source_id[:120],
    )

    source = db.get(KnowledgeSource, knowledge_source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")

    filename = _safe_upload_filename(file.filename)
    raw = file.file.read()
    if len(raw) > MAX_EXTRACT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    mime_type = _upload_mime_type(file.content_type, filename)
    if mime_type not in SUPPORTED_DOCUMENT_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    if confidentiality_level is not None:
        _validate_confidentiality(confidentiality_level)

    # Source-default inheritance, same resolver and same rules as register_document. The
    # fallbacks passed here are THIS endpoint's own pre-existing defaults, which differ from
    # register's (upload has always fallen back to "all-employees"), so both endpoints keep
    # behaving exactly as they do today whenever the source configures nothing.
    resolved = resolve_document_classification(
        requested_confidentiality_level=confidentiality_level,
        requested_access_groups=_requested_upload_access_groups(access_groups),
        source_id=source.id,
        source_default_confidentiality_level=source.default_confidentiality_level,
        source_default_access_groups=source.default_access_groups,
        platform_fallback_confidentiality_level=_UPLOAD_FALLBACK_CONFIDENTIALITY,
        platform_fallback_access_groups=_UPLOAD_FALLBACK_ACCESS_GROUPS,
    )
    _validate_access_groups(resolved.access_groups)

    document = Document(
        knowledge_source_id=source.id,
        title=title.strip() or Path(filename).stem or filename,
        object_uri=f"upload://{filename}",
        checksum="sha256-" + hashlib.sha256(raw).hexdigest(),
        mime_type=mime_type,
        confidentiality_level=resolved.confidentiality_level,
        access_groups=resolved.access_groups,
        status="registered",
        effective_date=effective_date,
        confidentiality_source=resolved.confidentiality_source,
        access_groups_source=resolved.access_groups_source,
        classification_source_id=resolved.classification_source_id,
    )
    db.add(document)
    db.flush()
    # Persist the original bytes to object storage (AF-009) when enabled, so the
    # document can be re-indexed later without re-uploading. No-op when disabled.
    object_store = get_object_store()
    if object_store is not None:
        object_store.put(document_object_key(document.id), raw)
    write_audit_event(
        db,
        principal=principal,
        event_type="document.registered",
        target_type="document",
        target_id=document.id,
        payload={
            **_classification_audit_payload(document, resolved),
            "upload_mime_type": document.mime_type,
        },
    )

    job = IndexJob(
        document_id=document.id,
        status="queued",
        stage="parse",
        config={
            "parser_profile": "upload-extract-text",
            "chunking": {"strategy": "line-heading", "chunk_size": 900, "chunk_overlap": 0},
            "embedding_model": embedding_model,
            "force_reindex": False,
            "source": "uploaded_file",
            "original_mime_type": mime_type,
            "original_filename": filename,
        },
        created_by=principal.user_id,
    )
    db.add(job)
    db.flush()

    run_index_job(
        db=db,
        document=document,
        job=job,
        principal=principal,
        source_text=_decode_uploaded_text(raw) if mime_type in SUPPORTED_TEXT_MIME_TYPES else None,
        source_bytes=raw if mime_type in SUPPORTED_BINARY_MIME_TYPES else None,
    )

    db.commit()
    db.refresh(document)
    db.refresh(job)
    return {"document": document, "index_job": job}


@router.post(
    "/documents/{document_id}/index-jobs",
    response_model=IndexJobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_index_job(
    document_id: str,
    payload: IndexJobCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> IndexJob:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # AUTHZ-DECISION: acl-gated -- the baseline bar is the target document's read ACL (below),
    # with a SECOND role bar for re-indexing (has_been_indexed). Recorded here so the mixed
    # gate is not mistaken for an oversight.
    # KNOWN UNCLOSED GAP: WO-2026-08-13-FIRST-INDEX-GATE (draft, awaiting a product decision).
    # While has_been_indexed is False, a merely READ-authorized principal may supply
    # source_text and have it embedded under this document's confidentiality/ACL tag. Closing
    # it removes self-service first-index, so it is not decided here. See
    # docs/10-architecture/roles-and-permissions.md section 10.
    # Authorize BEFORE any side effect. Indexing content into a document you cannot even
    # read is nonsensical and, with a caller-supplied source_text + force_reindex, purges
    # the document's real vectors and re-embeds attacker text under the document's UNCHANGED
    # confidentiality/ACL tag -- content poisoning served to legitimately-authorized users.
    # Read-ACL gate (matches sibling get_index_job / list_document_chunks in this file).
    if "admin" not in principal.roles and not principal_can_access_document(principal, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this document"
        )

    # Two-tier authorization for the destructive re-embed. The read-ACL gate above is the
    # BASELINE bar (matches the sibling read endpoints). This adds a SECOND, higher bar for
    # the one dangerous case:
    #   * FIRST-TIME indexing -- the document has never successfully held trusted content
    #     (has_been_indexed is False) -- stays at the read-ACL bar. There are no real
    #     vectors to poison, so self-service ingest by any read-authorized principal is
    #     intended. This INCLUDES retrying a first-ever index that failed (status
    #     'index_failed' but has_been_indexed still False): nothing trusted ever existed.
    #   * RE-INDEXING a document that HAS previously held trusted content is a
    #     PRIVILEGED_ROLES-only mutation (same bar as archive_document / restore_document /
    #     update_document_acl below). run_index_job purges the document's real vectors
    #     (store.delete_document) and re-embeds caller-supplied text under the document's
    #     UNCHANGED confidentiality/ACL tag, so an authorized-but-untrusted CO-READER could
    #     otherwise serve fabricated content to every other legitimate reader as a trusted
    #     citation.
    #     NOTE: that purge in run_index_job (indexing.py) is UNCONDITIONAL on the success
    #     path -- it is NOT gated on force_reindex (force_reindex only additionally drops
    #     the stale DB chunk rows). So gating force_reindex alone would leave the identical
    #     exploit open via a plain source_text re-index.
    # The bar keys on the DURABLE has_been_indexed flag, NOT the volatile status. An earlier
    # fix keyed on status == 'indexed', but run_index_job purges vectors unconditionally and
    # then, on any parse/upsert failure, flips a previously-'indexed' document to
    # 'index_failed'. A status-only gate silently stops applying in that state, reopening the
    # co-reader poisoning via an operational-failure side door. has_been_indexed is set once
    # on first success and never reset, so the privileged bar sticks. Third fix in this
    # trust-boundary family: PR #66 (unauthorized reader), PR #83 (authorized-but-untrusted
    # co-reader vs status=='indexed'), and this (the index_failed side door).
    if document.has_been_indexed:
        enforce_roles(
            db, principal, PRIVILEGED_ROLES,
            action="document.reindex", target_type="document", target_id=document.id,
        )

    job = IndexJob(
        document_id=document.id,
        status="queued",
        stage="parse",
        config=_index_job_config(payload),
        created_by=principal.user_id,
    )
    db.add(job)
    db.flush()

    if payload.source_text is None:
        write_audit_event(
            db,
            principal=principal,
            event_type="index_job.queued",
            target_type="index_job",
            target_id=job.id,
            payload={
                "document_id": document.id,
                "parser_profile": payload.parser_profile,
                "embedding_model": payload.embedding_model,
            },
        )
    else:
        run_index_job(
            db=db,
            document=document,
            job=job,
            source_text=payload.source_text,
            principal=principal,
        )

    db.commit()
    db.refresh(job)
    return job


@router.post("/index-jobs/{job_id}/process", response_model=IndexJobRead)
def process_index_job(
    job_id: str,
    payload: IndexJobProcess,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> IndexJob:
    """Worker stub: drive a queued index job through the pipeline.

    Real deployments will fetch the document body from object storage (AF-009).
    Until then a queued job is processed with the synthetic ``source_text`` provided
    here; if no content is available the job fails closed.
    """
    job = db.get(IndexJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    if job.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Index job is not queued"
        )

    document = db.get(Document, job.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # AUTHZ-DECISION: acl-gated -- same two-tier shape as create_index_job: the target
    # document's read ACL is the baseline bar, plus a role bar for re-indexing.
    # KNOWN UNCLOSED GAP: WO-2026-08-13-FIRST-INDEX-GATE (draft, awaiting a product decision)
    # -- the first-index path accepts caller-supplied source_text with read access only. Not
    # decided here. See docs/10-architecture/roles-and-permissions.md section 10.
    # Authorize BEFORE the document is touched: processing drives run_index_job, which can
    # purge + re-embed the document's vectors. Same read-ACL gate as create_index_job /
    # the sibling read endpoints; return 403 to stay consistent with get_index_job.
    if "admin" not in principal.roles and not principal_can_access_document(principal, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this index job"
        )

    # Two-tier authorization (see create_index_job for the full rationale). Processing a
    # queued job whose target document HAS previously held trusted content (has_been_indexed)
    # is a RE-INDEX, so it requires PRIVILEGED_ROLES on top of the read-ACL gate above.
    # run_index_job purges the real vectors (unconditional store.delete_document) and
    # re-embeds; even the fail-closed no-content branch below flips a previously-indexed
    # document to 'index_failed' (dropping it from search). The bar keys on the DURABLE
    # has_been_indexed flag rather than status == 'indexed': a status-only gate would stop
    # applying once a prior reindex failure dropped the document to 'index_failed' with its
    # vectors already purged, reopening the co-reader poisoning via that side door.
    # First-time processing (has_been_indexed still False, including retrying a first-ever
    # index that failed) stays at the read-ACL bar so normal self-service ingest keeps
    # working.
    if document.has_been_indexed:
        enforce_roles(
            db, principal, PRIVILEGED_ROLES,
            action="document.reindex", target_type="document", target_id=document.id,
        )

    source_text = payload.source_text
    source_bytes: bytes | None = None
    if source_text is None:
        raw = _fetch_object_bytes(document)
        if raw is not None:
            if document.mime_type in SUPPORTED_BINARY_MIME_TYPES:
                source_bytes = raw
            else:
                source_text = _decode_uploaded_text(raw)

    if source_text is None and source_bytes is None:
        job.started_at = datetime.now(UTC)
        job.status = "failed"
        job.stage = "parse"
        job.error_code = "SOURCE_CONTENT_UNAVAILABLE"
        job.error_message = (
            "No document content is available to index and none is stored in object storage."
        )
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db,
            principal=principal,
            event_type="document.index_failed",
            target_type="document",
            target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
        )
    else:
        run_index_job(
            db=db,
            document=document,
            job=job,
            source_text=source_text,
            source_bytes=source_bytes,
            principal=principal,
        )

    db.commit()
    db.refresh(job)
    return job


@router.get("/index-jobs/{job_id}", response_model=IndexJobRead)
def get_index_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> IndexJob:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    document = db.get(Document, job.document_id)
    if "admin" not in principal.roles and not (
        document is not None and principal_can_access_document(principal, document)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this index job"
        )
    return job


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[DocumentChunk]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if "admin" not in principal.roles and not principal_can_access_document(principal, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this document"
        )

    return list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.status != "archived")
            .order_by(DocumentChunk.chunk_index)
        )
    )


@router.post("/retrieval/preview", response_model=RetrievalPreviewResponse)
def preview_retrieval(
    payload: RetrievalPreviewRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> RetrievalPreviewResponse:
    # AUTHZ-DECISION: deliberately-open -- this is a READ in POST clothing. It is POST only
    # because the query text and the knowledge_source_ids list belong in a body, not a URL;
    # it creates no domain state. Authorization is the caller's own ACL, applied by
    # build_acl_filter(principal) and enforced inside the vector store exactly as a real run
    # does, so a caller can only preview chunks it is already authorized to retrieve (the
    # FakeVectorStore fallback enforces the same filter, so the degraded path is not a hole).
    # Its only persistent effect is one retrieval.previewed audit event attributed to the
    # caller, i.e. it makes the attempt MORE accountable, not less. Role-gating it would
    # remove the ability of an ordinary user to see why an agent answered as it did, without
    # protecting anything the caller cannot already retrieve through POST /runs.
    statement = (
        select(Document)
        .options(selectinload(Document.chunks))
        .order_by(Document.created_at.desc())
    )
    documents = list(db.scalars(statement))
    # Preview must exercise the SAME retrieval path as real runs (get_vector_store()
    # + retrieval_min_score), or a Qdrant deployment previews different results than
    # production answers. Mirrors runs.py's _search_authorized_context: configured
    # store first, FakeVectorStore fallback on error so preview stays available
    # (ACL-safe — the fake enforces the same ACL filter) in degraded mode. In
    # hermetic tests/CI no backend is configured, so this still resolves to the fake.
    # (The rerank hook is a run-pipeline stage, not part of the store; preview shows
    # raw store retrieval, as before.)
    query = VectorQuery(
        query_text=payload.query,
        knowledge_source_ids=tuple(payload.knowledge_source_ids),
        top_k=payload.top_k,
        min_score=get_settings().retrieval_min_score,
    )
    acl_filter = build_acl_filter(principal)
    store = get_vector_store()
    vector_adapter = "fake" if isinstance(store, FakeVectorStore) else "qdrant"
    try:
        vector_result = store.search(query=query, documents=documents, acl_filter=acl_filter)
    except Exception as exc:  # noqa: BLE001 - stay available, ACL-safe, but mark degraded
        logger.warning(
            "retrieval preview vector search failed (%s); falling back to FakeVectorStore", exc
        )
        vector_result = FakeVectorStore().search(
            query=query, documents=documents, acl_filter=acl_filter
        )
        vector_adapter = "fake_fallback"
    hits = [
        RetrievalPreviewHit(
            document_id=hit.document_id,
            knowledge_source_id=hit.knowledge_source_id,
            chunk_id=hit.chunk_id,
            title=hit.title,
            confidentiality_level=hit.confidentiality_level,
            access_groups=list(hit.access_groups),
            score=hit.score,
            citation=hit.citation,
            citation_locator=hit.citation_locator,
        )
        for hit in vector_result.hits
    ]

    write_audit_event(
        db,
        principal=principal,
        event_type="retrieval.previewed",
        target_type="retrieval_preview",
        target_id="synthetic",
        payload={
            "query_length": len(payload.query),
            "knowledge_source_count": len(payload.knowledge_source_ids),
            "result_count": len(hits),
            "denied_count": vector_result.denied_count,
            "vector_adapter": vector_adapter,
        },
    )
    db.commit()

    return RetrievalPreviewResponse(
        query=payload.query,
        hits=hits,
        denied_count=vector_result.denied_count,
    )


def _index_job_config(payload: IndexJobCreate) -> dict:
    return {
        "parser_profile": payload.parser_profile,
        "chunking": payload.chunking,
        "embedding_model": payload.embedding_model,
        "force_reindex": payload.force_reindex,
        "source": "synthetic_text" if payload.source_text is not None else "object_store",
    }


def _validate_confidentiality(level: str) -> None:
    if level.lower() not in CONFIDENTIALITY_RANK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown confidentiality_level",
        )


def _validate_access_groups(groups: list[str], *, field: str = "access_groups") -> None:
    """Reject malformed access-group strings at write time (AC-04).

    Applied to the values that are about to be PERSISTED, on every write path that stores
    group strings: source defaults (create_source), both ingestion endpoints (after
    inheritance is resolved, so an inherited group is checked too) and the ACL patch. A
    validation that covered only some write paths would just move the hole.

    HONEST SCOPE: this is a SHAPE rule (see domain/classification.access_group_shape_error),
    not a vocabulary rule. It catches padding, control characters, commas, over-length values
    and empty reserved prefixes -- the mechanically detectable half of the typo problem. It
    cannot catch ``all-employes``, which is well-shaped and simply names the wrong audience;
    that needs the authoritative group vocabulary, which SSO owns and which this Work Order
    explicitly excludes reproducing locally. The other half of the mitigation is removing the
    per-document retyping in the first place, which is what source defaults do.
    """
    errors = access_group_shape_errors(groups)
    if not errors:
        return
    detail = "; ".join(f"{group!r} {reason}" for group, reason in errors)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Invalid {field}: {detail}",
    )


def _classification_audit_payload(
    document: Document, resolved: ResolvedClassification
) -> dict:
    """Audit body for a document registration: the ACL and WHERE IT CAME FROM.

    The audit trail previously recorded ``confidentiality_level`` alone, which is exactly the
    "records the decision without evaluating it" gap that made a wrong classification
    undetectable. Recording the resolved groups plus the provenance of both halves makes the
    affected population reconstructable from the trail even after the current-state columns
    are overwritten by a later ACL patch. ``confidentiality_floor_applied`` is the detective
    signal for a source configured LESS restrictively than the platform fallback: the
    resolution silently raised it, and silent is exactly what must not go unrecorded.
    """
    return {
        "knowledge_source_id": document.knowledge_source_id,
        "title": document.title,
        "confidentiality_level": document.confidentiality_level,
        "access_groups": list(document.access_groups),
        "confidentiality_source": resolved.confidentiality_source,
        "access_groups_source": resolved.access_groups_source,
        "classification_source_id": resolved.classification_source_id,
        "confidentiality_floor_applied": resolved.confidentiality_floor_applied,
    }


def _fetch_object_bytes(document: Document) -> bytes | None:
    """Fetch a document's original bytes from object storage, or None if unavailable."""
    store = get_object_store()
    if store is None:
        return None
    key = document_object_key(document.id)
    if not store.exists(key):
        return None
    return store.get(key)


def _requested_upload_access_groups(value: str | None) -> list[str] | None:
    """Groups the UPLOAD request actually expressed, or None when it expressed none.

    The form field is comma-delimited, and splitting/stripping it is pre-existing transport
    behaviour that is preserved exactly. What changes is only how "nothing" is represented:

    * field absent            -> None (inherit)
    * field blank / ","-only  -> None (inherit). A blank field expresses no intent; the old
      code discarded it too, falling back to ["all-employees"] inside the parser. The only
      difference now is WHICH fallback applies, and a source default is never broader than
      "all-employees" (which every principal holds unconditionally), so this cannot widen.
    * field with tokens       -> those tokens, verbatim after the split/strip, treated as an
      explicit value exactly as before.
    """
    if value is None:
        return None
    groups = [group.strip() for group in value.split(",") if group.strip()]
    return groups or None


def _safe_upload_filename(filename: str | None) -> str:
    if not filename:
        return "uploaded-document"
    return filename.replace("\\", "/").split("/")[-1] or "uploaded-document"


def _upload_mime_type(content_type: str | None, filename: str) -> str:
    normalized_content_type = (content_type or "").split(";")[0].strip().lower()
    if normalized_content_type in SUPPORTED_DOCUMENT_MIME_TYPES:
        return normalized_content_type

    extension = Path(filename).suffix.casefold()
    if extension == ".pdf":
        return PDF_MIME_TYPE
    if extension == ".docx":
        return DOCX_MIME_TYPE
    if extension == ".md":
        return "text/markdown"
    if extension == ".txt":
        return "text/plain"
    return normalized_content_type or "application/octet-stream"


def _decode_uploaded_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")
