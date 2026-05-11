const events = [
  "agent.created",
  "agent_version.created",
  "knowledge_source.created",
  "document.uploaded",
  "document.indexed",
  "retrieval.previewed",
  "run.created",
  "run.refused",
];

export default function AuditPage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">Governance</p>
        <h1>Audit</h1>
        <p>
          Review the current audit event catalog and runtime trace pointers while the read API is
          being wired.
        </p>
      </div>
      <section className="panel evalNotice">
        <span className="badge warn">Audit read API pending</span>
        <p>
          Write paths and runtime endpoints emit traceable events today; searchable audit history is
          the next API surface.
        </p>
      </section>
      <section className="panel">
        <h2>Current event catalog</h2>
        <ul className="statusList">
          {events.map((event) => (
            <li key={event}>
              <span>{event}</span>
              <span className="badge neutral">Emitted</span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}

