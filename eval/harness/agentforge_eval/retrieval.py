from __future__ import annotations

from dataclasses import dataclass

from agentforge_eval.corpus import Corpus, Document, EvalCase, principal_can_access_document


@dataclass(frozen=True)
class FakeRetrievalHit:
    document_id: str
    locator: str
    allowed: bool
    used_as_citation: bool


def build_fake_retrieval_hits(case: EvalCase, corpus: Corpus) -> tuple[FakeRetrievalHit, ...]:
    """Build deterministic retrieval hits from expected and forbidden case fixtures.

    This is not semantic search. It is the first D3 security check for the retrieval contract:
    expected hits may appear only when ACL allows them, and forbidden hits must stay out of
    the allowed context/citation set.
    """
    documents_by_id = corpus.documents_by_id
    hits: list[FakeRetrievalHit] = []

    for citation in case.expected_citations:
        document = documents_by_id[citation.document_id]
        allowed = principal_can_access_document(case.principal, document)
        hits.append(
            FakeRetrievalHit(
                document_id=citation.document_id,
                locator=citation.locator,
                allowed=allowed,
                used_as_citation=allowed and case.expected_behavior == "answer",
            )
        )

    for document_id in case.forbidden_citations:
        document = documents_by_id.get(document_id)
        if document is None:
            continue
        locator = _first_locator(document)
        hits.append(
            FakeRetrievalHit(
                document_id=document.document_id,
                locator=locator,
                allowed=False,
                used_as_citation=False,
            )
        )

    return tuple(hits)


def allowed_context_hits(case: EvalCase, corpus: Corpus) -> tuple[FakeRetrievalHit, ...]:
    return tuple(hit for hit in build_fake_retrieval_hits(case, corpus) if hit.allowed)


def citation_hits(case: EvalCase, corpus: Corpus) -> tuple[FakeRetrievalHit, ...]:
    return tuple(hit for hit in build_fake_retrieval_hits(case, corpus) if hit.used_as_citation)


def _first_locator(document: Document) -> str:
    return sorted(document.locators)[0]

