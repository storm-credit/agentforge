# AgentForge MVP — Employee Chat Answer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire a real Qwen3 answer into the existing run pipeline (replacing the synthetic stub) so an employee can ask a question and get an ACL-respecting, cited answer in Korean or English, with a minimal chat UI.

**Architecture:** Add an env-driven, OpenAI-compatible LLM gateway (local Ollama `qwen3:8b` → on-prem vLLM `Qwen3.6:35B`, swap by env only). `runs.py` loads the retrieved chunk text, calls the gateway with a context-only/cite/refuse prompt in the resolved language, and keeps the existing citation-validation gate and run/step/audit recording. Retrieval stays the existing FakeVectorStore. A minimal Next.js chat page with a mock department selector and KO/EN toggle calls `POST /api/v1/runs`.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy (sync) / httpx; Next.js 15 / React 19 / TypeScript; Ollama (local) / vLLM (on-prem); pytest; Playwright.

**Test runner:** always `apps/api/.venv/Scripts/python.exe -m pytest` (the Python 3.11 venv; the global 3.14 lacks sqlalchemy so contract tests silently skip).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `apps/api/app/core/config.py` (modify) | Add `llm_base_url`, `llm_model`, `llm_timeout_seconds` settings |
| `apps/api/app/services/__init__.py` (create) | package marker |
| `apps/api/app/services/llm_gateway.py` (create) | OpenAI-compatible chat client; health; prompt build; language resolve; offline fallback |
| `apps/api/app/domain/language.py` (create) | `resolve_language(language, question)` (auto-detect KO/EN) |
| `apps/api/app/domain/schemas.py` (modify) | `RunCreate.language: Literal["auto","ko","en"] = "auto"` |
| `apps/api/app/api/v1/runs.py` (modify) | Replace `_build_synthetic_answer` with gateway-backed generation + context loading |
| `apps/api/app/seed_demo.py` (create) | Seed one agent + published version + knowledge source + indexed sample doc |
| `apps/api/tests/test_llm_gateway_contracts.py` (create) | Gateway unit tests (mocked httpx) |
| `apps/api/tests/test_language.py` (create) | Language resolution tests |
| `apps/api/tests/test_runtime_contracts.py` (modify) | Add LLM-answer + refuse + fallback run tests |
| `apps/api/tests/test_seed_demo.py` (create) | Seed produces searchable chunks |
| `apps/web/app/chat/page.tsx` (create) | Minimal chat UI (mock dept selector, KO/EN toggle, citations) |
| `apps/web/app/lib/api.ts` (create) | API base URL + run request helper |
| `apps/web/tests/chat.spec.ts` (create) | Playwright smoke |

---

## Task 0: Local LLM runtime (Ollama + qwen3:8b)

Not TDD — environment setup. RTX 4070 Ti has 12GB VRAM, so use a quantized 8B (Q4) which needs ~5–6GB.

- [ ] **Step 1: Install Ollama (Windows)**

Download and install from https://ollama.com/download (or `winget install Ollama.Ollama`). Verify in a new shell:
Run: `ollama --version`
Expected: prints a version (e.g., `ollama version 0.x`).

- [ ] **Step 2: Pull the quantized pilot model**

Run: `ollama pull qwen3:8b`
Expected: download completes; `ollama list` shows `qwen3:8b`.

- [ ] **Step 3: Verify the OpenAI-compatible endpoint**

Run: `curl http://localhost:11434/v1/models`
Expected: JSON listing `qwen3:8b`. (Ollama serves `/v1/...` OpenAI-compatible.)

- [ ] **Step 4: Record env for the API**

Add to `apps/api/.env` (gitignored):
```
AGENT_FORGE_LLM_BASE_URL=http://localhost:11434/v1
AGENT_FORGE_LLM_MODEL=qwen3:8b
AGENT_FORGE_LLM_TIMEOUT_SECONDS=30
```
(On-prem later: set these to the vLLM endpoint + `Qwen3.6:35B`. No code change.)

---

## Task 1: LLM gateway

**Files:**
- Modify: `apps/api/app/core/config.py`
- Create: `apps/api/app/services/__init__.py`, `apps/api/app/services/llm_gateway.py`
- Test: `apps/api/tests/test_llm_gateway_contracts.py`

- [ ] **Step 1: Add settings**

In `apps/api/app/core/config.py`, add to `Settings` (after `cors_origins`):
```python
    llm_base_url: str | None = None
    llm_model: str = "qwen3:8b"
    llm_timeout_seconds: float = 30.0
```
(env: `AGENT_FORGE_LLM_BASE_URL`, etc. — picked up automatically by the existing prefix.)

- [ ] **Step 2: Write the failing gateway test**

Create `apps/api/tests/test_llm_gateway_contracts.py`:
```python
import httpx
import pytest

from app.services.llm_gateway import ContextBlock, LLMGateway, build_messages

CTX = (ContextBlock(title="Holiday Policy", locator="Holiday Policy / lines 1-3", content="Five days paid leave per year."),)


def test_no_base_url_uses_fallback():
    gw = LLMGateway(base_url=None, model="qwen3:8b", timeout_seconds=5)
    result = gw.generate(question="휴가 며칠?", context=CTX, language="ko")
    assert result.used_llm is False
    assert result.fallback_used is True
    assert result.text  # non-empty template


def test_empty_context_refuses_without_calling_llm():
    gw = LLMGateway(base_url="http://x/v1", model="m", timeout_seconds=5)
    result = gw.generate(question="무엇?", context=(), language="ko")
    assert result.used_llm is False
    assert "근거" in result.text or "no" in result.text.lower()


def test_generate_calls_openai_endpoint(monkeypatch):
    captured = {}

    def fake_post(self, url, json, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>x</think>5 days."}}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    gw = LLMGateway(base_url="http://x/v1", model="qwen3:8b", timeout_seconds=5)
    result = gw.generate(question="leave days?", context=CTX, language="en")
    assert result.used_llm is True
    assert result.text == "5 days."  # <think> stripped
    assert captured["url"].endswith("/chat/completions")
    assert captured["json"]["model"] == "qwen3:8b"


def test_http_error_falls_back(monkeypatch):
    def boom(self, url, json, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.Client, "post", boom)
    gw = LLMGateway(base_url="http://x/v1", model="m", timeout_seconds=5)
    result = gw.generate(question="q", context=CTX, language="en")
    assert result.fallback_used is True


def test_build_messages_sets_language_and_context():
    msgs = build_messages(question="q", context=CTX, language="ko")
    assert msgs[0]["role"] == "system"
    assert "한국어" in msgs[0]["content"]
    assert "Holiday Policy / lines 1-3" in msgs[1]["content"]
```

- [ ] **Step 3: Run it to verify it fails**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_llm_gateway_contracts.py -q`
Expected: FAIL (module `app.services.llm_gateway` not found).

- [ ] **Step 4: Implement the gateway**

Create `apps/api/app/services/__init__.py` (empty). Create `apps/api/app/services/llm_gateway.py`:
```python
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_LANG_NAME = {"ko": "한국어", "en": "English"}


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
                        "temperature": 0.2,
                        "messages": build_messages(question=question, context=context, language=language),
                    },
                )
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                return GeneratedAnswer(text=_THINK.sub("", content).strip(), used_llm=True, fallback_used=False)
        except Exception:
            return GeneratedAnswer(text=_fallback(context, language), used_llm=False, fallback_used=True)


def get_gateway() -> LLMGateway:
    s = get_settings()
    return LLMGateway(base_url=s.llm_base_url, model=s.llm_model, timeout_seconds=s.llm_timeout_seconds)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_llm_gateway_contracts.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/core/config.py apps/api/app/services apps/api/tests/test_llm_gateway_contracts.py
git commit -m "feat(api): add env-driven OpenAI-compatible LLM gateway with fallback"
```

---

## Task 2: Language resolution

**Files:**
- Create: `apps/api/app/domain/language.py`
- Test: `apps/api/tests/test_language.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_language.py`:
```python
from app.domain.language import resolve_language


def test_explicit_language_wins():
    assert resolve_language("en", "안녕하세요") == "en"
    assert resolve_language("ko", "hello") == "ko"


def test_auto_detects_korean_by_hangul():
    assert resolve_language("auto", "휴가 며칠 남았나요?") == "ko"


def test_auto_defaults_english_without_hangul():
    assert resolve_language("auto", "How many leave days?") == "en"
```

- [ ] **Step 2: Run to verify it fails**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_language.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

Create `apps/api/app/domain/language.py`:
```python
def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def resolve_language(language: str, question: str) -> str:
    if language in ("ko", "en"):
        return language
    return "ko" if _has_hangul(question) else "en"
```

- [ ] **Step 4: Run to verify it passes**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_language.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/domain/language.py apps/api/tests/test_language.py
git commit -m "feat(api): add KO/EN language resolution (auto-detect + override)"
```

---

## Task 3: Wire real answer into the run pipeline

**Files:**
- Modify: `apps/api/app/domain/schemas.py` (add `RunCreate.language`)
- Modify: `apps/api/app/api/v1/runs.py:135` (replace synthetic answer; load chunk context; set generator mode)
- Test: `apps/api/tests/test_runtime_contracts.py`

- [ ] **Step 1: Add the language field to RunCreate**

In `apps/api/app/domain/schemas.py`, change the `RunCreate` class to add (keep all existing fields):
```python
from typing import Any, Literal  # ensure Literal imported at top
```
and inside `RunCreate`:
```python
    language: Literal["auto", "ko", "en"] = "auto"
```

- [ ] **Step 2: Write failing run tests**

In `apps/api/tests/test_runtime_contracts.py`, add (the file already has a `client` fixture + helpers to create agent/version/source/document/index — reuse them; if a helper to build an indexed doc does not exist, build one inline mirroring `test_metadata_contracts.py`):
```python
def test_run_uses_llm_answer_when_gateway_returns(client, monkeypatch):
    from app.services import llm_gateway

    def fake_generate(self, *, question, context, language):
        assert len(context) >= 1  # authorized chunk passed through
        return llm_gateway.GeneratedAnswer(text=f"[{language}] answer", used_llm=True, fallback_used=False)

    monkeypatch.setattr(llm_gateway.LLMGateway, "generate", fake_generate)

    ids = _seed_agent_with_indexed_doc(client)  # helper: returns {"agent_id":..., "source_id":...}
    resp = client.post(
        "/api/v1/runs",
        json={"agent_id": ids["agent_id"], "input": {"message": "휴가 며칠?"},
              "knowledge_source_ids": [ids["source_id"]], "language": "auto"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["answer"] == "[ko] answer"
    assert len(body["citations"]) >= 1


def test_run_refuses_when_no_authorized_context(client, monkeypatch):
    from app.services import llm_gateway
    # principal with no matching groups sees nothing -> empty context -> refusal
    ids = _seed_agent_with_indexed_doc(client)
    resp = client.post(
        "/api/v1/runs",
        headers={"X-Agent-Forge-Groups": "nobody", "X-Agent-Forge-Clearance": "public"},
        json={"agent_id": ids["agent_id"], "input": {"message": "휴가 며칠?"},
              "knowledge_source_ids": [ids["source_id"]], "language": "ko"},
    )
    assert resp.status_code == 201
    assert resp.json()["citations"] == []
    assert "문서" in resp.json()["answer"]  # refusal text


def test_run_falls_back_when_llm_unconfigured(client):
    # No AGENT_FORGE_LLM_BASE_URL in tests -> gateway fallback, but still a non-empty answer
    ids = _seed_agent_with_indexed_doc(client)
    resp = client.post(
        "/api/v1/runs",
        json={"agent_id": ids["agent_id"], "input": {"message": "leave days?"},
              "knowledge_source_ids": [ids["source_id"]], "language": "en"},
    )
    assert resp.status_code == 201
    assert resp.json()["answer"]
```
Add the helper near the top of the test module if missing:
```python
def _seed_agent_with_indexed_doc(client):
    source = client.post("/api/v1/knowledge/sources", json={
        "name": "Runtime Corpus", "description": "x", "owner_department": "Operations"}).json()
    agent = client.post("/api/v1/agents", json={
        "name": "Helpdesk", "purpose": "answer", "owner_department": "Operations"}).json()
    version = client.post("/api/v1/agents/versions", json={
        "agent_id": agent["id"], "version": 1, "config": {"citation_required": True}}).json()
    client.post(f"/api/v1/agents/versions/{version['id']}/validate", json={})
    client.post(f"/api/v1/agents/versions/{version['id']}/publish", json={})
    doc = client.post("/api/v1/knowledge/documents", json={
        "knowledge_source_id": source["id"], "title": "Holiday Policy",
        "object_uri": "object://holiday.md", "checksum": "sha256-x", "mime_type": "text/markdown",
        "confidentiality_level": "internal", "access_groups": ["all-employees"],
        "effective_date": "2026-05-10"}).json()
    client.post(f"/api/v1/knowledge/documents/{doc['id']}/index-jobs",
                json={"source_text": "# 휴가\n\n연 5일 유급 휴가가 제공됩니다."})
    return {"agent_id": agent["id"], "source_id": source["id"]}
```
> NOTE: confirm the exact agent/version endpoint paths against `apps/api/app/api/v1/agents.py` before running; adjust the helper to match (e.g., validate/publish route shapes).

- [ ] **Step 3: Run to verify failure**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_runtime_contracts.py -q`
Expected: FAIL (answer is the old synthetic string / language field rejected).

- [ ] **Step 4: Implement the generation swap**

In `apps/api/app/api/v1/runs.py`:

(a) Add imports near the top:
```python
from app.domain.models import DocumentChunk  # add to existing models import line
from app.domain.language import resolve_language
from app.services.llm_gateway import ContextBlock, get_gateway
```

(b) Replace line 135 (`run.answer = _build_synthetic_answer(len(citations))`) with:
```python
    answer_language = resolve_language(payload.language, payload.input.message)
    context_blocks = _load_context_blocks(db, vector_result.hits)
    generated = get_gateway().generate(
        question=payload.input.message, context=context_blocks, language=answer_language
    )
    run.answer = generated.text
```

(c) In the order=3 "generator" step, change `output_summary` `"mode": "synthetic"` to:
```python
            "mode": "llm" if generated.used_llm else ("fallback" if generated.fallback_used else "refused"),
            "language": answer_language,
```

(d) Replace `_build_synthetic_answer` (lines 370-374) with a context loader:
```python
def _load_context_blocks(db: Session, hits) -> tuple[ContextBlock, ...]:
    chunk_ids = [hit.chunk_id for hit in hits if hit.chunk_id]
    contents: dict[str, str] = {}
    if chunk_ids:
        rows = db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        contents = {row.id: row.content for row in rows}
    blocks = []
    for hit in hits:
        text = contents.get(hit.chunk_id or "", "")
        if not text:
            continue
        blocks.append(ContextBlock(title=hit.title, locator=hit.citation_locator or hit.citation, content=text))
    return tuple(blocks)
```

- [ ] **Step 5: Run to verify pass**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_runtime_contracts.py -q`
Expected: PASS (new tests + existing runtime tests still green).

- [ ] **Step 6: Run the full API suite (no regressions)**

Run: `apps/api/.venv/Scripts/python.exe -m pytest -q`
Expected: all pass, 0 skips.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/api/v1/runs.py apps/api/app/domain/schemas.py apps/api/tests/test_runtime_contracts.py
git commit -m "feat(api): generate cited answers via LLM gateway (context-only, KO/EN, refuse)"
```

---

## Task 4: Seed one demo agent + indexed document

**Files:**
- Create: `apps/api/app/seed_demo.py`
- Test: `apps/api/tests/test_seed_demo.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_seed_demo.py`:
```python
from app.seed_demo import seed_demo


def test_seed_creates_published_agent_and_indexed_chunks(db_session):
    result = seed_demo(db_session)
    assert result["agent_id"]
    assert result["agent_version_id"]
    assert result["source_id"]
    assert result["chunk_count"] >= 1
```
> Use the same in-memory `db_session` fixture style as the other contract tests (SQLite + `Base.metadata.create_all`). If only a `client` fixture exists, add a `db_session` fixture mirroring it.

- [ ] **Step 2: Run to verify failure**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_seed_demo.py -q`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement seed_demo**

Create `apps/api/app/seed_demo.py`:
```python
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.indexing import run_index_job
from app.domain.models import Agent, AgentVersion, Document, IndexJob, KnowledgeSource

_PRINCIPAL = Principal(user_id="seed", department="Operations", roles=("admin",),
                       groups=("all-employees",), clearance_level="internal")
_SAMPLE = "# 휴가 정책\n\n전 직원은 연 5일의 유급 휴가를 사용할 수 있습니다.\n\n## 신청\n\n관리자 승인 후 사용합니다."


def seed_demo(db: Session) -> dict:
    source = KnowledgeSource(name="사내 정책", description="데모", owner_department="Operations")
    db.add(source); db.flush()
    agent = Agent(name="사내 도우미", purpose="사내 문서 질의응답", owner_department="Operations", status="published")
    db.add(agent); db.flush()
    version = AgentVersion(agent_id=agent.id, version=1, status="published",
                           config={"citation_required": True, "knowledge_source_ids": [source.id]},
                           created_by="seed")
    db.add(version); db.flush()
    document = Document(knowledge_source_id=source.id, title="휴가 정책",
                        object_uri="object://seed/holiday.md", checksum="sha256-seed",
                        mime_type="text/markdown", confidentiality_level="internal",
                        access_groups=["all-employees"], status="registered", effective_date="2026-05-10")
    db.add(document); db.flush()
    job = IndexJob(document_id=document.id, status="queued", stage="parse",
                   config={"parser_profile": "default-txt-md", "chunking": {"chunk_size": 900},
                           "embedding_model": "none-smoke", "force_reindex": False, "source": "seed"},
                   created_by="seed")
    db.add(job); db.flush()
    run_index_job(db=db, document=document, job=job, source_text=_SAMPLE, principal=_PRINCIPAL)
    db.commit()
    return {"agent_id": agent.id, "agent_version_id": version.id, "source_id": source.id,
            "chunk_count": job.chunk_count}


if __name__ == "__main__":  # python -m app.seed_demo (against the real DB)
    from app.core.database import SessionLocal  # adjust to the project's session factory name
    with SessionLocal() as session:
        print(seed_demo(session))
```
> Confirm the session factory import in `app/core/database.py` (name may differ); adjust the `__main__` block accordingly.

- [ ] **Step 4: Run to verify pass**

Run: `apps/api/.venv/Scripts/python.exe -m pytest tests/test_seed_demo.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/seed_demo.py apps/api/tests/test_seed_demo.py
git commit -m "feat(api): seed a demo agent + indexed policy doc for chat MVP"
```

---

## Task 5: Minimal chat UI

**Files:**
- Create: `apps/web/app/lib/api.ts`, `apps/web/app/chat/page.tsx`
- Test: `apps/web/tests/chat.spec.ts`

- [ ] **Step 1: API helper**

Create `apps/web/app/lib/api.ts`:
```ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const MOCK_USERS = {
  finance: { "X-Agent-Forge-User": "fin1", "X-Agent-Forge-Department": "Finance", "X-Agent-Forge-Groups": "all-employees", "X-Agent-Forge-Clearance": "internal" },
  hr: { "X-Agent-Forge-User": "hr1", "X-Agent-Forge-Department": "HR", "X-Agent-Forge-Groups": "all-employees,hr-restricted", "X-Agent-Forge-Clearance": "restricted" },
} as const;

export type MockUserKey = keyof typeof MOCK_USERS;

export async function firstAgentId(): Promise<string | null> {
  const r = await fetch(`${API_BASE}/agents`);
  const list = await r.json();
  return list[0]?.id ?? null;
}

export async function ask(params: {
  agentId: string; message: string; language: "auto" | "ko" | "en"; user: MockUserKey;
}) {
  const r = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...MOCK_USERS[params.user] },
    body: JSON.stringify({ agent_id: params.agentId, input: { message: params.message }, language: params.language }),
  });
  if (!r.ok) throw new Error(`run failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: Chat page**

Create `apps/web/app/chat/page.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import { ask, firstAgentId, type MockUserKey } from "../lib/api";

export default function ChatPage() {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [user, setUser] = useState<MockUserKey>("finance");
  const [language, setLanguage] = useState<"auto" | "ko" | "en">("auto");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { firstAgentId().then(setAgentId); }, []);

  async function onAsk() {
    if (!agentId || !message) return;
    setLoading(true);
    try {
      const run = await ask({ agentId, message, language, user });
      setAnswer(run.answer);
      setCitations(run.citations ?? []);
    } catch (e) { setAnswer(String(e)); } finally { setLoading(false); }
  }

  return (
    <section className="page">
      <h1>Chat</h1>
      <div>
        <label>사용자(부서): </label>
        <select value={user} onChange={(e) => setUser(e.target.value as MockUserKey)}>
          <option value="finance">Finance</option>
          <option value="hr">HR</option>
        </select>
        <label> 언어: </label>
        <select value={language} onChange={(e) => setLanguage(e.target.value as any)}>
          <option value="auto">자동</option><option value="ko">한국어</option><option value="en">English</option>
        </select>
      </div>
      <textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="질문을 입력하세요" rows={3} />
      <button onClick={onAsk} disabled={loading || !agentId}>{loading ? "..." : "질문"}</button>
      {answer && <article className="card"><h3>답변</h3><p data-testid="answer">{answer}</p>
        <h4>출처</h4><ul>{citations.map((c, i) => <li key={i}>{c.title} — {c.citation_locator}</li>)}</ul>
      </article>}
    </section>
  );
}
```

- [ ] **Step 3: Playwright smoke**

Create `apps/web/tests/chat.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test("chat page renders controls", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await expect(page.getByPlaceholder("질문을 입력하세요")).toBeVisible();
});
```

- [ ] **Step 4: Run the smoke (web dev server running)**

Run (from `apps/web`, with `npm run dev` up): `npm run test:e2e -- chat.spec.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/lib/api.ts apps/web/app/chat/page.tsx apps/web/tests/chat.spec.ts
git commit -m "feat(web): minimal chat page with mock-user selector, KO/EN toggle, citations"
```

---

## End-to-End Verification

- [ ] **API regression:** `apps/api/.venv/Scripts/python.exe -m pytest -q` → all pass, 0 skips.
- [ ] **eval harness:** `python -m pytest eval/harness/tests/ -q` → green (ACL/citation/refusal quality unchanged).
- [ ] **Live local loop:** start Ollama (`qwen3:8b`), seed (`python -m app.seed_demo`), run API + web, open `/chat`:
  - Finance user asks "휴가 며칠?" → Korean answer with a citation locator.
  - Same question with English toggle → English answer.
  - A user/group with no access → refusal, no citations.
- [ ] **On-prem dry-run:** set `AGENT_FORGE_LLM_BASE_URL` to the vLLM endpoint and `AGENT_FORGE_LLM_MODEL=Qwen3.6:35B`, re-run the live loop (no code change), re-check eval scores.

---

## Notes for the implementer
- Always use the `.venv` python for API tests (global 3.14 skips them).
- Do not push; commit locally unless asked.
- Before Task 3's test helper, confirm the exact agent/version endpoint paths in `apps/api/app/api/v1/agents.py` and the session factory name in `app/core/database.py`, and adjust those two spots.
- Retrieval stays FakeVectorStore; if eval answer quality is poor on 8B, real embeddings are a separate follow-up plan (out of scope here).
