"""LLM-as-judge answerability gate (addresses refusal-discipline / over-answer).

Scalar vector scores can't tell an accessible-but-irrelevant passage from a real
answer (proved in eval v0.3: c07 over-answers). An LLM judge decides semantically
whether the retrieved context actually answers the question, and refuses if not.

Default ``NoopJudge`` (always answerable) keeps behavior unchanged. ``LlmAnswerabilityJudge``
uses the existing LLM gateway — so it runs on the local Ollama today and improves with the
in-house model later (same code, swap via env). Quality is model-dependent; measure with eval.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.services.llm_gateway import ContextBlock, LLMGateway


class AnswerabilityJudge(Protocol):
    name: str

    def is_answerable(self, question: str, context: Sequence["ContextBlock"]) -> bool:
        ...


class NoopJudge:
    """Always answerable — the default (no behavior change)."""

    name = "none"

    def is_answerable(self, question: str, context: Sequence["ContextBlock"]) -> bool:
        return True


class LlmAnswerabilityJudge:
    """Delegates the YES/NO verdict to the LLM gateway. Fails open (answerable) when
    the gateway returns no verdict, so a judge outage never blocks a valid answer."""

    name = "llm"

    def __init__(self, gateway: "LLMGateway") -> None:
        self._gateway = gateway

    def is_answerable(self, question: str, context: Sequence["ContextBlock"]) -> bool:
        verdict = self._gateway.judge_answerable(question=question, context=tuple(context))
        return True if verdict is None else verdict


@lru_cache
def get_judge() -> AnswerabilityJudge:
    from app.core.config import get_settings

    if get_settings().judge_backend == "llm":
        from app.services.llm_gateway import get_gateway

        return LlmAnswerabilityJudge(get_gateway())
    return NoopJudge()
