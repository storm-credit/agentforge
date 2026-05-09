from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from agentforge_eval.corpus import Corpus, EvalCase, principal_can_access_document


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    suite: str
    passed: bool
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ScoreReport:
    corpus_id: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    suite_counts: dict[str, int]
    results: tuple[CaseResult, ...]

    @property
    def passed(self) -> bool:
        return self.failed_cases == 0

    def to_dict(self) -> dict:
        return {
            "corpus_id": self.corpus_id,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "suite_counts": self.suite_counts,
            "results": [
                {
                    "case_id": result.case_id,
                    "suite": result.suite,
                    "passed": result.passed,
                    "findings": list(result.findings),
                }
                for result in self.results
            ],
        }


def score_corpus(corpus: Corpus) -> ScoreReport:
    documents_by_id = corpus.documents_by_id
    results = tuple(score_case(case, corpus) for case in corpus.cases)
    passed_cases = sum(1 for result in results if result.passed)
    suite_counts = Counter(case.suite for case in corpus.cases)

    if len(documents_by_id) != len(corpus.documents):
        duplicate_ids = len(corpus.documents) - len(documents_by_id)
        results = results + (
            CaseResult(
                case_id="corpus.documents",
                suite="corpus",
                passed=False,
                findings=(f"Duplicate document IDs detected: {duplicate_ids}",),
            ),
        )

    return ScoreReport(
        corpus_id=corpus.corpus_id,
        total_cases=len(corpus.cases),
        passed_cases=passed_cases,
        failed_cases=len(results) - passed_cases,
        suite_counts=dict(sorted(suite_counts.items())),
        results=results,
    )


def score_case(case: EvalCase, corpus: Corpus) -> CaseResult:
    documents_by_id = corpus.documents_by_id
    findings: list[str] = []

    if not case.case_id:
        findings.append("case_id is empty")

    for citation in case.expected_citations:
        document = documents_by_id.get(citation.document_id)
        if document is None:
            findings.append(f"Expected citation references unknown document {citation.document_id}")
            continue
        if citation.locator not in document.locators:
            findings.append(
                f"Expected citation {citation.document_id}/{citation.locator} has unknown locator"
            )
        if not principal_can_access_document(case.principal, document):
            findings.append(
                f"Expected citation {citation.document_id} is not accessible to principal"
            )

    if case.expected_behavior == "answer":
        if not case.expected_citations:
            findings.append("answer case has no expected citation")

        for document_id in case.forbidden_citations:
            document = documents_by_id.get(document_id)
            if document and principal_can_access_document(case.principal, document):
                findings.append(
                    f"Forbidden citation {document_id} is accessible; case needs a stricter reason"
                )

    if case.expected_behavior == "policy_denied":
        known_forbidden = [
            documents_by_id[document_id]
            for document_id in case.forbidden_citations
            if document_id in documents_by_id
        ]
        if not known_forbidden:
            findings.append("policy_denied case has no known forbidden documents")
        for document in known_forbidden:
            if principal_can_access_document(case.principal, document):
                findings.append(
                    f"policy_denied case forbids accessible document {document.document_id}"
                )

    if case.expected_behavior in {"refuse", "no_context"} and case.expected_citations:
        findings.append(f"{case.expected_behavior} case should not require citations")

    return CaseResult(
        case_id=case.case_id,
        suite=case.suite,
        passed=not findings,
        findings=tuple(findings),
    )

