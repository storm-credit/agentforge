"use client";
import { useEffect, useState } from "react";
import { ask, firstAgentId, type MockUserKey } from "../lib/api";

export default function ChatPage() {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [user, setUser] = useState<MockUserKey>("finance");
  const [language, setLanguage] = useState<"auto" | "ko" | "en">("auto");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<
    Array<{ title: string; citation_locator: string | null }>
  >([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    firstAgentId().then(setAgentId);
  }, []);

  async function onAsk() {
    if (!agentId || !message) return;
    setLoading(true);
    try {
      const run = await ask({ agentId, message, language, user });
      setAnswer(run.answer);
      setCitations(run.citations ?? []);
    } catch (e) {
      setAnswer(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Agent interaction</p>
        <h1>Chat</h1>
        <p>Ask the agent a question and review the cited sources.</p>
      </div>

      <div className="panel">
        <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", marginBottom: "16px" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
            사용자(부서)
            <select
              value={user}
              onChange={(e) => setUser(e.target.value as MockUserKey)}
              style={{ fontSize: "14px" }}
            >
              <option value="finance">Finance</option>
              <option value="hr">HR</option>
            </select>
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
            언어
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as "auto" | "ko" | "en")}
              style={{ fontSize: "14px" }}
            >
              <option value="auto">자동</option>
              <option value="ko">한국어</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>

        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="질문을 입력하세요"
          rows={3}
          style={{
            display: "block",
            width: "100%",
            fontSize: "14px",
            padding: "10px",
            borderRadius: "6px",
            border: "1px solid var(--line)",
            marginBottom: "12px",
            resize: "vertical",
          }}
        />

        <button
          className="button"
          onClick={onAsk}
          disabled={loading || !agentId}
        >
          {loading ? "..." : "질문"}
        </button>
      </div>

      {answer && (
        <article className="card">
          <h3>답변</h3>
          <p data-testid="answer">{answer}</p>
          {citations.length > 0 && (
            <>
              <h4 style={{ margin: "16px 0 8px" }}>출처</h4>
              <ul style={{ margin: 0, paddingLeft: "20px" }}>
                {citations.map((c, i) => (
                  <li key={i} style={{ fontSize: "14px", marginBottom: "4px" }}>
                    {c.title} — {c.citation_locator}
                  </li>
                ))}
              </ul>
            </>
          )}
        </article>
      )}
    </section>
  );
}
