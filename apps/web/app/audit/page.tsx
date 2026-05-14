const events = [
  {
    event: "eval_run.created",
    actor: "eval-api-runner",
    target: "synthetic-corpus-v0.1",
    time: "Latest smoke",
    state: "Captured",
  },
  {
    event: "run.created",
    actor: "local-user",
    target: "Policy RAG Assistant",
    time: "Runtime trace",
    state: "Captured",
  },
  {
    event: "document.indexed",
    actor: "storage-indexer",
    target: "Policy library",
    time: "Ingestion smoke",
    state: "Captured",
  },
  {
    event: "audit.search_api",
    actor: "system",
    target: "Audit Explorer",
    time: "Next sprint",
    state: "Pending",
  },
];

const controls = [
  { label: "Actor", value: "eval-api-runner" },
  { label: "Target", value: "runtime run or eval run" },
  { label: "Event type", value: "created / indexed / published" },
];

export default function AuditPage() {
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
      </div>

      <section className="nextAction">
        <div>
          <span className="badge warn">Audit read API pending</span>
          <strong>Write events are captured; searchable filtering remains the next API surface.</strong>
        </div>
        <span className="badge neutral">Trace-ready</span>
      </section>

      <div className="auditGrid">
        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Evidence timeline</h2>
              <p>Representative event flow for the current Sprint 1 path.</p>
            </div>
          </div>
          <div className="timeline">
            {events.map((item) => (
              <article className="timelineEvent" key={item.event}>
                <span className="timelineDot" />
                <div>
                  <strong>{item.event}</strong>
                  <p>
                    {item.actor} on {item.target}
                  </p>
                </div>
                <span className={`badge ${item.state === "Pending" ? "warn" : ""}`}>
                  {item.state}
                </span>
                <small>{item.time}</small>
              </article>
            ))}
          </div>
        </section>

        <aside className="panel">
          <div className="panelHeader">
            <div>
              <h2>Explorer shape</h2>
              <p>Search fields planned for the read API.</p>
            </div>
          </div>
          <div className="configList">
            {controls.map((control) => (
              <label key={control.label}>
                <span>{control.label}</span>
                <input disabled value={control.value} readOnly />
              </label>
            ))}
          </div>
        </aside>
      </div>
    </section>
  );
}
