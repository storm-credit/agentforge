from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ModelGatewayResult:
    answer: str
    provenance: dict[str, Any]


def generate_runtime_answer(
    *,
    citation_count: int,
    settings: Settings | None = None,
) -> ModelGatewayResult:
    gateway_settings = settings or get_settings()
    answer = _build_safe_synthetic_answer(citation_count)
    provenance: dict[str, Any] = {
        "status": "succeeded",
        "provider": gateway_settings.model_gateway_provider,
        "model_id": gateway_settings.model_gateway_model_id,
        "endpoint_alias": gateway_settings.model_gateway_endpoint_alias,
        "validation_lane": gateway_settings.model_gateway_validation_lane,
        "latency_ms": 1,
        "served_model": gateway_settings.model_gateway_model_id,
        "token_usage": _fake_token_usage(answer),
        "answer_source": "local-model-gateway",
        "mode": gateway_settings.model_gateway_mode,
    }
    return ModelGatewayResult(answer=answer, provenance=provenance)


def _build_safe_synthetic_answer(citation_count: int) -> str:
    if citation_count == 0:
        return "No authorized context was available for this runtime run."

    return f"Synthetic runtime response based on {citation_count} authorized citation(s)."


def _fake_token_usage(answer: str) -> dict[str, int]:
    completion_tokens = len(answer.split())
    return {
        "prompt_tokens": 0,
        "completion_tokens": completion_tokens,
        "total_tokens": completion_tokens,
    }
