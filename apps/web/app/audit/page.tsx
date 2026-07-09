"use client";
import { useEffect, useState } from "react";
import { listAuditEvents, type AuditEvent } from "../lib/api";
import { useDemoRole } from "../lib/useDemoRole";

export default function AuditPage() {
  // UX only: the server enforces RBAC on GET /audit/events regardless (403 for
  // non-privileged roles) — we skip the fetch entirely and show a friendly
  // placeholder instead of round-tripping into an ugly generic error state.
  const { role, isPrivileged } = useDemoRole();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [eventType, setEventType] = useState("");
  const [error, setError] = useState("");

  function refresh() {
    if (!isPrivileged) return;
    setError("");
    listAuditEvents({ event_type: eventType || undefined, limit: 50 })
      .then(setEvents)
      .catch((e) => setError(String(e)));
  }
  useEffect(refresh, [eventType, isPrivileged]);

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Governance</p>
        <h1>Audit</h1>
        <p>actor·부서·이벤트·대상·사유와 페이로드로 메타데이터 변경을 감사합니다. (admin 전용)</p>
      </div>
      <section className="panel">
        {!isPrivileged && (
          <p data-testid="role-restricted-note" style={{ fontSize: "12px", color: "#64748b" }}>
            데모 역할 &quot;{role}&quot; — 감사 로그 열람은 admin 전용이며, 서버가 거부(403)하므로
            이 화면에서는 조회를 시도하지 않습니다.
          </p>
        )}
        {isPrivileged && (
          <>
            <div style={{ display: "flex", gap: "8px", marginBottom: "10px", flexWrap: "wrap" }}>
              <input className="field" data-testid="audit-filter" placeholder="event_type 필터 (예: document.acl_changed)"
                value={eventType} onChange={(e) => setEventType(e.target.value)} style={{ marginBottom: 0, maxWidth: "320px" }} />
              <button className="button secondary" onClick={refresh}>새로고침</button>
            </div>
            {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
            {events.length === 0 && !error && <p data-testid="audit-empty">감사 이벤트가 없습니다.</p>}
            <ul className="statusList" data-testid="audit-list" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {events.map((e) => (
                <li key={e.id} data-testid="audit-row" style={{ padding: "8px 0" }}>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                    <span className="badge" data-testid="audit-event-type">{e.event_type}</span>
                    <span style={{ fontSize: "12px", color: "#64748b" }}>
                      {e.created_at.slice(0, 19).replace("T", " ")} · {e.actor_id} ({e.actor_department}) · {e.target_type}:{e.target_id.slice(0, 8)}
                    </span>
                  </div>
                  {e.reason && <p style={{ fontSize: "12px", margin: "2px 0 0" }}>사유: {e.reason}</p>}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </section>
  );
}
