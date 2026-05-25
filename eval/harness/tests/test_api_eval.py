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

    def test_trace_gate_accepts_ordered_answer_steps(self):
        case = next(case for case in self.corpus.cases if case.case_id == "rag_001")

        result = score_api_case(
            case,
            run={
                "id": "run-trace-1",
                "status": "succeeded",
                "latency_ms": 123,
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
            run_steps=[
                _step(1, "guard_input", "security_precheck", "fast-small"),
                _step(2, "retriever", "retriever", "deterministic"),
                _step(3, "generator", "answer_generator", "standard-rag"),
                _step(4, "citation_validator", "critic", "fast-small"),
                _step(5, "guard_output", "security_finalcheck", "fast-small"),
            ],
            api_document_id_map={"api-hr-001": "HR-001"},
            latency_threshold_ms=5000,
            trace_gate_enabled=True,
        )

        self.assertTrue(result.passed, result.findings)
        self.assertEqual(result.run_latency_ms, 123)
        self.assertEqual(
            result.trace_step_names,
            ("guard_input", "retriever", "generator", "citation_validator", "guard_output"),
        )

    def test_trace_gate_rejects_missing_route_unordered_steps_and_latency_breach(self):
        case = next(case for case in self.corpus.cases if case.case_id == "rag_001")

        result = score_api_case(
            case,
            run={
                "id": "run-trace-2",
                "status": "succeeded",
                "latency_ms": 6001,
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
            retrieval_hits=[],
            run_steps=[
                {
                    "step_order": 2,
                    "step_type": "retriever",
                    "status": "succeeded",
                    "output_summary": {"model_tier": "deterministic"},
                },
                _step(1, "guard_input", "security_precheck", "fast-small"),
            ],
            api_document_id_map={"api-hr-001": "HR-001"},
            latency_threshold_ms=5000,
            trace_gate_enabled=True,
        )

        self.assertFalse(result.passed)
        self.assertIn("Trace gate: run latency 6001ms exceeded 5000ms", result.findings)
        self.assertIn("Trace gate: runtime steps are not ordered by step_order", result.findings)
        self.assertIn(
            "Trace gate: missing runtime steps generator, citation_validator, guard_output",
            result.findings,
        )
        self.assertIn("Trace gate: retriever missing route_stage", result.findings)
        self.assertIn("Trace gate: answer case missing retrieval-hit records", result.findings)

    def test_trace_gate_accepts_guard_only_refusal_steps(self):
        case = next(case for case in self.corpus.cases if case.case_id == "ref_004")

        result = score_api_case(
            case,
            run={
                "id": "run-trace-3",
                "status": "failed",
                "latency_ms": 42,
                "answer": "Write actions are not supported by this document RAG runtime.",
                "citations": [],
                "guardrail": {"outcome": "refuse", "citation_validation_pass": False},
                "retrieval_denied_count": 0,
            },
            retrieval_hits=[],
            run_steps=[
                _step(1, "guard_input", "security_precheck", "fast-small", status="failed"),
                _step(2, "guard_output", "security_finalcheck", "fast-small", status="failed"),
            ],
            api_document_id_map={},
            latency_threshold_ms=5000,
            trace_gate_enabled=True,
        )

        self.assertTrue(result.passed, result.findings)


def _step(
    step_order: int,
    step_type: str,
    route_stage: str,
    model_tier: str,
    *,
    status: str = "succeeded",
) -> dict:
    return {
        "step_order": step_order,
        "step_type": step_type,
        "status": status,
        "output_summary": {
            "route_stage": route_stage,
            "model_tier": model_tier,
        },
    }


if __name__ == "__main__":
    unittest.main()
