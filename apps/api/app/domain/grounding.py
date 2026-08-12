"""Deterministic lexical-overlap check for the output guard.

Measures how much of an answer is lexically supported by the retrieved context:
the fraction of answer tokens that appear (via >=2-char prefix substring match)
in the context string. Language-robust for Korean via prefix matching (particle
suffixes are ignored).

This is a lexical-overlap indicator, not a grounding/faithfulness guarantee, and
it is defeated by construction for document-borne prompt injection: when the
injected instruction is copied into the answer, the *context* it is compared
against is the attacker's own uploaded document, so the attacker controls both
operands being compared. A payload string echoed verbatim out of a poisoned
context therefore scores 1.0, and no AGENT_FORGE_GROUNDING_MIN threshold in
[0, 1] can trip on that case (see test_grounding.py's poisoned-context test and
docs/40-delivery/live-demo-evidence-2026-08-12.md section 5). This score only
distinguishes a hijacked answer from a clean context when the injected text is
*absent* from that context (e.g. a user-turn injection with no matching
document) -- it provides no protection when the answer and the context share
an attacker-authored origin.

Two additional fail-open behaviours, kept exactly as measured: tokens shorter
than 2 characters are dropped entirely (never scored either way), and an
answer with no scoreable tokens (empty, whitespace-only, or all short tokens)
returns 1.0 -- not penalized. A bare "예" is therefore never flagged by this
guard regardless of context.
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
