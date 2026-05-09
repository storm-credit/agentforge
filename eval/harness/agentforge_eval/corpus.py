from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Principal:
    user_id: str
    department_id: str
    roles: frozenset[str]
    groups: frozenset[str]


@dataclass(frozen=True)
class Document:
    document_id: str
    title: str
    owner_department: str
    confidentiality_level: str
    allowed_departments: frozenset[str]
    allowed_groups: frozenset[str]
    locators: frozenset[str]


@dataclass(frozen=True)
class Citation:
    document_id: str
    locator: str


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    suite: str
    question: str
    principal: Principal
    expected_behavior: str
    expected_answer_points: tuple[str, ...]
    expected_citations: tuple[Citation, ...]
    forbidden_citations: tuple[str, ...]
    must_not_include: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Corpus:
    schema_version: str
    corpus_id: str
    documents: tuple[Document, ...]
    cases: tuple[EvalCase, ...]

    @property
    def documents_by_id(self) -> dict[str, Document]:
        return {document.document_id: document for document in self.documents}


def load_corpus(path: Path) -> Corpus:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_corpus(payload)


def parse_corpus(payload: dict[str, Any]) -> Corpus:
    documents = tuple(_parse_document(item) for item in payload["documents"])
    cases = tuple(_parse_case(item) for item in payload["cases"])
    return Corpus(
        schema_version=payload["schema_version"],
        corpus_id=payload["corpus_id"],
        documents=documents,
        cases=cases,
    )


def _parse_document(payload: dict[str, Any]) -> Document:
    return Document(
        document_id=payload["document_id"],
        title=payload["title"],
        owner_department=payload["owner_department"],
        confidentiality_level=payload["confidentiality_level"],
        allowed_departments=frozenset(payload.get("allowed_departments", [])),
        allowed_groups=frozenset(payload.get("allowed_groups", [])),
        locators=frozenset(payload["locators"]),
    )


def _parse_case(payload: dict[str, Any]) -> EvalCase:
    principal = Principal(
        user_id=payload["principal"]["user_id"],
        department_id=payload["principal"]["department_id"],
        roles=frozenset(payload["principal"]["roles"]),
        groups=frozenset(payload["principal"]["groups"]),
    )
    citations = tuple(
        Citation(document_id=item["document_id"], locator=item["locator"])
        for item in payload["expected_citations"]
    )
    return EvalCase(
        case_id=payload["case_id"],
        suite=payload["suite"],
        question=payload["question"],
        principal=principal,
        expected_behavior=payload["expected_behavior"],
        expected_answer_points=tuple(payload["expected_answer_points"]),
        expected_citations=citations,
        forbidden_citations=tuple(payload["forbidden_citations"]),
        must_not_include=tuple(payload["must_not_include"]),
        tags=tuple(payload["tags"]),
    )


def principal_can_access_document(principal: Principal, document: Document) -> bool:
    if document.confidentiality_level == "confidential":
        return False

    group_match = bool(principal.groups.intersection(document.allowed_groups))
    department_match = (
        "all" in document.allowed_departments
        or principal.department_id in document.allowed_departments
    )

    if document.confidentiality_level == "restricted":
        if document.allowed_groups:
            return group_match
        return department_match

    return department_match or group_match

