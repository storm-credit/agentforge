# Run Trace Viewer (`/runs`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영자가 `/runs`에서 실행 내역을 보고 단계 타임라인·검색 hit(본문 포함)·ACL·degraded/거부를 확인하게 한다.

**Architecture:** 작은 백엔드 추가(`retrieval-hits` 응답에 청크 content 노출) + Next.js 클라이언트 마스터-디테일 페이지가 기존 `GET /runs[/steps,/retrieval-hits]`를 호출. 평가 점수·토큰/비용은 범위 밖.

**Tech Stack:** FastAPI/SQLAlchemy(백엔드 1파일), Next.js/React/TS(프론트), pytest(.venv), Playwright(render).

**실행 환경:** 백엔드 작업 `apps/api` + `.venv\Scripts\python.exe`. 프론트 `apps/web`, 타입체크 `npx tsc --noEmit`(셰임 문제 시 `node node_modules/...`). 브랜치 `feat/run-trace-viewer`.

---

## File Structure
- **수정** `apps/api/app/domain/schemas.py` — `RetrievalHitRead`에 `content: str | None = None`.
- **수정** `apps/api/app/api/v1/runs.py` — `list_run_retrieval_hits`가 청크 content를 조인해 반환.
- **수정** `apps/api/tests/test_runtime_contracts.py` — content 계약 테스트 추가.
- **수정** `apps/web/app/lib/api.ts` — `RunSummary/RunStep/RetrievalHit` 타입 + `listRuns/getRunSteps/getRunHits`.
- **신규** `apps/web/app/runs/page.tsx` — 마스터-디테일 뷰어.
- **수정** `apps/web/app/layout.tsx` — 네비에 "Runs".
- **신규** `apps/web/tests/runs.spec.ts` — Playwright render.

---

## Task 1: 백엔드 — retrieval-hits에 청크 content 노출

**Files:** `apps/api/app/domain/schemas.py`, `apps/api/app/api/v1/runs.py`, `apps/api/tests/test_runtime_contracts.py`

- [ ] **Step 1: 계약 테스트 추가** — `apps/api/tests/test_runtime_contracts.py` 맨 아래에 추가(기존 `client` 픽스처·헬퍼 사용; 헬퍼 시그니처는 파일 내 기존 사용처를 그대로 따를 것):
```python
def test_retrieval_hits_include_chunk_content(client):
    source = _create_source(client)
    document = _register_document(
        client, source_id=source["id"], title="Remote Work Policy",
        confidentiality_level="internal", access_groups=["all-employees"],
    )
    _index_document(client, document_id=document["id"], source_text="remote work is allowed two days per week")
    agent = _publish_agent(client, knowledge_source_id=source["id"])
    run = _create_run(client, agent_id=agent["id"], message="remote work policy")

    hits = client.get(f"/api/v1/runs/{run['id']}/retrieval-hits").json()
    assert hits, "expected at least one retrieval hit"
    # 본문(content) 키가 있고, 색인된 청크는 비어있지 않아야 한다
    assert "content" in hits[0]
    assert any(h.get("content") for h in hits)
```
> 참고: `_create_source/_register_document/_index_document/_publish_agent/_create_run` 등은 이미 파일에 존재. 실제 이름/시그니처가 다르면 같은 파일의 기존 사용처를 그대로 따른다(예: 빌더 폴백 테스트에서 쓴 헬퍼들).

- [ ] **Step 2: 실패 확인**

Run (from apps/api): `.venv\Scripts\python.exe -m pytest tests/test_runtime_contracts.py::test_retrieval_hits_include_chunk_content -q`
Expected: FAIL — 응답에 `content` 키 없음(KeyError/assert) 또는 None.

- [ ] **Step 3: 스키마 필드 추가** — `apps/api/app/domain/schemas.py`의 `RetrievalHitRead` 클래스에 `created_at` 위(또는 필드 목록 끝, `model_config` 위)에 추가:
```python
    content: str | None = None
```

- [ ] **Step 4: 핸들러 수정** — `apps/api/app/api/v1/runs.py`의 `list_run_retrieval_hits`를 교체:
```python
@router.get("/{run_id}/retrieval-hits", response_model=list[RetrievalHitRead])
def list_run_retrieval_hits(run_id: str, db: Session = Depends(get_db)) -> list[RetrievalHitRead]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    hits = list(
        db.scalars(
            select(RetrievalHit)
            .where(RetrievalHit.run_id == run_id)
            .order_by(RetrievalHit.rank_original)
        )
    )
    chunk_ids = [hit.chunk_id for hit in hits if hit.chunk_id]
    contents: dict[str, str] = {}
    if chunk_ids:
        rows = db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        contents = {row.id: row.content for row in rows}
    return [
        RetrievalHitRead.model_validate(hit).model_copy(
            update={"content": contents.get(hit.chunk_id or "")}
        )
        for hit in hits
    ]
```
NOTE: `DocumentChunk`, `RetrievalHit`, `RetrievalHitRead`, `select`, `status`, `HTTPException` are already imported in `runs.py` (confirm at top of file). `RetrievalHitRead` has `model_config = ConfigDict(from_attributes=True)` so `model_validate(hit)` reads the ORM row.

- [ ] **Step 5: 통과 + 전체 회귀**

Run (from apps/api): `.venv\Scripts\python.exe -m pytest tests/test_runtime_contracts.py::test_retrieval_hits_include_chunk_content -q` → PASS.
Then move `.env` aside and run full suite (the live `.env` leaks LLM/db into 2 tests — see project memory):
```
move .env .env.live ; .venv\Scripts\python.exe -m pytest -q ; move .env.live .env
```
Expected: 57 passed (56 + 1), 0 skipped.

- [ ] **Step 6: Commit**
```bash
git add apps/api/app/domain/schemas.py apps/api/app/api/v1/runs.py apps/api/tests/test_runtime_contracts.py
git commit -m "feat(api): expose retrieved chunk content in run retrieval-hits"
```

---

## Task 2: lib/api.ts — run 조회 헬퍼

**Files:** Modify `apps/web/app/lib/api.ts`

- [ ] **Step 1: 헬퍼/타입 추가** — 파일 끝에 추가:
```ts
export type RunSummary = {
  id: string;
  input: { message?: string };
  status: string;
  latency_ms: number;
  started_at: string | null;
  answer: string;
  citations: Array<{ title: string; citation_locator: string | null }>;
  guardrail: Record<string, unknown>;
};

export type RunStep = {
  step_order: number;
  step_type: string;
  status: string;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  latency_ms: number;
  error_code: string | null;
  error_message: string | null;
};

export type RetrievalHit = {
  rank_original: number;
  title: string;
  citation_locator: string | null;
  score_vector: number;
  used_in_context: boolean;
  used_as_citation: boolean;
  chunk_id: string | null;
  content?: string | null;
  acl_filter_snapshot: Record<string, unknown>;
};

export async function listRuns(): Promise<RunSummary[]> {
  const r = await fetch(`${API_BASE}/runs`);
  if (!r.ok) throw new Error(`list runs failed: ${r.status}`);
  return r.json();
}

export async function getRunSteps(runId: string): Promise<RunStep[]> {
  const r = await fetch(`${API_BASE}/runs/${runId}/steps`);
  if (!r.ok) throw new Error(`get steps failed: ${r.status}`);
  return r.json();
}

export async function getRunHits(runId: string): Promise<RetrievalHit[]> {
  const r = await fetch(`${API_BASE}/runs/${runId}/retrieval-hits`);
  if (!r.ok) throw new Error(`get hits failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 타입체크** — `npx tsc --noEmit` (from apps/web) → exit 0.

- [ ] **Step 3: Commit**
```bash
git add apps/web/app/lib/api.ts
git commit -m "feat(web): add run trace API helpers (runs, steps, hits)"
```

---

## Task 3: `/runs` 페이지 + 네비

**Files:** Create `apps/web/app/runs/page.tsx`; Modify `apps/web/app/layout.tsx`; Create `apps/web/tests/runs.spec.ts`

- [ ] **Step 1: Playwright 실패 테스트** `apps/web/tests/runs.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test("runs page renders heading", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
});
```

- [ ] **Step 2: 실패 확인** — `npx playwright test tests/runs.spec.ts` → FAIL(라우트 없음). (dev 서버 필요 시 컨트롤러가 처리.)

- [ ] **Step 3: 네비 항목 추가** — `apps/web/app/layout.tsx`의 `navItems`에서 `{ href: "/chat", label: "Chat" }` 다음 줄에 추가:
```tsx
  { href: "/runs", label: "Runs" },
```

- [ ] **Step 4: 페이지 구현** — `apps/web/app/runs/page.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import {
  getRunHits,
  getRunSteps,
  listRuns,
  type RetrievalHit,
  type RunStep,
  type RunSummary,
} from "../lib/api";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<RunSummary | null>(null);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [hits, setHits] = useState<RetrievalHit[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listRuns()
      .then((rs) => { setRuns(rs); if (rs.length) setSelected(rs[0]); })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    getRunSteps(selected.id).then(setSteps).catch(() => setSteps([]));
    getRunHits(selected.id).then(setHits).catch(() => setHits([]));
  }, [selected]);

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Governance</p>
        <h1>Runs</h1>
        <p>실행 단계 트레이스, 검색 근거(본문·점수·권한), 거부/강등 사유를 확인합니다.</p>
      </div>

      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      {!error && runs.length === 0 && (
        <p>아직 실행 내역이 없습니다. /chat이나 빌더 테스트에서 질문해 보세요.</p>
      )}

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* 목록 */}
        <div className="panel" style={{ flex: "1 1 280px", maxWidth: "340px" }}>
          <h3>최근 실행</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {runs.map((r) => (
              <li key={r.id} style={{ marginBottom: "6px" }}>
                <button
                  onClick={() => setSelected(r)}
                  style={{
                    width: "100%", textAlign: "left", cursor: "pointer", padding: "8px",
                    borderRadius: "6px", border: "1px solid var(--line,#cbd5e1)",
                    background: selected?.id === r.id ? "#eff6ff" : "transparent",
                  }}
                >
                  <div style={{ fontSize: "14px" }}>{r.input?.message ?? "(질문 없음)"}</div>
                  <div style={{ fontSize: "12px", color: "#64748b" }}>
                    <span className="badge">{r.status}</span> · {r.latency_ms}ms
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* 상세 */}
        <div className="panel" style={{ flex: "2 1 420px" }}>
          {!selected ? (
            <p>왼쪽에서 실행을 선택하세요.</p>
          ) : (
            <>
              <h3>답변</h3>
              <p data-testid="run-answer">{selected.answer}</p>
              {selected.citations?.length > 0 && (
                <ul>
                  {selected.citations.map((c, i) => (
                    <li key={i} style={{ fontSize: "14px" }}>{c.title} — {c.citation_locator}</li>
                  ))}
                </ul>
              )}

              <h3 style={{ marginTop: "16px" }}>단계 타임라인</h3>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {steps.map((s) => (
                  <li key={s.step_order} style={{ marginBottom: "8px" }}>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <strong>{s.step_order}. {s.step_type}</strong>
                      <span className="badge" style={{ color: s.status === "succeeded" ? "#15803d" : "#b91c1c" }}>
                        {s.status}
                      </span>
                      <span style={{ fontSize: "12px", color: "#64748b" }}>{s.latency_ms}ms</span>
                    </div>
                    {s.error_message && <div style={{ color: "#b91c1c", fontSize: "13px" }}>{s.error_code}: {s.error_message}</div>}
                    <details>
                      <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer" }}>입출력</summary>
                      <pre style={{ fontSize: "12px", whiteSpace: "pre-wrap", background: "#f8fafc", padding: "8px", borderRadius: "6px" }}>
{JSON.stringify({ input: s.input_summary, output: s.output_summary }, null, 2)}
                      </pre>
                    </details>
                  </li>
                ))}
              </ul>

              <h3 style={{ marginTop: "16px" }}>검색 근거 (hits)</h3>
              {hits.length === 0 && <p style={{ fontSize: "14px", color: "#64748b" }}>검색 결과 없음(또는 권한 거부).</p>}
              {hits.map((h, i) => (
                <article key={i} className="card" style={{ marginBottom: "8px" }}>
                  <div style={{ fontSize: "13px" }}>
                    #{h.rank_original} · {h.title} · score {h.score_vector}
                    {" "}{h.used_as_citation ? <span className="badge">인용됨</span> : <span className="badge">미인용</span>}
                  </div>
                  {h.citation_locator && <div style={{ fontSize: "12px", color: "#64748b" }}>{h.citation_locator}</div>}
                  {h.content && (
                    <details>
                      <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer" }}>본문</summary>
                      <p style={{ fontSize: "13px", whiteSpace: "pre-wrap" }}>{h.content}</p>
                    </details>
                  )}
                </article>
              ))}

              {hits[0]?.acl_filter_snapshot && (
                <details style={{ marginTop: "8px" }}>
                  <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer" }}>ACL 필터 스냅샷</summary>
                  <pre style={{ fontSize: "12px", whiteSpace: "pre-wrap", background: "#f8fafc", padding: "8px", borderRadius: "6px" }}>
{JSON.stringify(hits[0].acl_filter_snapshot, null, 2)}
                  </pre>
                </details>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: 타입체크** — `npx tsc --noEmit` (from apps/web) → exit 0.

- [ ] **Step 6: Commit**
```bash
git add apps/web/app/runs/page.tsx apps/web/app/layout.tsx apps/web/tests/runs.spec.ts
git commit -m "feat(web): Run Trace Viewer page with step timeline + hits (content/ACL)"
```

---

## Task 4: 라이브 수동 검증 — 컨트롤러 직접 수행

**Files:** 없음(검증).

- [ ] **Step 1: 스택** — API :8000(qdrant 백엔드, agentforge_mvp2), Qdrant, Ollama(bge-m3/qwen3) 기동. 웹 dev :3300.
- [ ] **Step 2: Playwright** — `apps/web`에서 `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3300`로 `node node_modules/@playwright/test/cli.js test tests/runs.spec.ts` → PASS.
- [ ] **Step 3: 화면** — `/runs` 진입 → 이번 세션 run들(휴가/연차/출장비/거부 등) 목록 표시. 하나 클릭 → 단계 타임라인(generator `mode=llm`, retriever `vector_adapter=qdrant`/`degraded`), hit 표에 **점수·인용여부·본문**, ACL 스냅샷. 거부 run 선택 시 거부 답변 + denied 표시.
- [ ] **Step 4: Preview 스크린샷**(가능 시).

---

## Self-Review (작성자 확인)
- **스펙 커버리지:** §2 백엔드 content(Task1) / §3 헬퍼(Task2) / §3 네비·페이지(Task3) / §4 화면(타임라인·hit본문·ACL: Task3) / §5 빈상태·에러(Task3) / §6 테스트(Task1 계약 + Task3 Playwright + Task4 수동) — 모두 매핑.
- **플레이스홀더:** 모든 코드 스텝 완전. TODO 없음.
- **타입 일관성:** `RunSummary/RunStep/RetrievalHit`(Task2)가 Task3 사용과 일치. 백엔드 `content` 필드(Task1 schema)가 프론트 `RetrievalHit.content`(Task2)와 일치. `data-testid="run-answer"`·heading "Runs"가 테스트와 일치. import 경로 `../lib/api`는 `app/runs/page.tsx`에서 정확.
- **주의:** `list_run_retrieval_hits` 반환을 ORM→`RetrievalHitRead` 명시 생성으로 바꿈(content 주입). `model_copy(update=...)`는 pydantic v2 API(프로젝트 pydantic>=2.8).
