import Link from "next/link";

const stats = [
  { label: "Access control", value: "RBAC + ACL", note: "enforced in-query at retrieval" },
  { label: "Answers", value: "Cited", note: "mandatory citations, eval-tracked" },
  { label: "Deployment", value: "On-prem", note: "closed-network / self-hosted" },
];

// Delivered, CI-verified capabilities (permission-scoped RAG Q&A end to end).
// Pilot entry itself is a separate organizational decision (SSO, pilot documents),
// not a per-workspace status — see docs/status-and-go-no-go.md.
const workstreams = [
  { name: "Knowledge & document ACL", status: "Live" },
  { name: "Agent registry & versioning", status: "Live" },
  { name: "Runs & retrieval tracing", status: "Live" },
  { name: "Evaluation history", status: "Live" },
  { name: "Audit log", status: "Live" },
];

export default function Home() {
  return (
    <section className="page">
      <div className="header">
        <div>
          <p className="eyebrow">Pilot readiness</p>
          <h1>Governed agent build workspace</h1>
          <p>
            Permission-scoped RAG question answering with mandatory citations, document-level
            ACL/RBAC, and a full audit trail — built and verified end to end.
          </p>
        </div>
        <div className="buttonRow">
          <Link className="button" href="/agents">
            Agents
          </Link>
          <Link className="button secondary" href="/knowledge">
            Knowledge
          </Link>
        </div>
      </div>

      <div className="statGrid">
        {stats.map((item) => (
          <div className="stat" key={item.label}>
            <strong>{item.value}</strong>
            <h3>{item.label}</h3>
            <p>{item.note}</p>
          </div>
        ))}
      </div>

      <section className="panel">
        <h2>Workspace capabilities</h2>
        <ul className="statusList">
          {workstreams.map((item) => (
            <li key={item.name}>
              <span>{item.name}</span>
              <span className={item.status === "Planned" ? "badge warn" : "badge success"}>
                {item.status}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
