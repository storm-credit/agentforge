# PII Masking (slice 4/4)

Opt-in, deterministic regex redaction layer on the run **output** surfaces. Defense-in-depth —
NOT a complete PII detector.

## What it does
- `app/domain/pii.py` `mask_pii(text) -> (masked, changed)` redacts: Korean RRN (`######-#######`),
  email, Korean mobile (`01X-####-####` and no-separator), 16-digit card numbers. Each match →
  `[REDACTED:<LABEL>]`.
- Applied in `app/api/v1/runs.py` when `AGENT_FORGE_PII_MASKING_ENABLED=true` (default **false** = no
  behavior change):
  - `Run.answer` (masked before persist → covers POST and the GET re-fetch).
  - `citations[].title` / `citations[].citation_locator` (heading-derived → can carry PII).
  - `GET /runs/{id}/retrieval-hits`: chunk `content`, `title`, `citation_locator`.
  - `guardrail.pii_masked` reflects whether anything was redacted.

## Config
`AGENT_FORGE_PII_MASKING_ENABLED` (bool, default `false`), pydantic-settings under prefix
`AGENT_FORGE_`.

## Limits (honest)
- Regex is **deterministic but not exhaustive**: natural-language PII (names, addresses), uncommon
  formats, `+82` international phone, dot-separated numbers, and dash-less RRN are **not** caught.
  LLM-based PII detection is out of scope (needs an in-house model — non-code dependency).
- Account numbers are not masked (format too variable → false-positive risk).
- Conservative patterns chosen to keep false positives low.

## Verification (2026-06-15)
- Unit tests (`tests/test_pii_masking.py`): 7 — RRN/email/phone/card masked, clean text unchanged,
  multi-PII, empty-safe.
- Contract tests (`tests/test_runtime_contracts.py`): answer masked when enabled / unmasked when
  disabled (`guardrail.pii_masked` reflects it); retrieval-hit content masked; **citation
  title/locator masked** (regression for the residual-leak found in security review).
- Full suite (.env aside): **102 passed, 0 skipped**. ruff clean.
- security-review: 2 high-confidence residual-leak findings (sibling `title`/`citation_locator` leaked
  while `answer`/`content` were masked) — **both fixed** and covered by the regression test.
- **Live (real Qdrant + bge-m3, flag on):** uploaded a doc with `hong@corp.com` + `010-1234-5678`;
  `GET /retrieval-hits` returned `Contact [REDACTED:EMAIL] or call [REDACTED:PHONE] ...`,
  `guardrail.pii_masked=true`, zero leak across content/locator/title. Regex match is deterministic.
