import json
import sys
import unittest
from pathlib import Path
from urllib.error import URLError

HARNESS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.model_probe import (  # noqa: E402
    ModelProbeConfig,
    chat_completions_url,
    model_probe_skipped,
    probe_openai_compatible_model,
)


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ModelProbeTest(unittest.TestCase):
    def test_chat_completions_url_accepts_base_or_full_path(self):
        self.assertEqual(
            chat_completions_url("http://model.local"),
            "http://model.local/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("http://model.local/v1"),
            "http://model.local/v1/chat/completions",
        )
        self.assertEqual(
            chat_completions_url("http://model.local/v1/chat/completions"),
            "http://model.local/v1/chat/completions",
        )

    def test_probe_records_successful_model_provenance(self):
        requests = []

        def fake_open(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse(
                {
                    "model": "qwen3.6-35b-company",
                    "choices": [{"message": {"content": "ready"}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 1},
                }
            )

        result = probe_openai_compatible_model(
            ModelProbeConfig(
                validation_lane="company-quality",
                provider="company-vllm",
                model_id="qwen3.6-35b-company",
                base_url="http://vllm.local/v1",
                endpoint_alias="company-qwen35b",
                timeout_seconds=15,
                api_key="secret",
            ),
            open_fn=fake_open,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["validation_lane"], "company-quality")
        self.assertEqual(result["provider"], "company-vllm")
        self.assertEqual(result["served_model"], "qwen3.6-35b-company")
        self.assertEqual(result["response_preview"], "ready")
        self.assertEqual(result["usage"]["completion_tokens"], 1)
        self.assertEqual(requests[0][1], 15)
        self.assertEqual(requests[0][0].full_url, "http://vllm.local/v1/chat/completions")
        self.assertEqual(requests[0][0].headers["Authorization"], "Bearer secret")

    def test_probe_records_network_failure_without_endpoint_secret(self):
        def fake_open(request, timeout):
            raise URLError("connection refused")

        result = probe_openai_compatible_model(
            ModelProbeConfig(
                validation_lane="local-regression",
                provider="local",
                model_id="qwen3-8b-local",
                base_url="http://localhost:8010",
                endpoint_alias="local-qwen8b",
                timeout_seconds=3,
            ),
            open_fn=fake_open,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_type"], "network_error")
        self.assertEqual(result["endpoint_alias"], "local-qwen8b")
        self.assertNotIn("base_url", result)

    def test_skipped_probe_uses_safe_metadata(self):
        result = model_probe_skipped(
            validation_lane="local-regression",
            provider="local",
            model_id="",
            endpoint_alias="local-qwen8b",
            reason="model endpoint not configured",
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "model endpoint not configured")


if __name__ == "__main__":
    unittest.main()
