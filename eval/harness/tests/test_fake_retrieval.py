import sys
import unittest
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.corpus import load_corpus
from agentforge_eval.retrieval import allowed_context_hits, citation_hits


class FakeRetrievalAclTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_corpus(REPO_ROOT / "eval" / "synthetic-corpus" / "cases-v0.1.json")

    def test_blocked_acl_case_has_no_allowed_context(self):
        case = next(case for case in self.corpus.cases if case.case_id == "acl_001")

        self.assertEqual(allowed_context_hits(case, self.corpus), ())
        self.assertEqual(citation_hits(case, self.corpus), ())

    def test_allowed_acl_case_can_use_expected_restricted_document(self):
        case = next(case for case in self.corpus.cases if case.case_id == "acl_002")

        hits = citation_hits(case, self.corpus)

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].document_id, "HR-003")
        self.assertEqual(hits[0].locator, "section:case-escalation")

    def test_confidential_forbidden_documents_never_enter_context(self):
        for case in self.corpus.cases:
            with self.subTest(case_id=case.case_id):
                context_document_ids = {
                    hit.document_id for hit in allowed_context_hits(case, self.corpus)
                }
                self.assertNotIn("EXEC-001", context_document_ids)

    def test_answer_cases_only_cite_allowed_documents(self):
        for case in self.corpus.cases:
            if case.expected_behavior != "answer":
                continue
            with self.subTest(case_id=case.case_id):
                for hit in citation_hits(case, self.corpus):
                    self.assertTrue(hit.allowed)
                    self.assertTrue(hit.used_as_citation)


if __name__ == "__main__":
    unittest.main()

