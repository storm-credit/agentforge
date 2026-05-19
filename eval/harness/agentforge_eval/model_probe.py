from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OpenFn = Callable[..., Any]


@dataclass(frozen=True)
class ModelProbeConfig:
    validation_lane: str
    provider: str
    model_id: str
    base_url: str
    endpoint_alias: str
    timeout_seconds: float
    api_key: str | None = None
    prompt: str = "Reply with exactly: ready"


def model_probe_skipped(
    *,
    validation_lane: str,
    provider: str,
    model_id: str,
    endpoint_alias: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": "skipped",
        "validation_lane": validation_lane,
        "provider": provider,
        "model_id": model_id,
        "endpoint_alias": endpoint_alias,
        "reason": reason,
    }


def probe_openai_compatible_model(
    config: ModelProbeConfig,
    *,
    open_fn: OpenFn = urlopen,
) -> dict[str, Any]:
    endpoint = chat_completions_url(config.base_url)
    payload = {
        "model": config.model_id,
        "messages": [
            {
                "role": "system",
                "content": "You are an Agent Forge model health probe. Answer briefly.",
            },
            {"role": "user", "content": config.prompt},
        ],
        "temperature": 0,
        "max_tokens": 32,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    started = time.perf_counter()
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with open_fn(request, timeout=config.timeout_seconds) as response:
            body = response.read()
    except HTTPError as exc:
        latency_ms = _elapsed_ms(started)
        return _failure_payload(
            config,
            latency_ms=latency_ms,
            error_type="http_error",
            error=str(exc.code),
            response_body=exc.read().decode("utf-8", errors="replace")[:500],
        )
    except URLError as exc:
        return _failure_payload(
            config,
            latency_ms=_elapsed_ms(started),
            error_type="network_error",
            error=str(exc.reason),
        )
    except TimeoutError as exc:
        return _failure_payload(
            config,
            latency_ms=_elapsed_ms(started),
            error_type="timeout",
            error=str(exc),
        )

    latency_ms = _elapsed_ms(started)
    try:
        decoded = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return _failure_payload(
            config,
            latency_ms=latency_ms,
            error_type="invalid_json",
            error=str(exc),
            response_body=body.decode("utf-8", errors="replace")[:500],
        )

    return {
        **_base_payload(config),
        "status": "succeeded",
        "latency_ms": latency_ms,
        "served_model": _served_model(decoded) or config.model_id,
        "response_preview": _response_preview(decoded),
        "usage": _usage(decoded),
    }


def chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _base_payload(config: ModelProbeConfig) -> dict[str, Any]:
    return {
        "validation_lane": config.validation_lane,
        "provider": config.provider,
        "model_id": config.model_id,
        "endpoint_alias": config.endpoint_alias,
        "timeout_seconds": config.timeout_seconds,
        "endpoint_configured": bool(config.base_url),
    }


def _failure_payload(
    config: ModelProbeConfig,
    *,
    latency_ms: int,
    error_type: str,
    error: str,
    response_body: str | None = None,
) -> dict[str, Any]:
    payload = {
        **_base_payload(config),
        "status": "failed",
        "latency_ms": latency_ms,
        "error_type": error_type,
        "error": error,
    }
    if response_body:
        payload["response_body"] = response_body
    return payload


def _elapsed_ms(started: float) -> int:
    return max(1, int((time.perf_counter() - started) * 1000))


def _served_model(payload: Mapping[str, Any]) -> str | None:
    model = payload.get("model")
    return model if isinstance(model, str) else None


def _response_preview(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    message = first.get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    if not isinstance(content, str):
        return ""
    return content.strip()[:160]


def _usage(payload: Mapping[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage")
    return dict(usage) if isinstance(usage, Mapping) else {}
