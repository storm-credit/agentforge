import sys
import unittest
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

import run_api_synthetic_eval as runner  # noqa: E402


class ApiRunnerOptionsTest(unittest.TestCase):
    def test_local_regression_payload_uses_smoke_budget(self):
        payload = runner._eval_run_payload(
            {
                "corpus_id": "synthetic-corpus-v0.1",
                "mode": "api",
                "setup": {
                    "validation_lane": "local-regression",
                    "trace_latency_threshold_ms": 5000,
                },
                "results": [
                    {
                        "case_id": "rag_001",
                        "run_id": "run-1",
                        "run_latency_ms": 42,
                        "trace_step_names": ["guard_input", "retriever"],
                        "findings": [],
                    }
                ],
            }
        )

        self.assertEqual(payload["budget_class"], "smoke")
        trace_gate = payload["summary"]["trace_gate"]
        self.assertEqual(trace_gate["status"], "passed")
        self.assertEqual(trace_gate["latency_threshold_ms"], 5000)
        self.assertEqual(trace_gate["p50_latency_ms"], 42)
        self.assertEqual(trace_gate["p95_latency_ms"], 42)
        self.assertEqual(trace_gate["failed_case_ids"], [])

    def test_trace_gate_summary_records_failed_case_ids(self):
        payload = runner._eval_run_payload(
            {
                "corpus_id": "synthetic-corpus-v0.1",
                "mode": "api",
                "setup": {
                    "validation_lane": "local-regression",
                    "trace_latency_threshold_ms": 5000,
                },
                "results": [
                    {
                        "case_id": "rag_001",
                        "run_id": "run-1",
                        "run_latency_ms": 6001,
                        "trace_step_names": [],
                        "findings": ["Trace gate: missing runtime steps"],
                    }
                ],
            }
        )

        trace_gate = payload["summary"]["trace_gate"]
        self.assertEqual(trace_gate["status"], "failed")
        self.assertEqual(trace_gate["failed_case_ids"], ["rag_001"])
        self.assertEqual(trace_gate["cases_with_run_id"], 1)
        self.assertEqual(trace_gate["cases_with_steps"], 0)

    def test_company_quality_payload_uses_release_gate_budget(self):
        payload = runner._eval_run_payload(
            {
                "corpus_id": "synthetic-corpus-v0.1",
                "mode": "api",
                "setup": {"validation_lane": "company-quality"},
                "results": [],
            }
        )

        self.assertEqual(payload["budget_class"], "release-gate")
        quality_review = payload["summary"]["quality_review"]
        self.assertEqual(quality_review["rubric_version"], "quality-rubric-v0.1")
        self.assertEqual(quality_review["status"], "pending_human_review")
        self.assertTrue(quality_review["human_review_required"])
        self.assertTrue(quality_review["release_approval_blocked_until_review"])
        self.assertEqual(
            quality_review["automatic_gates"]["final_answer_cleanliness"]["must_not_include"],
            ["<think>", "</think>"],
        )

    def test_local_regression_quality_review_is_advisory_only(self):
        payload = runner._eval_run_payload(
            {
                "corpus_id": "synthetic-corpus-v0.1",
                "mode": "api",
                "setup": {"validation_lane": "local-regression"},
                "summary": {"existing": "kept"},
                "results": [],
            }
        )

        self.assertEqual(payload["summary"]["existing"], "kept")
        quality_review = payload["summary"]["quality_review"]
        self.assertEqual(quality_review["status"], "advisory_only")
        self.assertFalse(quality_review["human_review_required"])
        self.assertFalse(quality_review["release_approval_blocked_until_review"])

    def test_company_quality_requires_successful_model_probe(self):
        args = runner.parse_args(
            [
                "--validation-lane",
                "company-quality",
                "--skip-model-probe",
            ]
        )
        probe = runner._run_model_probe(args)

        self.assertEqual(probe["status"], "skipped")
        self.assertTrue(runner._model_probe_blocks_lane(args, probe))
        self.assertIn("Model probe skipped", runner._model_probe_finding(probe))

    def test_local_regression_can_skip_unconfigured_probe(self):
        args = runner.parse_args(["--validation-lane", "local-regression"])
        probe = runner._run_model_probe(args)

        self.assertEqual(probe["status"], "skipped")
        self.assertFalse(runner._model_probe_blocks_lane(args, probe))
        self.assertEqual(runner._model_setup(args, probe)["model_endpoint_alias"], "local-qwen8b")


if __name__ == "__main__":
    unittest.main()
