"""Reranker hook for retrieval results.

A portable lever (like the LLM/embedding gateways): retrieval hits pass through a
reranker before becoming citations/context. The default ``NoopReranker`` preserves
order (no behavior change). A cross-encoder backend (vLLM/Cohere-compatible /rerank;
see docs/research-reranking-options.md) plugs in here once an in-house model is
available — that is the documented path to address the refusal-discipline gap
(c07 over-answer), which scalar vector scores cannot fix.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: Sequence[T]) -> tuple[T, ...]:
        ...


class NoopReranker:
    """Order-preserving reranker — the default. Deterministic, no model call."""

    name = "none"

    def rerank(self, query: str, hits: Sequence[T]) -> tuple[T, ...]:
        return tuple(hits)


@lru_cache
def get_reranker() -> Reranker:
    from app.core.config import get_settings

    backend = get_settings().rerank_backend
    if backend == "none":
        return NoopReranker()
    # Future backend (e.g. "vllm"): construct a cross-encoder client here and call its
    # /rerank endpoint. Not wired until an in-house reranker is available; fall back to
    # no-op so behavior stays unchanged and safe.
    logger.warning("rerank_backend=%r not implemented; using no-op reranker", backend)
    return NoopReranker()
