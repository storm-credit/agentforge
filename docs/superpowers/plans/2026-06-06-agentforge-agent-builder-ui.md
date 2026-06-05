# 에이전트 빌더 UI (가이드형 한 화면) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영자가 `/agents/new` 한 화면에서 에이전트 생성 → 기존 지식소스 연결 → 게시 → 인라인 채팅 테스트를 끝내게 한다.

**Architecture:** Next.js App Router 클라이언트 컴포넌트 1개(`/agents/new`)가 기존 FastAPI 엔드포인트(`/agents`, `/agents/versions`, `/agents/versions/{id}/publish`, `/knowledge/sources`, `/knowledge/documents`, `/runs`)를 `lib/api.ts` 헬퍼로 호출. 백엔드 무변경. 게시는 생성→버전→게시 3-콜을 멱등하게 수행.

**Tech Stack:** Next.js(App Router), React, TypeScript, Playwright(render 테스트). 기존 web 스타일 클래스(`page/panel/card/button/eyebrow`) 재사용.

**실행 환경:** 작업 디렉터리 `apps/web`. 빌드/타입체크 `npm run build`. e2e `npx playwright test`. 브랜치 `feat/agent-builder-ui`. 백엔드는 라이브 검증 때만 필요(`apps/api/.venv` + Qdrant + Ollama, DB `agentforge_mvp2`).

---

## File Structure
- **수정** `apps/web/app/lib/api.ts` — OPERATOR 헤더 + 빌더 헬퍼(listAgents, listSources, indexedDocCountBySource, createAgent, createVersion, publishVersion).
- **신규** `apps/web/app/agents/new/page.tsx` — 가이드형 빌더(클라이언트).
- **수정** `apps/web/app/agents/page.tsx` — 목록 + "새 에이전트 만들기" 링크.
- **신규** `apps/web/tests/agent-builder.spec.ts` — Playwright render/유효성 테스트.

---

## Task 1: lib/api.ts 빌더 헬퍼

**Files:** Modify `apps/web/app/lib/api.ts`

- [ ] **Step 1: 헬퍼 추가** — 파일 끝에 다음을 추가(기존 `API_BASE`, `ask`, `MOCK_USERS`는 유지):

```ts
const OPERATOR = {
  "X-Agent-Forge-User": "operator",
  "X-Agent-Forge-Department": "Operations",
  "X-Agent-Forge-Roles": "admin",
  "X-Agent-Forge-Groups": "all-employees",
  "X-Agent-Forge-Clearance": "internal",
} as const;

export type KnowledgeSource = { id: string; name: string };
export type AgentSummary = {
  id: string; name: string; purpose: string; owner_department: string; status: string;
};

export async function listAgents(): Promise<AgentSummary[]> {
  const r = await fetch(`${API_BASE}/agents`);
  if (!r.ok) throw new Error(`list agents failed: ${r.status}`);
  return r.json();
}

export async function listSources(): Promise<KnowledgeSource[]> {
  const r = await fetch(`${API_BASE}/knowledge/sources`);
  if (!r.ok) throw new Error(`list sources failed: ${r.status}`);
  return r.json();
}

// 소스별 status==="indexed" 문서 수
export async function indexedDocCountBySource(): Promise<Record<string, number>> {
  const r = await fetch(`${API_BASE}/knowledge/documents`);
  if (!r.ok) throw new Error(`list documents failed: ${r.status}`);
  const docs: Array<{ knowledge_source_id: string; status: string }> = await r.json();
  const counts: Record<string, number> = {};
  for (const d of docs) {
    if (d.status === "indexed") {
      counts[d.knowledge_source_id] = (counts[d.knowledge_source_id] ?? 0) + 1;
    }
  }
  return counts;
}

export async function createAgent(input: {
  name: string; purpose: string; owner_department: string;
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({ ...input, status: "draft" }),
  });
  if (!r.ok) throw new Error(`create agent failed: ${r.status}`);
  return r.json();
}

export async function createVersion(input: {
  agent_id: string; knowledge_source_ids: string[];
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/agents/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({
      agent_id: input.agent_id,
      version: 1,
      status: "draft",
      config: { citation_required: true, knowledge_source_ids: input.knowledge_source_ids },
    }),
  });
  if (!r.ok) throw new Error(`create version failed: ${r.status}`);
  return r.json();
}

export async function publishVersion(versionId: string): Promise<{ id: string; status: string }> {
  const r = await fetch(`${API_BASE}/agents/versions/${versionId}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({ reason: "published via Agent Studio" }),
  });
  if (!r.ok) throw new Error(`publish failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 타입체크/빌드 통과 확인**

Run (from `apps/web`): `npm run build`
Expected: 빌드 성공(타입 오류 없음). (경고는 무시 가능, 에러 0.)

- [ ] **Step 3: Commit**
```bash
git add apps/web/app/lib/api.ts
git commit -m "feat(web): add agent-builder API helpers (sources, create, version, publish)"
```

---

## Task 2: `/agents/new` 가이드형 빌더 페이지

**Files:** Create `apps/web/app/agents/new/page.tsx`; Test `apps/web/tests/agent-builder.spec.ts`

- [ ] **Step 1: Playwright 실패 테스트 작성** `apps/web/tests/agent-builder.spec.ts` (백엔드 불요 — 렌더/유효성만; 기존 `chat.spec.ts` 패턴):
```ts
import { test, expect } from "@playwright/test";

test("builder renders guided sections and disables publish until valid", async ({ page }) => {
  await page.goto("/agents/new");
  await expect(page.getByRole("heading", { name: "에이전트 만들기" })).toBeVisible();
  await expect(page.getByPlaceholder("이름 (예: 사내 도우미)")).toBeVisible();
  // 이름/소스 없으면 게시 비활성
  await expect(page.getByTestId("publish")).toBeDisabled();
  // 테스트 패널은 게시 전 잠금 안내
  await expect(page.getByText("게시하면 활성화")).toBeVisible();
});
```

- [ ] **Step 2: 실패 확인**

Run (from `apps/web`): `npx playwright test tests/agent-builder.spec.ts`
Expected: FAIL — `/agents/new` 라우트가 없어 heading을 못 찾음. (playwright.config의 webServer가 dev를 자동 기동. 자동 기동이 없으면 별도 터미널에서 `npm run dev` 먼저.)

- [ ] **Step 3: 빌더 페이지 구현** `apps/web/app/agents/new/page.tsx`:
```tsx
"use client";
import { useEffect, useState } from "react";
import {
  ask,
  createAgent,
  createVersion,
  indexedDocCountBySource,
  listSources,
  publishVersion,
  type KnowledgeSource,
  type MockUserKey,
} from "../../lib/api";

export default function NewAgentPage() {
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [department, setDepartment] = useState("");

  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [docCounts, setDocCounts] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sourcesError, setSourcesError] = useState("");

  // idempotent publish state
  const [agentId, setAgentId] = useState<string | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [published, setPublished] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState("");

  // test panel
  const [user, setUser] = useState<MockUserKey>("finance");
  const [language, setLanguage] = useState<"auto" | "ko" | "en">("auto");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<
    Array<{ title: string; citation_locator: string | null }>
  >([]);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    Promise.all([listSources(), indexedDocCountBySource()])
      .then(([s, c]) => { setSources(s); setDocCounts(c); })
      .catch((e) => setSourcesError(String(e)));
  }, []);

  function toggleSource(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const canPublish = name.trim().length > 0 && selected.size > 0 && !publishing && !published;

  async function onPublish() {
    setPublishing(true);
    setPublishError("");
    try {
      let aid = agentId;
      if (!aid) {
        aid = (await createAgent({ name, purpose, owner_department: department || "Operations" })).id;
        setAgentId(aid);
      }
      let vid = versionId;
      if (!vid) {
        vid = (await createVersion({ agent_id: aid, knowledge_source_ids: [...selected] })).id;
        setVersionId(vid);
      }
      await publishVersion(vid);
      setPublished(true);
    } catch (e) {
      setPublishError(String(e));
    } finally {
      setPublishing(false);
    }
  }

  async function onAsk() {
    if (!agentId || !message) return;
    setAsking(true);
    try {
      const run = await ask({ agentId, message, language, user });
      setAnswer(run.answer);
      setCitations(run.citations ?? []);
    } catch (e) {
      setAnswer(String(e));
    } finally {
      setAsking(false);
    }
  }

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Builder</p>
        <h1>에이전트 만들기</h1>
        <p>생성 → 지식소스 연결 → 게시 → 바로 테스트.</p>
      </div>

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* 설정 */}
        <div className="panel" style={{ flex: "1 1 360px" }}>
          <h3>① 기본정보</h3>
          <input className="field" placeholder="이름 (예: 사내 도우미)"
            value={name} onChange={(e) => setName(e.target.value)} />
          <input className="field" placeholder="목적 (예: 사내 문서 질의응답)"
            value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          <input className="field" placeholder="담당 부서 (예: Operations)"
            value={department} onChange={(e) => setDepartment(e.target.value)} />

          <h3 style={{ marginTop: "16px" }}>② 지식소스 연결</h3>
          {sourcesError && <p style={{ color: "#b91c1c" }}>{sourcesError}</p>}
          {!sourcesError && sources.length === 0 && (
            <p data-testid="no-sources">
              지식소스가 없습니다. 시드(<code>python -m app.seed_demo</code>)를 실행하거나 Knowledge에서 추가하세요.
            </p>
          )}
          <ul style={{ listStyle: "none", padding: 0 }}>
            {sources.map((s) => {
              const count = docCounts[s.id] ?? 0;
              const disabled = count === 0;
              return (
                <li key={s.id} style={{ marginBottom: "6px", opacity: disabled ? 0.5 : 1 }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <input type="checkbox" disabled={disabled}
                      checked={selected.has(s.id)} onChange={() => toggleSource(s.id)} />
                    {s.name}
                    <span className="badge">{disabled ? "색인 0" : `색인됨 ${count}`}</span>
                  </label>
                </li>
              );
            })}
          </ul>

          <h3 style={{ marginTop: "16px" }}>③ 게시</h3>
          <button className="button" data-testid="publish" onClick={onPublish} disabled={!canPublish}>
            {publishing ? "게시 중…" : published ? "게시됨 ✓" : "게시하기"}
          </button>
          {publishError && <p style={{ color: "#b91c1c" }}>{publishError}</p>}
          {published && <p style={{ color: "#15803d" }}>✓ 게시됨 — 오른쪽에서 테스트하세요.</p>}
        </div>

        {/* 테스트 */}
        <div className="panel" style={{ flex: "1 1 360px", opacity: published ? 1 : 0.5 }}>
          <h3>테스트</h3>
          {!published && <p data-testid="test-lock">🔒 게시하면 활성화됩니다.</p>}
          <div style={{ display: "flex", gap: "12px", marginBottom: "10px" }}>
            <select value={user} onChange={(e) => setUser(e.target.value as MockUserKey)} disabled={!published}>
              <option value="finance">Finance</option>
              <option value="hr">HR</option>
            </select>
            <select value={language} onChange={(e) => setLanguage(e.target.value as "auto" | "ko" | "en")} disabled={!published}>
              <option value="auto">자동</option>
              <option value="ko">한국어</option>
              <option value="en">English</option>
            </select>
          </div>
          <textarea className="field" rows={3} placeholder="질문 (예: 연차 며칠 쓸 수 있어?)"
            value={message} onChange={(e) => setMessage(e.target.value)} disabled={!published} />
          <button className="button" onClick={onAsk} disabled={!published || asking || !message}>
            {asking ? "답변 생성 중… (첫 질문은 모델 로딩으로 느릴 수 있어요)" : "질문"}
          </button>
          {answer && (
            <article className="card" style={{ marginTop: "12px" }}>
              <h4>답변</h4>
              <p data-testid="answer">{answer}</p>
              {citations.length > 0 && (
                <ul>
                  {citations.map((c, i) => (
                    <li key={i}>{c.title} — {c.citation_locator}</li>
                  ))}
                </ul>
              )}
            </article>
          )}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: 최소 스타일 추가** — `apps/web/app/globals.css` 끝에 `.field`/`.badge`가 없으면 추가(있으면 생략):
```css
.field { display:block; width:100%; padding:8px 10px; margin-bottom:8px;
  border:1px solid var(--line, #cbd5e1); border-radius:6px; font-size:14px; }
.badge { font-size:11px; color:#475569; background:#f1f5f9; border-radius:10px; padding:1px 8px; margin-left:auto; }
```

- [ ] **Step 5: 빌드 + 테스트 통과 확인**

Run (from `apps/web`): `npm run build` → 성공(타입 에러 0).
Run: `npx playwright test tests/agent-builder.spec.ts` → PASS (heading/placeholder/게시 비활성/잠금 문구 확인).

- [ ] **Step 6: Commit**
```bash
git add apps/web/app/agents/new/page.tsx apps/web/tests/agent-builder.spec.ts apps/web/app/globals.css
git commit -m "feat(web): guided single-page agent builder with inline test panel"
```

---

## Task 3: `/agents` 목록 + 만들기 링크

**Files:** Modify `apps/web/app/agents/page.tsx`

- [ ] **Step 1: 페이지 교체** — 스캐폴드를 목록+링크로 (클라이언트 컴포넌트):
```tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listAgents, type AgentSummary } from "../lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listAgents().then(setAgents).catch((e) => setError(String(e)));
  }, []);

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Builder</p>
        <h1>Agents</h1>
        <p>에이전트를 만들고 게시한 뒤 바로 테스트하세요.</p>
      </div>
      <Link className="button" href="/agents/new">새 에이전트 만들기</Link>
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      <div className="cardGrid" style={{ marginTop: "16px" }}>
        {agents.map((a) => (
          <article className="card" key={a.id}>
            <h3>{a.name}</h3>
            <p>{a.purpose}</p>
            <p><span className="badge">{a.status}</span> · {a.owner_department}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: 빌드 확인** — `npm run build` 성공.

- [ ] **Step 3: Commit**
```bash
git add apps/web/app/agents/page.tsx
git commit -m "feat(web): agents list with create link and status badges"
```

---

## Task 4: 라이브 수동 검증 (전체 루프) — 컨트롤러 직접 수행

**Files:** 없음(검증).

- [ ] **Step 1: 백엔드 스택 확인** — postgres/qdrant/ollama 기동, `apps/api/.env`(qdrant 백엔드+bge-m3, DB `agentforge_mvp2`) 존재, API `uvicorn :8000` 기동, 지식소스 '사내 정책'이 색인됨(`/knowledge/documents`에서 status=indexed 1+).

- [ ] **Step 2: 웹 기동** — `apps/web`에서 `npm run dev -- -p 3300` (CORS에 3300 포함됨). 브라우저 `http://localhost:3300/agents` → "새 에이전트 만들기" → `/agents/new`.

- [ ] **Step 3: 전체 루프 확인**
  - ① 이름 "테스트 도우미", 목적/부서 입력
  - ② '사내 정책'(색인됨 N 배지, 체크 가능) 선택. 색인 0 소스는 비활성인지 확인.
  - ③ "게시하기" → "게시됨 ✓", 오른쪽 테스트 패널 활성화
  - 테스트: Finance·자동, "연차 며칠 쓸 수 있어?" → 한국어 답변 + 출처 노출
  - Claude Preview로 스크린샷 1장(게시 후 답변 화면) 남기기.

- [ ] **Step 4: 멱등 확인(선택)** — 게시 직후 새로고침 없이 같은 이름으로 다시 만들 때 중복 생성 안 되는지(같은 세션 재클릭은 published 상태라 버튼 비활성). API 레벨에서 createAgent가 1회만 호출됐는지 네트워크 탭/로그로 확인.

---

## Self-Review (작성자 확인)
- **스펙 커버리지:** §2 라우트(Task 2,3) / §3 헬퍼(Task 1) / §4 흐름·멱등 게시(Task 2 onPublish) / §5 보강 1~5: 멱등(onPublish 상태), 색인배지+0건비활성(Task2 Step3 체크리스트), 로딩/콜드스타트("게시 중…","답변 생성 중…"), 빈상태(no-sources), 게시후마무리+기본 Finance(Task2) — 모두 매핑. §7 테스트: Playwright(Task2)+수동(Task4).
- **플레이스홀더:** 모든 코드 스텝에 완전한 코드 포함. TODO/TBD 없음.
- **타입 일관성:** `MockUserKey`·`ask`·`KnowledgeSource`·`AgentSummary`는 Task1에서 정의/기존 export와 일치. `createAgent/createVersion/publishVersion` 시그니처가 Task2 `onPublish` 호출과 일치. `data-testid`("publish","answer","no-sources","test-lock")가 Task2 테스트와 일치.
- **주의:** Playwright happy-path(게시→답변)는 백엔드 필요라 자동화에서 제외, Task4 수동으로 명시(기존 chat.spec 패턴=렌더만과 일관).
