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
  const [temperature, setTemperature] = useState(0.2);

  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [docCounts, setDocCounts] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sourcesError, setSourcesError] = useState("");

  const [agentId, setAgentId] = useState<string | null>(null);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [published, setPublished] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState("");

  const [user, setUser] = useState<MockUserKey>("finance");
  const [language, setLanguage] = useState<"auto" | "ko" | "en">("auto");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<
    Array<{ title: string; citation_locator: string | null }>
  >([]);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState("");

  useEffect(() => {
    Promise.all([listSources(), indexedDocCountBySource()])
      .then(([s, c]) => { setSources(s); setDocCounts(c); })
      .catch((e) => setSourcesError(String(e)));
  }, []);

  function toggleSource(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
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
        vid = (await createVersion({ agent_id: aid, knowledge_source_ids: [...selected], temperature })).id;
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
    setAskError("");
    try {
      const run = await ask({ agentId, message, language, user });
      setAnswer(run.answer);
      setCitations(run.citations ?? []);
    } catch (e) {
      setAnswer("");
      setCitations([]);
      setAskError(String(e));
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
        <div className="panel" style={{ flex: "1 1 360px" }}>
          <h3>① 기본정보</h3>
          <input className="field" placeholder="이름 (예: 사내 도우미)"
            value={name} onChange={(e) => setName(e.target.value)} />
          <input className="field" placeholder="목적 (예: 사내 문서 질의응답)"
            value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          <input className="field" placeholder="담당 부서 (예: Operations)"
            value={department} onChange={(e) => setDepartment(e.target.value)} />

          <h3 style={{ marginTop: "var(--space-4)" }}>② 지식소스 연결</h3>
          {sourcesError && <p className="error-text">{sourcesError}</p>}
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
                    <span className={disabled ? "badge" : "badge success"}>{disabled ? "색인 0" : `색인됨 ${count}`}</span>
                  </label>
                </li>
              );
            })}
          </ul>

          <h3 style={{ marginTop: "var(--space-4)" }}>③ 생성 설정</h3>
          <label style={{ display: "block", fontSize: "var(--text-base)" }}>
            답변 성향: <strong data-testid="temperature-value">{temperature.toFixed(1)}</strong>{" "}
            <span style={{ color: "var(--text-muted)" }}>(정확 ↔ 다양)</span>
            <input
              type="range" data-testid="temperature" min={0} max={0.7} step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              disabled={published}
              style={{ display: "block", width: "100%", marginTop: "6px" }}
            />
          </label>
          <p className="note" style={{ margin: "4px 0 0" }}>
            근거형 RAG 권장: 낮게(0.2). 상한 0.7로 제한됩니다(환각 통제).
          </p>

          <h3 style={{ marginTop: "var(--space-4)" }}>④ 게시</h3>
          <button className="button" data-testid="publish" onClick={onPublish} disabled={!canPublish}>
            {publishing ? "게시 중…" : published ? "게시됨 ✓" : "게시하기"}
          </button>
          {publishError && <p className="error-text">{publishError}</p>}
          {published && <p className="success-text">✓ 게시됨 — 오른쪽에서 테스트하세요.</p>}
        </div>

        <div className="panel" style={{ flex: "1 1 360px", opacity: published ? 1 : 0.5 }}>
          <h3>테스트</h3>
          {!published && <p data-testid="test-lock">🔒 게시하면 활성화됩니다.</p>}
          <div style={{ display: "flex", gap: "var(--space-3)", marginBottom: "var(--space-3)" }}>
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
          {askError && (
            <p data-testid="ask-error" className="error-text">{askError}</p>
          )}
          {answer && (
            <article className="card" style={{ marginTop: "var(--space-3)" }}>
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
