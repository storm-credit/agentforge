"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  createDraftVersion,
  getAgent,
  listVersions,
  publishVersion,
  validateVersion,
  type AgentSummary,
  type AgentVersionSummary,
} from "../../lib/api";
import { useDemoRole } from "../../lib/useDemoRole";

const STATUS_BADGE: Record<string, string> = {
  draft: "badge warn",
  validated: "badge info",
  published: "badge success",
  superseded: "badge",
};

// Keys whose JSON value differs between the current published config and another version.
function diffConfig(
  current: Record<string, unknown>,
  other: Record<string, unknown>,
): string[] {
  const cur = current ?? {};
  const oth = other ?? {};
  const keys = Array.from(new Set([...Object.keys(cur), ...Object.keys(oth)])).sort();
  const out: string[] = [];
  for (const k of keys) {
    const a = JSON.stringify(cur[k]);
    const b = JSON.stringify(oth[k]);
    if (a !== b) out.push(`${k}: ${a ?? "∅"} → ${b ?? "∅"}`);
  }
  return out;
}

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  // UX only: version create/validate/publish are role-gated server-side (403 for
  // non-privileged roles) — hide the controls the current demo role can't use.
  const { isPrivileged } = useDemoRole();
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

  async function onCreateVersion() {
    setBusyId("new");
    setError("");
    try {
      // Clone the latest version's config as a sensible base for the new draft.
      const base = versions[0]?.config ?? { citation_required: true };
      await createDraftVersion(id, base);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyId(null);
    }
  }

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
        <Link href="/agents" style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>← Agents</Link>
        <h1>{agent ? agent.name : "에이전트"}</h1>
        {agent && (
          <p>
            <span className={STATUS_BADGE[agent.status] ?? "badge"}>{agent.status}</span>
            {" · "}{agent.owner_department}
          </p>
        )}
        {agent && <p>{agent.purpose}</p>}
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="panel">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", flexWrap: "wrap" }}>
          <h3 style={{ margin: 0 }}>버전 라이프사이클</h3>
          {isPrivileged && (
            <button
              className="button secondary"
              data-testid="new-version"
              disabled={busyId === "new"}
              onClick={onCreateVersion}
            >
              {busyId === "new" ? "생성 중…" : "새 버전 생성"}
            </button>
          )}
        </div>
        <p className="note" style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
          draft → validated → published. 게시하면 기존 게시 버전은 superseded 됩니다.
        </p>
        {versions.length === 0 && <p data-testid="no-versions">버전이 없습니다.</p>}
        <ul data-testid="version-list" className="statusList" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {versions.map((v) => {
            const published = versions.find((x) => x.status === "published");
            const showDiff = published && published.id !== v.id;
            const diff = showDiff ? diffConfig(published!.config, v.config) : [];
            return (
            <li key={v.id} data-testid="version-row" style={{ padding: "12px 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <strong>v{v.version}</strong>
                <span className={STATUS_BADGE[v.status] ?? "badge"} data-testid="version-status">{v.status}</span>
                <span className="meta">
                  by {v.created_by}{v.published_at ? ` · 게시 ${v.published_at.slice(0, 10)}` : ""}
                </span>
              </div>
              {isPrivileged && (v.status === "draft" || v.status === "validated" || v.status === "superseded") && (
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
                  {v.status === "superseded" ? (
                    <button
                      className="button secondary"
                      data-testid="rollback"
                      disabled={busyId === v.id}
                      onClick={() => act(v.id, "publish")}
                    >
                      {busyId === v.id ? "롤백 중…" : "이 버전으로 롤백(재게시)"}
                    </button>
                  ) : (
                    <button
                      className="button"
                      data-testid="publish"
                      disabled={busyId === v.id}
                      onClick={() => act(v.id, "publish")}
                    >
                      {busyId === v.id ? "게시 중…" : "게시"}
                    </button>
                  )}
                </div>
              )}
              {showDiff && (
                <details data-testid="version-diff" style={{ marginTop: "6px", fontSize: "var(--text-xs)" }}>
                  <summary>현재 게시본(v{published!.version})과 차이 {diff.length ? `(${diff.length})` : "(동일)"}</summary>
                  {diff.length === 0 ? (
                    <p style={{ color: "var(--text-muted)", margin: "4px 0 0" }}>config 동일</p>
                  ) : (
                    <ul style={{ margin: "4px 0 0" }}>
                      {diff.map((d, i) => (
                        <li key={i}><code>{d}</code></li>
                      ))}
                    </ul>
                  )}
                </details>
              )}
            </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
