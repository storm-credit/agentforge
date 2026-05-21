import importlib.util
import json
from typing import Any

import pytest


RUNTIME_DEPS = ("pydantic_settings",)


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)


def test_fake_model_gateway_remains_deterministic_default():
    from app.core.config import Settings
    from app.infra.model_gateway import generate_runtime_answer

    result = generate_runtime_answer(citation_count=2, settings=Settings())

    assert result.answer == "Synthetic runtime response based on 2 authorized citation(s)."
    assert result.provenance == {
        "status": "succeeded",
        "provider": "local-fake",
        "model_id": "synthetic-runtime-answerer",
        "endpoint_alias": "local-fake",
        "validation_lane": "local-regression",
        "latency_ms": 1,
        "served_model": "synthetic-runtime-answerer",
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 8,
            "total_tokens": 8,
        },
        "answer_source": "local-model-gateway",
        "mode": "fake",
    }


def test_openai_compatible_gateway_returns_safe_success_provenance(monkeypatch):
    from app.core.config import Settings
    from app.infra import model_gateway

    requests = []

    def fake_urlopen(request, timeout):
        requests.append(
            {
                "url": request.full_url,
                "authorization": request.get_header("Authorization"),
                "payload": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return _FakeResponse(
            {
                "model": "qwen3:8b",
                "choices": [
                    {
                        "message": {
                            "content": (
                                "<think>internal reasoning must not reach the final answer</think>\n"
                                "Local answer from authorized context."
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            }
        )

    monkeypatch.setattr(model_gateway.http_request, "urlopen", fake_urlopen)
    settings = Settings(
        model_gateway_provider="local-vllm",
        model_gateway_model_id="qwen3:8b",
        model_gateway_endpoint_alias="local-openai-compatible",
        model_gateway_validation_lane="local-regression",
        model_gateway_timeout_seconds=3.5,
        model_gateway_mode="openai-compatible",
        model_gateway_openai_base_url="http://127.0.0.1:8000/v1",
        model_gateway_openai_api_key="local-secret-key",
    )

    result = model_gateway.generate_runtime_answer(citation_count=1, settings=settings)

    assert result.answer == "Local answer from authorized context."
    assert "<think>" not in result.answer
    assert requests == [
        {
            "url": "http://127.0.0.1:8000/v1/chat/completions",
            "authorization": "Bearer local-secret-key",
            "payload": {
                "model": "qwen3:8b",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer only from Agent Forge context that has already passed "
                            "retrieval ACL filtering and citation validation. If the authorized "
                            "context is insufficient, say that no supported answer is available."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Authorized citation count: 1. Provide a concise answer grounded only "
                            "in those citations."
                        ),
                    },
                ],
                "temperature": 0,
                "stream": False,
            },
            "timeout": 3.5,
        }
    ]
    assert result.provenance["status"] == "succeeded"
    assert result.provenance["provider"] == "local-vllm"
    assert result.provenance["model_id"] == "qwen3:8b"
    assert result.provenance["endpoint_alias"] == "local-openai-compatible"
    assert result.provenance["served_model"] == "qwen3:8b"
    assert result.provenance["token_usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 5,
        "total_tokens": 17,
    }
    assert result.provenance["answer_source"] == "local-model-gateway"
    assert result.provenance["mode"] == "openai-compatible"
    _assert_no_sensitive_provenance(result.provenance)


def test_openai_compatible_gateway_falls_back_with_safe_provenance(monkeypatch):
    from app.core.config import Settings
    from app.infra import model_gateway

    def fake_urlopen(request, timeout):
        raise OSError(
            "connection refused at http://127.0.0.1:8000/v1 with local-secret-key and raw prompt"
        )

    monkeypatch.setattr(model_gateway.http_request, "urlopen", fake_urlopen)
    settings = Settings(
        model_gateway_provider="local-vllm",
        model_gateway_model_id="qwen3:8b",
        model_gateway_endpoint_alias="http://127.0.0.1:8000/v1",
        model_gateway_mode="openai-compatible",
        model_gateway_openai_base_url="http://127.0.0.1:8000/v1",
        model_gateway_openai_api_key="local-secret-key",
    )

    result = model_gateway.generate_runtime_answer(citation_count=3, settings=settings)

    assert result.answer == "Synthetic runtime response based on 3 authorized citation(s)."
    assert result.provenance["status"] == "fallback"
    assert result.provenance["endpoint_alias"] == "configured-local-endpoint"
    assert result.provenance["answer_source"] == "safe-fallback"
    assert result.provenance["fallback_reason"] == "gateway_unavailable"
    assert result.provenance["token_usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 8,
        "total_tokens": 8,
    }
    _assert_no_sensitive_provenance(result.provenance)


def _assert_no_sensitive_provenance(provenance: dict[str, Any]) -> None:
    serialized = json.dumps(provenance, sort_keys=True)
    assert "api_key" not in provenance
    assert "base_url" not in provenance
    assert "prompt" not in provenance
    assert "http://127.0.0.1:8000/v1" not in serialized
    assert "local-secret-key" not in serialized
    assert "connection refused" not in serialized
    assert "raw prompt" not in serialized


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")
