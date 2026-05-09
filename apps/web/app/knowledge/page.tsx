const sourceTypes = [
  "Policy documents",
  "Operating procedures",
  "Product knowledge",
  "Pilot evaluation sets",
];

export default function KnowledgePage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">RAG data</p>
        <h1>Knowledge</h1>
        <p>Register source ownership, confidentiality level, document checksum, and access groups.</p>
      </div>
      <div className="cardGrid">
        {sourceTypes.map((sourceType) => (
          <article className="card" key={sourceType}>
            <h3>{sourceType}</h3>
            <p>Prepared for ingestion controls and document-level audit trails.</p>
          </article>
        ))}
      </div>
    </section>
  );
}

