from __future__ import annotations

import json
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from urllib import request as http_request
from urllib.error import HTTPError, URLError

from app.core.config import Settings, get_settings

_OPENAI_COMPATIBLE_MODES = {"openai-compatible", "openai_compatible", "openai"}
_OPENAI_CHAT_COMPLETIONS_PATH = "/chat/completions"
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
_THINK_TAG_RE = re.compile(r"</?think>", flags=re.IGNORECASE)


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
    mode = _normalize_mode(gateway_settings.model_gateway_mode)
    if mode in _OPENAI_COMPATIBLE_MODES:
        return _generate_openai_compatible_answer(
            citation_count=citation_count,
            settings=gateway_settings,
            mode=mode,
        )

    answer = _build_safe_synthetic_answer(citation_count)
    provenance: dict[str, Any] = {
        "status": "succeeded",
        "provider": gateway_settings.model_gateway_provider,
        "model_id": gateway_settings.model_gateway_model_id,
        "endpoint_alias": _safe_endpoint_alias(gateway_settings.model_gateway_endpoint_alias),
        "validation_lane": gateway_settings.model_gateway_validation_lane,
        "latency_ms": 1,
        "served_model": gateway_settings.model_gateway_model_id,
        "token_usage": _fake_token_usage(answer),
        "answer_source": "local-model-gateway",
        "mode": mode,
    }
    return ModelGatewayResult(answer=answer, provenance=provenance)


def _generate_openai_compatible_answer(
    *,
    citation_count: int,
    settings: Settings,
    mode: str,
) -> ModelGatewayResult:
    started_at = perf_counter()
    try:
        base_url = _configured_base_url(settings)
        if base_url is None:
            return _fallback_result(
                citation_count=citation_count,
                settings=settings,
                mode=mode,
                started_at=started_at,
                fallback_reason="gateway_misconfigured",
            )

        payload = _openai_compatible_payload(
            citation_count=citation_count,
            model_id=settings.model_gateway_model_id,
        )
        headers = {"Content-Type": "application/json"}
        api_key = _configured_api_key(settings)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        request = http_request.Request(
            _chat_completions_url(base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with http_request.urlopen(  # noqa: S310 - configured for local OpenAI-compatible gateways.
            request,
            timeout=settings.model_gateway_timeout_seconds,
        ) as response:
            response_payload = json.loads(response.read().decode("utf-8"))

        answer = _extract_openai_answer(response_payload)
        if answer is None:
            return _fallback_result(
                citation_count=citation_count,
                settings=settings,
                mode=mode,
                started_at=started_at,
                fallback_reason="empty_gateway_response",
            )

        provenance = _base_provenance(
            settings=settings,
            mode=mode,
            latency_ms=_latency_ms(started_at),
            status="succeeded",
            answer_source="local-model-gateway",
            served_model=_safe_served_model(
                response_payload.get("model"),
                fallback=settings.model_gateway_model_id,
            ),
            token_usage=_normalize_token_usage(response_payload.get("usage")),
        )
        return ModelGatewayResult(answer=answer, provenance=provenance)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return _fallback_result(
            citation_count=citation_count,
            settings=settings,
            mode=mode,
            started_at=started_at,
            fallback_reason="gateway_unavailable",
        )


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


def _fallback_result(
    *,
    citation_count: int,
    settings: Settings,
    mode: str,
    started_at: float,
    fallback_reason: str,
) -> ModelGatewayResult:
    answer = _build_safe_synthetic_answer(citation_count)
    provenance = _base_provenance(
        settings=settings,
        mode=mode,
        latency_ms=_latency_ms(started_at),
        status="fallback",
        answer_source="safe-fallback",
        served_model=settings.model_gateway_model_id,
        token_usage=_fake_token_usage(answer),
    )
    provenance["fallback_reason"] = fallback_reason
    return ModelGatewayResult(answer=answer, provenance=provenance)


def _base_provenance(
    *,
    settings: Settings,
    mode: str,
    latency_ms: int,
    status: str,
    answer_source: str,
    served_model: str,
    token_usage: dict[str, int],
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": settings.model_gateway_provider,
        "model_id": settings.model_gateway_model_id,
        "endpoint_alias": _safe_endpoint_alias(settings.model_gateway_endpoint_alias),
        "validation_lane": settings.model_gateway_validation_lane,
        "latency_ms": latency_ms,
        "served_model": served_model,
        "token_usage": token_usage,
        "answer_source": answer_source,
        "mode": mode,
    }


def _openai_compatible_payload(*, citation_count: int, model_id: str) -> dict[str, Any]:
    return {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer only from Agent Forge context that has already passed retrieval ACL "
                    "filtering and citation validation. If the authorized context is insufficient, "
                    "say that no supported answer is available."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Authorized citation count: "
                    f"{citation_count}. Provide a concise answer grounded only in those citations."
                ),
            },
        ],
        "temperature": 0,
        "stream": False,
    }


def _extract_openai_answer(response_payload: dict[str, Any]) -> str | None:
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None

    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        cleaned_content = _clean_model_answer(content)
        if cleaned_content is not None:
            return cleaned_content

    text = first_choice.get("text")
    cleaned_text = _clean_model_answer(text)
    if cleaned_text is not None:
        return cleaned_text

    return None


def _clean_model_answer(answer: Any) -> str | None:
    if not isinstance(answer, str):
        return None

    cleaned = _THINK_BLOCK_RE.sub("", answer)
    cleaned = _THINK_TAG_RE.sub("", cleaned).strip()
    return cleaned or None


def _normalize_token_usage(usage: Any) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    prompt_tokens = _coerce_non_negative_int(usage.get("prompt_tokens"))
    completion_tokens = _coerce_non_negative_int(usage.get("completion_tokens"))
    total_tokens = _coerce_non_negative_int(usage.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _configured_base_url(settings: Settings) -> str | None:
    if settings.model_gateway_openai_base_url is None:
        return None

    base_url = settings.model_gateway_openai_base_url.strip().rstrip("/")
    if not base_url:
        return None
    return base_url


def _configured_api_key(settings: Settings) -> str | None:
    api_key = settings.model_gateway_openai_api_key
    if api_key is None:
        return None

    value = api_key.get_secret_value().strip()
    return value or None


def _chat_completions_url(base_url: str) -> str:
    if base_url.endswith(_OPENAI_CHAT_COMPLETIONS_PATH):
        return base_url
    return f"{base_url}{_OPENAI_CHAT_COMPLETIONS_PATH}"


def _latency_ms(started_at: float) -> int:
    return max(1, int((perf_counter() - started_at) * 1000))


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized == "openai_compatible":
        return "openai-compatible"
    return normalized or "fake"


def _safe_endpoint_alias(endpoint_alias: str) -> str:
    if "://" in endpoint_alias or endpoint_alias.lower().startswith("www."):
        return "configured-local-endpoint"
    return endpoint_alias


def _safe_served_model(served_model: Any, *, fallback: str) -> str:
    if not isinstance(served_model, str):
        return fallback
    normalized = served_model.strip()
    if not normalized or "://" in normalized or len(normalized) > 128:
        return fallback
    return normalized
