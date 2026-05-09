const gates = [
  { name: "Retrieval quality", state: "Planned" },
  { name: "Answer groundedness", state: "Planned" },
  { name: "Policy refusal", state: "Planned" },
  { name: "Regression suite", state: "Planned" },
];

export default function EvalPage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">Quality gates</p>
        <h1>Evaluation</h1>
        <p>Track quality, safety, and release-readiness checks before agent publication.</p>
      </div>
      <section className="panel">
        <h2>Gate backlog</h2>
        <ul className="statusList">
          {gates.map((gate) => (
            <li key={gate.name}>
              <span>{gate.name}</span>
              <span className="badge warn">{gate.state}</span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}

