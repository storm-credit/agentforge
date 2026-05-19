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
                "setup": {"validation_lane": "local-regression"},
                "results": [],
            }
        )

        self.assertEqual(payload["budget_class"], "smoke")

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
