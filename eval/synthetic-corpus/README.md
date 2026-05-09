# Synthetic Corpus v0.1

This folder contains machine-readable D3 evidence for QA, RAG, and Security work.

The corpus uses only synthetic document IDs and synthetic questions. It is safe to run in
development, CI, and closed-network smoke environments without exposing real internal data.

## Files

| File | Purpose |
|---|---|
| `case.schema.json` | JSON Schema for corpus and eval cases |
| `cases-v0.1.json` | Initial 30-case ACL/citation/refusal/safety set |

## Suites

| Suite | Count | Purpose |
|---|---:|---|
| `rag-core` | 8 | General policy Q&A grounding |
| `citation` | 6 | Citation locator and answer support |
| `acl` | 8 | Allowed/blocked principal behavior |
| `refusal` | 5 | No-grounding, out-of-scope, or permission refusal |
| `safety` | 3 | Prompt injection and sensitive output handling |

## Use

Sprint 1 should wire these cases into a deterministic scorer:

- forbidden citations never appear in retrieval, context, answer, or citation output
- expected citations overlap with selected citation IDs
- expected refusal or policy-denied behavior is respected
- every run produces trace and audit evidence

