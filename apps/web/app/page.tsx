import Link from "next/link";

const stats = [
  { label: "Sprint 0 scope", value: "7", note: "foundation work items" },
  { label: "Governance gates", value: "4", note: "draft, review, eval, release" },
  { label: "Primary use case", value: "RAG", note: "secure internal assistant" },
];

const workstreams = [
  { name: "API foundation", status: "Started" },
  { name: "Web workbench", status: "Started" },
  { name: "Postgres migrations", status: "Started" },
  { name: "Evaluation harness", status: "Planned" },
];

export default function Home() {
  return (
    <section className="page">
      <div className="header">
        <div>
          <p className="eyebrow">Pilot readiness</p>
          <h1>Governed agent build workspace</h1>
          <p>
            Sprint 0 now has the first executable shape: API service, metadata models,
            web navigation, and local compose dependencies.
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
        <h2>Sprint 0 workstream state</h2>
        <ul className="statusList">
          {workstreams.map((item) => (
            <li key={item.name}>
              <span>{item.name}</span>
              <span className={item.status === "Planned" ? "badge warn" : "badge"}>
                {item.status}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}

