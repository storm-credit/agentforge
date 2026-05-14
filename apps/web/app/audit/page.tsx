"use client";

import { useMemo, useState, useTransition } from "react";
import { AuditEvent, fetchAuditEvents } from "./api";

const seedEvents: AuditEvent[] = [
  {
    id: "seed-eval",
    eventType: "eval_run.created",
    actorId: "eval-api-runner",
    actorDepartment: "QA",
    targetType: "eval_run",
    targetId: "synthetic-corpus-v0.1",
    reason: "",
    payload: { passed: true, total_cases: 30 },
    createdAt: "Latest smoke",
  },
  {
    id: "seed-run",
    eventType: "run.created",
    actorId: "local-user",
    actorDepartment: "Operations",
    targetType: "run",
    targetId: "Policy RAG Assistant",
    reason: "",
    payload: { citation_validation_pass: true },
    createdAt: "Runtime trace",
  },
  {
    id: "seed-document",
    eventType: "document.indexed",
    actorId: "storage-indexer",
    actorDepartment: "Operations",
    targetType: "document",
    targetId: "Policy library",
    reason: "",
    payload: { chunk_count: 2 },
    createdAt: "Ingestion smoke",
  },
];

const eventTypes = ["", "eval_run.created", "run.created", "document.indexed", "agent_version.published"];
const targetTypes = ["", "eval_run", "run", "document", "agent_version"];

export default function AuditPage() {
  const [events, setEvents] = useState(seedEvents);
  const [eventType, setEventType] = useState("");
  const [targetType, setTargetType] = useState("");
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState(
    "Seed evidence is loaded until the audit API is synced from a running stack.",
  );
  const [isPending, startTransition] = useTransition();

  const latestRunTarget = useMemo(
    () => events.find((event) => event.eventType === "run.created")?.targetId ?? "No run event yet",
    [events],
  );

  async function syncAuditEvents() {
    const result = await fetchAuditEvents({ eventType, targetType, query });
    if (result.ok && result.data) {
      setEvents(result.data.length ? result.data : []);
      setNotice(`Synced ${result.data.length} audit event(s) from ${result.endpoint ?? "audit API"}.`);
      return;
    }

    setNotice(
      `Audit events unavailable (${result.error ?? "request failed"}). Showing seed evidence.`,
    );
  }

  return (
    <section className="page auditPage">
      <div className="header">
        <div>
          <p className="eyebrow">Governance</p>
          <h1>Audit</h1>
          <p>
            Track the evidence chain from document ingestion through runtime trace and eval
            report persistence.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={isPending}
          onClick={() => startTransition(() => void syncAuditEvents())}
          type="button"
        >
          {isPending ? "Syncing" : "Sync audit"}
        </button>
      </div>

      <section className="nextAction">
        <div>
          <span className="badge">Audit API</span>
          <strong>Searchable event reads are now wired to /api/v1/audit/events.</strong>
        </div>
        <span className="badge neutral">Trace target: {latestRunTarget}</span>
      </section>

      <section className="panel evalNotice" aria-live="polite">
        <span className="badge neutral">Audit data</span>
        <p>{notice}</p>
      </section>

      <div className="auditGrid">
        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Evidence timeline</h2>
              <p>Recent matching events from the governance trail.</p>
            </div>
            <span className="badge neutral">{events.length} event(s)</span>
          </div>
          <div className="timeline">
            {events.length ? (
              events.map((item) => (
                <article className="timelineEvent" key={item.id}>
                  <span className="timelineDot" />
                  <div>
                    <strong>{item.eventType}</strong>
                    <p>
                      {item.actorId} on {item.targetType}:{item.targetId}
                    </p>
                  </div>
                  <span className="badge">{item.actorDepartment}</span>
                  <small>{formatDateLabel(item.createdAt)}</small>
                </article>
              ))
            ) : (
              <p className="emptyState">No audit events matched this filter.</p>
            )}
          </div>
        </section>

        <aside className="panel">
          <div className="panelHeader">
            <div>
              <h2>Explorer filters</h2>
              <p>Filter the event trail by release-evidence fields.</p>
            </div>
          </div>
          <div className="configList">
            <label>
              <span>Event type</span>
              <select value={eventType} onChange={(event) => setEventType(event.target.value)}>
                {eventTypes.map((value) => (
                  <option key={value || "all-events"} value={value}>
                    {value || "All events"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Target type</span>
              <select value={targetType} onChange={(event) => setTargetType(event.target.value)}>
                {targetTypes.map((value) => (
                  <option key={value || "all-targets"} value={value}>
                    {value || "All targets"}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Search</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} />
            </label>
          </div>
        </aside>
      </div>
    </section>
  );
}

function formatDateLabel(value: string) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) {
    return value || "Latest";
  }

  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
