"""Deterministic grounding check for the output guard.

Measures how much of an answer is lexically supported by the retrieved context.
A hijacked/hallucinated answer (e.g. a prompt-injection "PWNED") shares almost
nothing with the Korean policy context and scores near zero, while a grounded
answer that quotes or paraphrases the context scores high. Language-robust for
Korean via prefix matching (particle suffixes are ignored).
"""

from __future__ import annotations

_PUNCT = ".,!?;:()[]{}\"'`…·-—/／<>《》「」『』*#"


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in text.casefold().split():
        stripped = raw.strip(_PUNCT)
        if len(stripped) >= 2:
            tokens.append(stripped)
    return tokens


def grounding_score(answer: str, context: str) -> float:
    """Fraction of answer tokens supported by the context (0.0–1.0).

    A token counts as grounded when any prefix of length >= 2 appears in the
    context as a substring (so an inflected "휴가를" matches "휴가"). An answer
    with no scoreable tokens (empty/whitespace) returns 1.0 (not penalized).
    """
    tokens = _tokens(answer)
    if not tokens:
        return 1.0
    ctx = context.casefold()
    grounded = 0
    for token in tokens:
        if any(token[:n] in ctx for n in range(len(token), 1, -1)):
            grounded += 1
    return round(grounded / len(tokens), 4)
