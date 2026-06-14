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
          <Link className="card" data-testid="agent-card" key={a.id} href={`/agents/${a.id}`}
            style={{ textDecoration: "none", color: "inherit" }}>
            <h3>{a.name}</h3>
            <p>{a.purpose}</p>
            <p><span className="badge">{a.status}</span> · {a.owner_department}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
