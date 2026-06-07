# 문서 업로드/인제스트 (TXT/MD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영자가 `/knowledge`에서 TXT/MD 문서를 업로드/붙여넣어 지식소스에 추가하면 실제 bge-m3 임베딩으로 Qdrant에 색인되게 한다.

**Architecture:** Next.js 클라이언트 페이지(`/knowledge`)가 기존 API(`POST /knowledge/sources`, `POST /knowledge/documents`, `POST /knowledge/documents/{id}/index-jobs` with `source_text`)를 `lib/api.ts` 헬퍼로 호출. 백엔드 무변경. 파일은 브라우저 `FileReader`로 텍스트만 읽어 전송(객체저장 없음).

**Tech Stack:** Next.js(App Router), React, TypeScript, Web Crypto(sha256), Playwright(render 테스트). 기존 스타일 클래스(`page/panel/card/button/eyebrow/field/badge`) 재사용.

**실행 환경:** 작업 디렉터리 `apps/web`. 타입체크 `npx tsc --noEmit`. 브랜치 `feat/doc-upload`. 라이브 검증 때만 백엔드(API :8000 + Qdrant + Ollama bge-m3, DB agentforge_mvp2) 필요.

---

## File Structure
- **수정** `apps/web/app/lib/api.ts` — `DocumentSummary` 타입 + `listDocuments`, `createSource`, `registerDocument`, `indexDocument`, `sha256Hex`. (기존 `OPERATOR`, `listSources` 재사용.)
- **수정** `apps/web/app/knowledge/page.tsx` — 스캐폴드 → 소스/문서 목록 + "문서 추가" 폼.
- **신규** `apps/web/tests/knowledge-upload.spec.ts` — Playwright render/유효성.
- 백엔드: 변경 없음.

---

## Task 1: lib/api.ts 인제스트 헬퍼

**Files:** Modify `apps/web/app/lib/api.ts`

- [ ] **Step 1: 헬퍼 추가** — 파일 끝에 추가(기존 `API_BASE`, `OPERATOR`, `listSources`, `KnowledgeSource` 등은 그대로):

```ts
export type DocumentSummary = {
  id: string; knowledge_source_id: string; title: string; status: string;
};

export async function listDocuments(): Promise<DocumentSummary[]> {
  const r = await fetch(`${API_BASE}/knowledge/documents`);
  if (!r.ok) throw new Error(`list documents failed: ${r.status}`);
  return r.json();
}

export async function sha256Hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function createSource(input: {
  name: string; owner_department: string;
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/knowledge/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`create source failed: ${r.status}`);
  return r.json();
}

export async function registerDocument(input: {
  knowledge_source_id: string;
  title: string;
  mime_type: string;
  confidentiality_level: string;
  access_groups: string[];
  object_uri: string;
  checksum: string;
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/knowledge/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({ ...input, status: "registered" }),
  });
  if (!r.ok) throw new Error(`register document failed: ${r.status}`);
  return r.json();
}

export async function indexDocument(input: {
  document_id: string; source_text: string;
}): Promise<{ status: string; chunk_count: number; error_code: string | null; error_message: string | null }> {
  const r = await fetch(`${API_BASE}/knowledge/documents/${input.document_id}/index-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({
      parser_profile: "default-txt-md",
      embedding_model: "bge-m3",
      source_text: input.source_text,
    }),
  });
  if (!r.ok) throw new Error(`index failed: ${r.status}`);
  return r.json();
}
```

NOTE: `OPERATOR` is module-private in this file (added in a prior feature) — these new functions are in the same module so they can reference it. Do NOT export or redeclare it.

- [ ] **Step 2: 타입체크**

Run (from apps/web): `npx tsc --noEmit`
Expected: exit 0, no new type errors.

- [ ] **Step 3: Commit**
```bash
git add apps/web/app/lib/api.ts
git commit -m "feat(web): add knowledge ingest helpers (source, register, index, sha256)"
```

---

## Task 2: `/knowledge` 페이지 — 목록 + 문서 추가 폼

**Files:** Modify `apps/web/app/knowledge/page.tsx`; Create `apps/web/tests/knowledge-upload.spec.ts`

- [ ] **Step 1: Playwright 실패 테스트 작성** `apps/web/tests/knowledge-upload.spec.ts`:
```ts
import { test, expect } from "@playwright/test";

test("knowledge page shows add-document form and disables submit until valid", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByPlaceholder("문서 제목")).toBeVisible();
  await expect(page.getByTestId("ingest")).toBeDisabled();
});
```

- [ ] **Step 2: 실패 확인**

Run (from apps/web): `npx playwright test tests/knowledge-upload.spec.ts` (dev 서버 필요 시 컨트롤러가 처리; 자동화 환경에선 라우트 부재로 heading mismatch 또는 placeholder 없음으로 FAIL)
Expected: FAIL.

- [ ] **Step 3: 페이지 구현** — `apps/web/app/knowledge/page.tsx` 전체 교체:
```tsx
"use client";
import { useEffect, useState } from "react";
import {
  createSource,
  indexDocument,
  listDocuments,
  listSources,
  registerDocument,
  sha256Hex,
  type DocumentSummary,
  type KnowledgeSource,
} from "../lib/api";

export default function KnowledgePage() {
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);

  const [sourceMode, setSourceMode] = useState<"existing" | "new">("existing");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [newSourceName, setNewSourceName] = useState("");

  const [title, setTitle] = useState("");
  const [fileName, setFileName] = useState("");
  const [content, setContent] = useState("");
  const [confidentiality, setConfidentiality] = useState("internal");
  const [accessGroups, setAccessGroups] = useState("all-employees");

  const [createdSourceId, setCreatedSourceId] = useState<string | null>(null);
  const [createdDocId, setCreatedDocId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");

  function refresh() {
    listSources().then(setSources).catch(() => {});
    listDocuments().then(setDocuments).catch(() => {});
  }
  useEffect(refresh, []);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileName(f.name);
    const reader = new FileReader();
    reader.onload = () => setContent(String(reader.result ?? ""));
    reader.readAsText(f);
    if (!title) setTitle(f.name.replace(/\.(txt|md)$/i, ""));
  }

  const sourceReady = sourceMode === "existing" ? !!selectedSourceId : newSourceName.trim().length > 0;
  const canSubmit = sourceReady && title.trim().length > 0 && content.trim().length > 0 && !busy;

  async function onSubmit() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      let sid = sourceMode === "existing" ? selectedSourceId : createdSourceId;
      if (sourceMode === "new" && !sid) {
        sid = (await createSource({ name: newSourceName, owner_department: "Operations" })).id;
        setCreatedSourceId(sid);
      }
      if (!sid) throw new Error("지식소스를 선택하거나 새로 만드세요.");

      let did = createdDocId;
      if (!did) {
        const mime = fileName.toLowerCase().endsWith(".md") ? "text/markdown" : "text/plain";
        const checksum = "sha256-" + (await sha256Hex(content));
        const groups = accessGroups.split(",").map((g) => g.trim()).filter(Boolean);
        did = (await registerDocument({
          knowledge_source_id: sid,
          title,
          mime_type: mime,
          confidentiality_level: confidentiality,
          access_groups: groups.length ? groups : ["all-employees"],
          object_uri: "inline://" + (fileName || title),
          checksum,
        })).id;
        setCreatedDocId(did);
      }

      const job = await indexDocument({ document_id: did, source_text: content });
      if (job.status === "succeeded") {
        setResult(`색인됨 ${job.chunk_count}청크 — 이제 에이전트 빌더에서 이 소스를 연결할 수 있어요.`);
        refresh();
      } else {
        setError(`색인 실패: ${job.error_code ?? ""} ${job.error_message ?? ""}`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function addAnother() {
    setTitle(""); setFileName(""); setContent("");
    setCreatedDocId(null); setResult(""); setError("");
  }

  return (
    <section className="page">
      <div>
        <p className="eyebrow">RAG data</p>
        <h1>Knowledge</h1>
        <p>지식소스에 TXT/MD 문서를 추가하면 임베딩 색인되어 에이전트가 답할 수 있습니다.</p>
      </div>

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* 추가 폼 */}
        <div className="panel" style={{ flex: "1 1 380px" }}>
          <h3>문서 추가</h3>

          <label className="label">지식소스</label>
          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <select value={sourceMode} onChange={(e) => setSourceMode(e.target.value as "existing" | "new")}>
              <option value="existing">기존 선택</option>
              <option value="new">새로 만들기</option>
            </select>
            {sourceMode === "existing" ? (
              <select value={selectedSourceId} onChange={(e) => setSelectedSourceId(e.target.value)}>
                <option value="">소스 선택…</option>
                {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            ) : (
              <input className="field" placeholder="새 소스 이름" value={newSourceName}
                onChange={(e) => setNewSourceName(e.target.value)} style={{ marginBottom: 0 }} />
            )}
          </div>

          <input className="field" placeholder="문서 제목" value={title}
            onChange={(e) => setTitle(e.target.value)} />
          <input type="file" accept=".txt,.md" onChange={onFile} style={{ marginBottom: "8px" }} />
          <textarea className="field" rows={6} placeholder="본문 (.txt/.md 파일 선택 시 자동 채움, 또는 직접 붙여넣기)"
            value={content} onChange={(e) => setContent(e.target.value)} />

          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <select value={confidentiality} onChange={(e) => setConfidentiality(e.target.value)}>
              <option value="public">공개</option>
              <option value="internal">내부</option>
              <option value="restricted">제한</option>
            </select>
            <input className="field" placeholder="접근그룹(쉼표)" value={accessGroups}
              onChange={(e) => setAccessGroups(e.target.value)} style={{ marginBottom: 0 }} />
          </div>

          <button className="button" data-testid="ingest" onClick={onSubmit} disabled={!canSubmit}>
            {busy ? "색인 중…" : "추가 & 색인"}
          </button>
          {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
          {result && (
            <div>
              <p style={{ color: "#15803d" }}>✓ {result}</p>
              <button className="button" onClick={addAnother}>다른 문서 추가</button>
            </div>
          )}
        </div>

        {/* 목록 */}
        <div className="panel" style={{ flex: "1 1 320px" }}>
          <h3>지식소스 / 문서</h3>
          {sources.map((s) => (
            <div key={s.id} style={{ marginBottom: "10px" }}>
              <strong>{s.name}</strong>
              <ul style={{ margin: "4px 0", paddingLeft: "18px" }}>
                {documents.filter((d) => d.knowledge_source_id === s.id).map((d) => (
                  <li key={d.id} style={{ fontSize: "14px" }}>
                    {d.title} <span className="badge">{d.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {sources.length === 0 && <p>아직 지식소스가 없습니다.</p>}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: 타입체크**

Run (from apps/web): `npx tsc --noEmit` → exit 0, no new type errors.

- [ ] **Step 5: Commit**
```bash
git add apps/web/app/knowledge/page.tsx apps/web/tests/knowledge-upload.spec.ts
git commit -m "feat(web): knowledge page with TXT/MD upload + inline indexing"
```

---

## Task 3: 라이브 수동 검증 — 컨트롤러 직접 수행

**Files:** 없음(검증).

- [ ] **Step 1: 스택 확인** — API :8000(qdrant 백엔드, DB agentforge_mvp2), Qdrant :6333, Ollama bge-m3. 웹 dev :3300(Preview).
- [ ] **Step 2: Playwright 렌더 테스트** — `apps/web`에서 `$env:PLAYWRIGHT_BASE_URL="http://127.0.0.1:3300"; npx playwright test tests/knowledge-upload.spec.ts` → PASS.
- [ ] **Step 3: 업로드 루프** — `/knowledge`에서 새 소스 "출장 규정집" 생성, 제목 "출장 규정", 본문 붙여넣기(예: "# 출장 규정\n국내 출장비는 일 5만원, 해외는 일 10만원을 지급한다.") → "추가 & 색인" → "색인됨 N청크". Qdrant points 증가 확인.
- [ ] **Step 4: 엔드투엔드** — `/agents/new`에서 그 소스(색인됨 배지) 연결 → 게시 → "출장비 얼마?" 질문 → 새 문서 근거 답변+출처. Preview 스크린샷(가능 시).
- [ ] **Step 5: ACL 음성 확인(선택)** — confidentiality=restricted + access_groups=`department:Finance`로 올린 문서를, 빌더 테스트에서 HR 사용자로 질문 시 거부되는지.

---

## Self-Review (작성자 확인)
- **스펙 커버리지:** §2 위치(Task2) / §3 헬퍼(Task1) / §4 폼·멱등 흐름(Task2 onSubmit: createdSourceId/createdDocId 가드) / §5 통합효과(Task3 Step4) / §6 에러·기본 all-employees(onSubmit groups fallback, error 표시) / §7 테스트(Task2 Playwright + Task3 수동) — 모두 매핑.
- **플레이스홀더:** 모든 코드 스텝 완전. TODO 없음.
- **타입 일관성:** `KnowledgeSource`(기존)·`DocumentSummary`(Task1 신규)·`createSource/registerDocument/indexDocument/sha256Hex/listDocuments` 시그니처가 Task2 사용처와 일치. `data-testid="ingest"`가 Playwright와 일치. import 경로 `../lib/api`는 `app/knowledge/page.tsx`에서 한 단계 위 → 정확.
- **주의:** `indexDocument`는 동기 색인(IndexJobRead 반환). 첫 색인은 bge-m3 임베딩 호출이라 수 초 소요 — `busy`로 버튼 잠금.
