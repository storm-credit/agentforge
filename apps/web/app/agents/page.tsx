const stages = [
  "Draft agent metadata",
  "Create versioned runtime config",
  "Run policy and evaluation gates",
  "Publish approved versions",
];

export default function AgentsPage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">Builder</p>
        <h1>Agents</h1>
        <p>Define agent purpose, ownership, versioned configuration, and release status.</p>
      </div>
      <div className="cardGrid">
        {stages.map((stage, index) => (
          <article className="card" key={stage}>
            <h3>{index + 1}. {stage}</h3>
            <p>Backed by the Sprint 0 agent and agent version metadata tables.</p>
          </article>
        ))}
      </div>
    </section>
  );
}

