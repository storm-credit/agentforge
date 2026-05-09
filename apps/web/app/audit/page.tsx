const events = [
  "agent.created",
  "agent_version.created",
  "knowledge_source.created",
  "document.registered",
];

export default function AuditPage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">Governance</p>
        <h1>Audit</h1>
        <p>Review metadata changes with actor, department, target, reason, and event payload.</p>
      </div>
      <section className="panel">
        <h2>Current event draft</h2>
        <ul className="statusList">
          {events.map((event) => (
            <li key={event}>
              <span>{event}</span>
              <span className="badge">Captured</span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}

