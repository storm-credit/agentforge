"""Reranker hook for retrieval results.

A portable lever (like the LLM/embedding gateways): retrieval hits pass through a
reranker before becoming citations/context. The default ``NoopReranker`` preserves
order (no behavior change).

Backends:

- ``none`` (default): order-preserving no-op.
- ``hybrid_lexical``: deterministic, dependency-free hybrid reranker. Computes a
  BM25 lexical score for each hit against its actual chunk content (supplied by the
  caller via ``content_by_chunk_id`` — ``VectorHit`` itself does not carry content),
  then fuses the vector-similarity ranking with the lexical ranking via Reciprocal
  Rank Fusion (RRF). No model call, fully unit-testable.
- A cross-encoder backend (vLLM/Cohere-compatible /rerank; see
  docs/research-reranking-options.md) plugs in here once an in-house model is
  available — that remains the documented path for semantic reranking gains that
  lexical signals cannot provide.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class Reranker(Protocol):
    name: str

    def rerank(
        self,
        query: str,
        hits: Sequence[T],
        content_by_chunk_id: Mapping[str, str] | None = None,
    ) -> tuple[T, ...]:
        ...


class NoopReranker:
    """Order-preserving reranker — the default. Deterministic, no model call."""

    name = "none"

    def rerank(
        self,
        query: str,
        hits: Sequence[T],
        content_by_chunk_id: Mapping[str, str] | None = None,
    ) -> tuple[T, ...]:
        return tuple(hits)


def _tokenize(text: str) -> list[str]:
    """Casefolded word tokens (``\\w+`` — covers Hangul at eojeol granularity)."""
    return _TOKEN_RE.findall(text.casefold())


def _bm25_scores(
    query_terms: Sequence[str],
    docs: Sequence[Sequence[str]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """BM25 over the in-request hit set (a handful of docs — pure Python is fine).

    IDF is computed across the hit set itself, so a term shared by every hit stops
    discriminating; length normalization uses the average tokenized chunk length.
    """
    n = len(docs)
    if n == 0 or not query_terms:
        return [0.0] * n
    avgdl = sum(len(d) for d in docs) / n
    if avgdl == 0:
        return [0.0] * n
    unique_terms = sorted(set(query_terms))
    df = {t: sum(1 for d in docs if t in d) for t in unique_terms}
    idf = {t: math.log(1.0 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in unique_terms}
    scores: list[float] = []
    for doc in docs:
        dl = len(doc)
        score = 0.0
        for term in unique_terms:
            tf = doc.count(term)
            if tf == 0:
                continue
            denom = tf + k1 * (1.0 - b + b * dl / avgdl)
            score += idf[term] * tf * (k1 + 1.0) / denom
        scores.append(score)
    return scores


class HybridLexicalReranker:
    """Deterministic hybrid reranker: vector rank + BM25 lexical rank fused via RRF.

    The two raw signals live on different scales (cosine similarity vs BM25), so
    instead of a weighted sum we rank hits by each signal independently and combine
    with Reciprocal Rank Fusion: ``1/(k + rank_vector) + 1/(k + rank_lexical)``.

    - The incoming hit order is taken as the vector ranking (hits arrive sorted by
      vector score descending from the store).
    - Lexical BM25 is computed against each hit's chunk content, looked up via the
      caller-supplied ``content_by_chunk_id`` (hits without content score 0).
    - All ties break toward the original vector order, so with no content (or a
      lexically indiscriminate query) the output order equals the input order.
    """

    name = "hybrid_lexical"

    def __init__(self, *, rrf_k: int = 60) -> None:
        self._rrf_k = rrf_k

    def rerank(
        self,
        query: str,
        hits: Sequence[T],
        content_by_chunk_id: Mapping[str, str] | None = None,
    ) -> tuple[T, ...]:
        if len(hits) < 2:
            return tuple(hits)
        contents = content_by_chunk_id or {}
        query_terms = _tokenize(query)
        docs = [
            _tokenize(contents.get(getattr(hit, "chunk_id", None) or "", ""))
            for hit in hits
        ]
        lexical = _bm25_scores(query_terms, docs)

        # Vector rank = incoming position (1-based). Lexical rank = BM25 order with
        # ties broken by incoming position (stable sort on index).
        indices = list(range(len(hits)))
        lexical_order = sorted(indices, key=lambda i: (-lexical[i], i))
        lexical_rank = {idx: rank for rank, idx in enumerate(lexical_order, start=1)}

        k = self._rrf_k
        rrf = {
            i: 1.0 / (k + (i + 1)) + 1.0 / (k + lexical_rank[i])
            for i in indices
        }
        fused_order = sorted(indices, key=lambda i: (-rrf[i], i))
        return tuple(hits[i] for i in fused_order)


@lru_cache
def get_reranker() -> Reranker:
    from app.core.config import get_settings

    backend = get_settings().rerank_backend
    if backend == "none":
        return NoopReranker()
    if backend == "hybrid_lexical":
        return HybridLexicalReranker()
    # Future backend (e.g. "vllm"): construct a cross-encoder client here and call its
    # /rerank endpoint. Not wired until an in-house reranker is available; fall back to
    # no-op so behavior stays unchanged and safe.
    logger.warning("rerank_backend=%r not implemented; using no-op reranker", backend)
    return NoopReranker()
