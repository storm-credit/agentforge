from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_LANG_NAME = {"ko": "한국어", "en": "English"}
_TEMPERATURE = 0.2


@dataclass(frozen=True)
class ContextBlock:
    title: str
    locator: str
    content: str


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    used_llm: bool
    fallback_used: bool


def build_messages(*, question: str, context: tuple[ContextBlock, ...], language: str) -> list[dict]:
    lang_name = _LANG_NAME.get(language, "한국어")
    blocks = "\n\n".join(
        f"[{i + 1}] {b.title} ({b.locator})\n{b.content}" for i, b in enumerate(context)
    )
    system = (
        "/no_think\n"
        f"You are an internal company assistant. Answer ONLY using the provided context. "
        f"Do not use outside knowledge. Cite the source locator(s) you used. "
        f"If the context is insufficient, say you cannot answer from the available documents. "
        f"Answer in {lang_name}."
    )
    user = f"Question:\n{question}\n\nContext:\n{blocks}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _refusal(language: str) -> str:
    if language == "en":
        return "I couldn't find authorized documents to answer this question."
    return "이 질문에 답할 수 있는 권한 있는 문서를 찾지 못했습니다."


def _fallback(context: tuple[ContextBlock, ...], language: str) -> str:
    if not context:
        return _refusal(language)
    locators = ", ".join(b.locator for b in context)
    if language == "en":
        return f"(LLM offline) Relevant sources: {locators}."
    return f"(LLM 미연결) 관련 출처: {locators}."


class LLMGateway:
    """Gateway to an OpenAI-compatible chat endpoint.

    base_url must include the OpenAI version prefix, e.g. ``http://host:11434/v1``.
    """

    def __init__(self, base_url: str | None, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.timeout_seconds = timeout_seconds

    def health(self) -> dict:
        if not self.base_url:
            return {"configured": False, "model": self.model}
        try:
            with httpx.Client(timeout=min(self.timeout_seconds, 5.0)) as client:
                r = client.get(f"{self.base_url}/models")
                r.raise_for_status()
                return {"configured": True, "status": "ok", "model": self.model}
        except Exception as exc:
            return {"configured": True, "status": "unreachable", "error": str(exc)}

    def generate(
        self, *, question: str, context: tuple[ContextBlock, ...], language: str
    ) -> GeneratedAnswer:
        if not context:
            return GeneratedAnswer(text=_refusal(language), used_llm=False, fallback_used=False)
        if not self.base_url:
            return GeneratedAnswer(text=_fallback(context, language), used_llm=False, fallback_used=True)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                r = client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "temperature": _TEMPERATURE,
                        "messages": build_messages(question=question, context=context, language=language),
                    },
                )
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                return GeneratedAnswer(text=_THINK.sub("", content).strip(), used_llm=True, fallback_used=False)
        except Exception as exc:
            logger.warning("LLM call failed, using fallback: %s", exc)
            return GeneratedAnswer(text=_fallback(context, language), used_llm=False, fallback_used=True)


def get_gateway() -> LLMGateway:
    s = get_settings()
    return LLMGateway(base_url=s.llm_base_url, model=s.llm_model, timeout_seconds=s.llm_timeout_seconds)
