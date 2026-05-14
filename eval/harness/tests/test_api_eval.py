import sys
import unittest
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.api_eval import (
    build_document_markdown,
    document_access_groups,
    index_expected_to_succeed,
    principal_headers,
    score_api_case,
    select_cases,
)
from agentforge_eval.corpus import load_corpus


class ApiEvalHelperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_corpus(REPO_ROOT / "eval" / "synthetic-corpus" / "cases-v0.1.json")
        cls.documents = cls.corpus.documents_by_id

    def test_restricted_documents_with_groups_preserve_group_gate(self):
        self.assertEqual(document_access_groups(self.documents["HR-003"]), ("hr-readers",))
        self.assertEqual(document_access_groups(self.documents["FIN-002"]), ("finance-close",))

    def test_internal_documents_include_all_employee_api_subject(self):
        groups = document_access_groups(self.documents["HR-001"])

        self.assertIn("all-employees", groups)
        self.assertIn("employee", groups)

    def test_confidential_document_index_failure_is_expected(self):
        self.assertFalse(index_expected_to_succeed(self.documents["EXEC-001"]))
        self.assertTrue(index_expected_to_succeed(self.documents["SEC-001"]))

    def test_restricted_answer_case_raises_principal_clearance(self):
        allowed_case = next(case for case in self.corpus.cases if case.case_id == "acl_002")
        blocked_case = next(case for case in self.corpus.cases if case.case_id == "acl_001")

        self.assertEqual(principal_headers(allowed_case, self.corpus)["X-Agent-Forge-Clearance"], "restricted")
        self.assertEqual(principal_headers(blocked_case, self.corpus)["X-Agent-Forge-Clearance"], "internal")

    def test_generated_markdown_keeps_locator_and_question_terms_together(self):
        markdown = build_document_markdown(self.documents["HR-001"], self.corpus.cases)

        self.assertIn("## section:annual-leave", markdown)
        self.assertIn(
            "How many days before annual leave should an employee submit a request?",
            markdown,
        )
        self.assertIn("annual leave request timing", markdown)

    def test_select_cases_accepts_comma_separated_case_and_suite_filters(self):
        cases = select_cases(
            self.corpus,
            case_ids=("rag_001,acl_002",),
            suites=("acl",),
        )

        self.assertEqual([case.case_id for case in cases], ["acl_002"])

    def test_score_answer_maps_api_document_id_and_locator(self):
        case = next(case for case in self.corpus.cases if case.case_id == "rag_001")

        result = score_api_case(
            case,
            run={
                "id": "run-1",
                "status": "succeeded",
                "answer": "Synthetic runtime response based on 1 authorized citation(s).",
                "citations": [
                    {
                        "document_id": "api-hr-001",
                        "title": "Vacation and Leave Policy",
                        "citation_locator": (
                            "Vacation and Leave Policy / "
                            "Vacation and Leave Policy > section:annual-leave / lines 7-12"
                        ),
                    }
                ],
                "guardrail": {"citation_validation_pass": True, "outcome": "answer"},
                "retrieval_denied_count": 1,
            },
            retrieval_hits=[
                {
                    "document_id": "api-hr-001",
                    "title": "Vacation and Leave Policy",
                    "citation_locator": (
                        "Vacation and Leave Policy / "
                        "Vacation and Leave Policy > section:annual-leave / lines 7-12"
                    ),
                }
            ],
            api_document_id_map={"api-hr-001": "HR-001"},
        )

        self.assertTrue(result.passed, result.findings)
        self.assertEqual(result.citation_document_ids, ("HR-001",))
        self.assertEqual(result.retrieval_document_ids, ("HR-001",))

    def test_score_policy_denied_fails_when_forbidden_document_is_cited(self):
        case = next(case for case in self.corpus.cases if case.case_id == "acl_001")

        result = score_api_case(
            case,
            run={
                "id": "run-2",
                "status": "succeeded",
                "answer": "Synthetic runtime response based on 1 authorized citation(s).",
                "citations": [
                    {
                        "document_id": "api-hr-003",
                        "title": "Restricted HR Case Handling",
                        "citation_locator": (
                            "Restricted HR Case Handling / "
                            "Restricted HR Case Handling > section:case-escalation / lines 7-12"
                        ),
                    }
                ],
                "guardrail": {"citation_validation_pass": True, "outcome": "answer"},
                "retrieval_denied_count": 0,
            },
            retrieval_hits=[
                {
                    "document_id": "api-hr-003",
                    "title": "Restricted HR Case Handling",
                    "citation_locator": (
                        "Restricted HR Case Handling / "
                        "Restricted HR Case Handling > section:case-escalation / lines 7-12"
                    ),
                }
            ],
            api_document_id_map={"api-hr-003": "HR-003"},
        )

        self.assertFalse(result.passed)
        self.assertIn("policy_denied case returned citations", result.findings)
        self.assertIn("Forbidden documents were cited: HR-003", result.findings)

    def test_score_refuse_requires_refusal_outcome_without_hits(self):
        case = next(case for case in self.corpus.cases if case.case_id == "ref_004")

        result = score_api_case(
            case,
            run={
                "id": "run-3",
                "status": "failed",
                "answer": "Write actions are not supported by this document RAG runtime.",
                "citations": [],
                "guardrail": {"outcome": "refuse", "citation_validation_pass": False},
                "retrieval_denied_count": 0,
            },
            retrieval_hits=[],
            api_document_id_map={},
        )

        self.assertTrue(result.passed, result.findings)

    def test_score_no_context_rejects_retrieval_hits(self):
        case = next(case for case in self.corpus.cases if case.case_id == "ref_002")

        result = score_api_case(
            case,
            run={
                "id": "run-4",
                "status": "failed",
                "answer": "No authorized context was available for this runtime run.",
                "citations": [],
                "guardrail": {"outcome": "no_context", "citation_validation_pass": False},
                "retrieval_denied_count": 0,
            },
            retrieval_hits=[{"document_id": "api-hr-001", "title": "Vacation and Leave Policy"}],
            api_document_id_map={"api-hr-001": "HR-001"},
        )

        self.assertFalse(result.passed)
        self.assertIn("no_context case used retrieval hits", result.findings)


if __name__ == "__main__":
    unittest.main()
