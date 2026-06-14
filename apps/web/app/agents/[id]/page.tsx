"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  getAgent,
  listVersions,
  publishVersion,
  validateVersion,
  type AgentSummary,
  type AgentVersionSummary,
} from "../../lib/api";

const STATUS_BADGE: Record<string, string> = {
  draft: "badge warn",
  validated: "badge warn",
  published: "badge",
  superseded: "badge",
};

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [agent, setAgent] = useState<AgentSummary | null>(null);
  const [versions, setVersions] = useState<AgentVersionSummary[]>([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reasonById, setReasonById] = useState<Record<string, string>>({});

  function refresh() {
    Promise.all([getAgent(id), listVersions(id)])
      .then(([a, v]) => { setAgent(a); setVersions(v); })
      .catch((e) => setError(String(e)));
  }

  useEffect(refresh, [id]);

  async function act(versionId: string, action: "validate" | "publish") {
    setBusyId(versionId);
    setError("");
    try {
      const reason = (reasonById[versionId] ?? "").trim();
      if (action === "validate") await validateVersion(versionId, reason || "validated via Agent Studio");
      else await publishVersion(versionId, reason || "published via Agent Studio");
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Builder</p>
        <Link href="/agents" style={{ fontSize: "13px" }}>← Agents</Link>
        <h1>{agent ? agent.name : "에이전트"}</h1>
        {agent && (
          <p>
            <span className={STATUS_BADGE[agent.status] ?? "badge"}>{agent.status}</span>
            {" · "}{agent.owner_department}
          </p>
        )}
        {agent && <p>{agent.purpose}</p>}
      </div>

      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}

      <div className="panel">
        <h3>버전 라이프사이클</h3>
        <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 12px" }}>
          draft → validated → published. 게시하면 기존 게시 버전은 superseded 됩니다.
        </p>
        {versions.length === 0 && <p data-testid="no-versions">버전이 없습니다.</p>}
        <ul data-testid="version-list" className="statusList" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {versions.map((v) => (
            <li key={v.id} data-testid="version-row" style={{ padding: "12px 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <strong>v{v.version}</strong>
                <span className={STATUS_BADGE[v.status] ?? "badge"} data-testid="version-status">{v.status}</span>
                <span style={{ fontSize: "12px", color: "#64748b" }}>
                  by {v.created_by}{v.published_at ? ` · 게시 ${v.published_at.slice(0, 10)}` : ""}
                </span>
              </div>
              {(v.status === "draft" || v.status === "validated") && (
                <div className="buttonRow" style={{ marginTop: "8px" }}>
                  <input
                    className="field"
                    style={{ maxWidth: "260px" }}
                    placeholder="사유 (감사 기록)"
                    value={reasonById[v.id] ?? ""}
                    onChange={(e) => setReasonById((p) => ({ ...p, [v.id]: e.target.value }))}
                  />
                  {v.status === "draft" && (
                    <button
                      className="button secondary"
                      data-testid="validate"
                      disabled={busyId === v.id}
                      onClick={() => act(v.id, "validate")}
                    >
                      {busyId === v.id ? "검증 중…" : "검증"}
                    </button>
                  )}
                  <button
                    className="button"
                    data-testid="publish"
                    disabled={busyId === v.id}
                    onClick={() => act(v.id, "publish")}
                  >
                    {busyId === v.id ? "게시 중…" : "게시"}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
