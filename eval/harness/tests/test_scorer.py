import sys
import unittest
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.corpus import load_corpus, principal_can_access_document
from agentforge_eval.scorer import score_corpus


class SyntheticCorpusScorerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_corpus(REPO_ROOT / "eval" / "synthetic-corpus" / "cases-v0.1.json")
        cls.documents = cls.corpus.documents_by_id

    def test_corpus_scores_without_findings(self):
        report = score_corpus(self.corpus)

        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual(report.total_cases, 30)
        self.assertEqual(report.failed_cases, 0)

    def test_restricted_documents_require_matching_group_when_group_is_declared(self):
        blocked_case = next(case for case in self.corpus.cases if case.case_id == "acl_001")
        allowed_case = next(case for case in self.corpus.cases if case.case_id == "acl_002")

        self.assertFalse(
            principal_can_access_document(blocked_case.principal, self.documents["HR-003"])
        )
        self.assertTrue(
            principal_can_access_document(allowed_case.principal, self.documents["HR-003"])
        )

    def test_confidential_documents_are_denied_by_default(self):
        case = next(case for case in self.corpus.cases if case.case_id == "safe_001")

        self.assertFalse(principal_can_access_document(case.principal, self.documents["EXEC-001"]))


if __name__ == "__main__":
    unittest.main()

