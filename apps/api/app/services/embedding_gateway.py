from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingUnavailable(RuntimeError):
    """Raised when the embedding endpoint is unset or unreachable."""


class EmbeddingGateway:
    """Gateway to an OpenAI-compatible embeddings endpoint.

    base_url must include the OpenAI version prefix, e.g. ``http://host:11434/v1``.
    """

    def __init__(self, base_url: str | None, model: str, dim: int, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.dim = dim
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.base_url:
            raise EmbeddingUnavailable("embedding base_url is not configured")
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                r = client.post(
                    f"{self.base_url}/embeddings",
                    json={"model": self.model, "input": texts},
                )
                r.raise_for_status()
                data = r.json()["data"]
                return [item["embedding"] for item in data]
        except Exception as exc:  # noqa: BLE001 - normalize to a domain error
            logger.warning("embedding call failed: %s", exc)
            raise EmbeddingUnavailable(str(exc)) from exc


def get_embedding_gateway() -> EmbeddingGateway:
    s = get_settings()
    return EmbeddingGateway(
        base_url=s.embedding_base_url,
        model=s.embedding_model,
        dim=s.embedding_dim,
        timeout_seconds=s.embedding_timeout_seconds,
    )
