"""Deterministic regex-based PII masking for output surfaces.

Conservative by design: only patterns with low false-positive risk are masked
(Korean RRN, email, Korean mobile numbers, 16-digit card numbers). This is a
defense-in-depth redaction layer, NOT a complete PII detector — natural-language
PII (names, addresses) and uncommon formats are NOT caught. LLM-based detection
is out of scope (depends on an in-house model).
"""

from __future__ import annotations

import re

# Order matters: more specific / longer patterns first so they win the span.
# Each entry is (label, compiled pattern).
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Korean resident registration number: YYMMDD-NNNNNNN
    ("RRN", re.compile(r"\b\d{6}-\d{7}\b")),
    # Email
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # 16-digit card number in 4 groups (optional separators)
    ("CARD", re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b")),
    # Korean mobile: 010/011/016-019, optional separators, 3-4 then 4 digits
    ("PHONE", re.compile(r"\b01[0-9][- ]?\d{3,4}[- ]?\d{4}\b")),
)


def mask_pii(text: str | None) -> tuple[str, bool]:
    """Redact known PII patterns in ``text``.

    Returns the (possibly) masked text and a flag indicating whether anything
    was redacted. ``None``/empty input is returned unchanged with ``False``.
    """
    if not text:
        return text or "", False

    masked = text
    changed = False
    for label, pattern in _PATTERNS:
        masked, count = pattern.subn(f"[REDACTED:{label}]", masked)
        if count:
            changed = True
    return masked, changed
