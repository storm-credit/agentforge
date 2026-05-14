import Link from "next/link";

const readinessStats = [
  { label: "Release gate", value: "83%", note: "5 of 6 checks passing", tone: "" },
  { label: "Open blockers", value: "1", note: "Real vector adapter", tone: "warn" },
  { label: "Eval corpus", value: "30", note: "API-backed cases", tone: "" },
];

const releaseSteps = [
  { label: "Agent card", status: "Ready", detail: "Owner, purpose, runtime config locked" },
  { label: "Knowledge", status: "Ready", detail: "Upload, index, ACL preview verified" },
  { label: "Runtime trace", status: "Ready", detail: "Runs, steps, retrieval hits stored" },
  { label: "Eval report", status: "Ready", detail: "Persisted through /api/v1/eval" },
  { label: "Trace viewer", status: "Ready", detail: "Step payloads and retrieval comparison wired" },
];

const evidence = [
  {
    name: "API-backed eval",
    owner: "QA/Eval",
    state: "Passed",
    target: "/eval",
  },
  {
    name: "Real ingestion smoke",
    owner: "Backend + RAG",
    state: "Passed",
    target: "/knowledge",
  },
  {
    name: "Audit event coverage",
    owner: "Security",
    state: "Passed",
    target: "/audit",
  },
];

export default function Home() {
  return (
    <section className="page overviewPage">
      <div className="header">
        <div>
          <p className="eyebrow">Pilot readiness</p>
          <h1>Agent readiness control</h1>
          <p>
            Move the pilot RAG assistant through governed knowledge, runtime trace, eval,
            and audit gates before release.
          </p>
        </div>
        <div className="buttonRow">
          <Link className="button" href="/agents">
            Review agent
          </Link>
          <Link className="button secondary" href="/eval">
            Open eval
          </Link>
        </div>
      </div>

      <section className="nextAction">
        <div>
          <span className="badge warn">Next required action</span>
          <strong>Connect the next real vector adapter behind the retrieval trace.</strong>
        </div>
        <Link className="button secondary" href="/audit">
          Inspect evidence
        </Link>
      </section>

      <div className="statGrid">
        {readinessStats.map((item) => (
          <div className={`stat ${item.tone}`} key={item.label}>
            <strong>{item.value}</strong>
            <h3>{item.label}</h3>
            <p>{item.note}</p>
          </div>
        ))}
      </div>

      <div className="readinessGrid">
        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Release path</h2>
              <p>Current gate state for the pilot policy assistant.</p>
            </div>
            <span className="badge warn">One review item</span>
          </div>
          <ol className="releasePath">
            {releaseSteps.map((step, index) => (
              <li key={step.label}>
                <span className="stepIndex">{index + 1}</span>
                <div>
                  <strong>{step.label}</strong>
                  <p>{step.detail}</p>
                </div>
                <span className={`badge ${step.status === "Needs review" ? "warn" : ""}`}>
                  {step.status}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Evidence queue</h2>
              <p>Artifacts the orchestrator can cite in a release decision.</p>
            </div>
          </div>
          <div className="evidenceList">
            {evidence.map((item) => (
              <Link className="evidenceRow" href={item.target} key={item.name}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.owner}</span>
                </div>
                <span className={`badge ${item.state === "Review" ? "warn" : ""}`}>
                  {item.state}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
