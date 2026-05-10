"use client";

import { ChangeEvent, FormEvent, useMemo, useState, useTransition } from "react";
import {
  fetchKnowledgeDocuments,
  fetchKnowledgeSources,
  KnowledgeDocument,
  KnowledgeSource,
  previewRetrieval,
  queueKnowledgeIndex,
  RetrievalPreviewResult,
  uploadKnowledgeDocument,
} from "./api";

const seedSources: KnowledgeSource[] = [
  {
    id: "policies",
    name: "Policy library",
    owner: "Risk Operations",
    confidentiality: "Restricted",
    accessGroups: ["risk-ops", "pilot-builders"],
    status: "Ready",
    documentCount: 3,
    indexedCount: 2,
    lastIndexedAt: "May 10, 2026",
  },
  {
    id: "procedures",
    name: "Operating procedures",
    owner: "Support Enablement",
    confidentiality: "Internal",
    accessGroups: ["support", "pilot-builders"],
    status: "Draft",
    documentCount: 2,
    indexedCount: 1,
    lastIndexedAt: "May 8, 2026",
  },
  {
    id: "product",
    name: "Product knowledge",
    owner: "Product Ops",
    confidentiality: "Internal",
    accessGroups: ["product", "support"],
    status: "Needs review",
    documentCount: 2,
    indexedCount: 0,
    lastIndexedAt: null,
  },
];

const seedDocuments: KnowledgeDocument[] = [
  {
    id: "policy-refunds",
    sourceId: "policies",
    title: "Refund exception policy",
    checksum: "sha256:7b2d1c",
    status: "Indexed",
    chunkCount: 18,
    updatedAt: "May 10, 2026",
    sizeLabel: "214 KB",
  },
  {
    id: "policy-retention",
    sourceId: "policies",
    title: "Customer data retention rules",
    checksum: "sha256:31f8aa",
    status: "Indexed",
    chunkCount: 24,
    updatedAt: "May 9, 2026",
    sizeLabel: "340 KB",
  },
  {
    id: "policy-vendors",
    sourceId: "policies",
    title: "Vendor handling checklist",
    checksum: "sha256:draft",
    status: "Queued",
    chunkCount: 9,
    updatedAt: "May 10, 2026",
    sizeLabel: "118 KB",
  },
  {
    id: "procedure-escalation",
    sourceId: "procedures",
    title: "Tier 2 escalation procedure",
    checksum: "sha256:a17c04",
    status: "Indexed",
    chunkCount: 16,
    updatedAt: "May 8, 2026",
    sizeLabel: "188 KB",
  },
  {
    id: "procedure-handoff",
    sourceId: "procedures",
    title: "Agent handoff playbook",
    checksum: "sha256:0e3bd2",
    status: "Draft",
    chunkCount: 0,
    updatedAt: "May 10, 2026",
    sizeLabel: "92 KB",
  },
  {
    id: "product-pricing",
    sourceId: "product",
    title: "Pricing package notes",
    checksum: "sha256:needs-review",
    status: "Draft",
    chunkCount: 0,
    updatedAt: "May 7, 2026",
    sizeLabel: "156 KB",
  },
  {
    id: "product-roadmap",
    sourceId: "product",
    title: "Roadmap FAQ extracts",
    checksum: "sha256:pending",
    status: "Draft",
    chunkCount: 0,
    updatedAt: "May 6, 2026",
    sizeLabel: "122 KB",
  },
];

const starterPreview: RetrievalPreviewResult[] = [
  {
    id: "preview-1",
    documentTitle: "Refund exception policy",
    sourceName: "Policy library",
    excerpt:
      "Refund exceptions require source ownership, policy version, approving department, and a traceable customer-impact reason.",
    score: 0.87,
  },
  {
    id: "preview-2",
    documentTitle: "Customer data retention rules",
    sourceName: "Policy library",
    excerpt:
      "Retention answers should cite the governing rule and avoid exposing restricted fields outside the approved access group.",
    score: 0.81,
  },
];

const statusTone: Record<KnowledgeDocument["status"], string> = {
  Indexed: "",
  Queued: "warn",
  Draft: "neutral",
  Failed: "danger",
};

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${Math.round(kb)} KB`;
  }

  return `${(kb / 1024).toFixed(1)} MB`;
}

function buildLocalPreview(
  query: string,
  source: KnowledgeSource,
  documents: KnowledgeDocument[],
): RetrievalPreviewResult[] {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((term) => term.length > 2);

  return documents
    .map((document, index) => {
      const title = document.title.toLowerCase();
      const matches = terms.filter((term) => title.includes(term)).length;
      const statusBoost = document.status === "Indexed" ? 0.12 : 0;
      const score = Math.min(0.96, 0.68 + matches * 0.08 + statusBoost - index * 0.03);

      return {
        id: `local-preview-${document.id}`,
        documentTitle: document.title,
        sourceName: source.name,
        excerpt:
          document.status === "Indexed"
            ? `${document.title} is indexed and available for grounded answers with checksum ${document.checksum}.`
            : `${document.title} is visible in the ingestion queue and should be indexed before release use.`,
        score,
      };
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, 3);
}

export function KnowledgeWorkspace() {
  const [sources, setSources] = useState(seedSources);
  const [documents, setDocuments] = useState(seedDocuments);
  const [selectedSourceId, setSelectedSourceId] = useState(seedSources[0].id);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState(
    seedDocuments.filter((document) => document.sourceId === seedSources[0].id).map((document) => document.id),
  );
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadOwner, setUploadOwner] = useState("Risk Operations");
  const [uploadAccessGroup, setUploadAccessGroup] = useState("pilot-builders");
  const [uploadChecksum, setUploadChecksum] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [query, setQuery] = useState("Can the agent explain refund exceptions?");
  const [retrievalResults, setRetrievalResults] = useState(starterPreview);
  const [apiNotice, setApiNotice] = useState(
    "Local planning data is loaded. Use Sync API when the ingestion service is available.",
  );
  const [indexNotice, setIndexNotice] = useState("No index job queued in this session.");
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const selectedSource = useMemo(
    () => sources.find((source) => source.id === selectedSourceId) ?? sources[0],
    [selectedSourceId, sources],
  );

  const sourceDocuments = useMemo(
    () => documents.filter((document) => document.sourceId === selectedSource.id),
    [documents, selectedSource.id],
  );

  const selectedDocuments = useMemo(
    () => sourceDocuments.filter((document) => selectedDocumentIds.includes(document.id)),
    [selectedDocumentIds, sourceDocuments],
  );

  const indexedDocumentCount = documents.filter((document) => document.status === "Indexed").length;
  const queuedDocumentCount = documents.filter((document) => document.status === "Queued").length;
  const chunkCount = documents.reduce((total, document) => total + document.chunkCount, 0);

  function selectSource(sourceId: string) {
    const nextDocumentIds = documents
      .filter((document) => document.sourceId === sourceId)
      .map((document) => document.id);

    setSelectedSourceId(sourceId);
    setSelectedDocumentIds(nextDocumentIds);
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((selectedId) => selectedId !== documentId)
        : [...current, documentId],
    );
  }

  async function syncWithApi() {
    setPendingAction("sync");

    const [sourceResult, documentResult] = await Promise.all([
      fetchKnowledgeSources(),
      fetchKnowledgeDocuments(),
    ]);

    if (sourceResult.ok && sourceResult.data?.length) {
      const syncedDocuments = documentResult.data ?? [];
      setSources(
        sourceResult.data.map((source) => {
          const sourceDocuments = syncedDocuments.filter((document) => document.sourceId === source.id);
          return {
            ...source,
            documentCount: sourceDocuments.length,
            indexedCount: sourceDocuments.filter((document) => document.status === "Indexed").length,
          };
        }),
      );
      setSelectedSourceId(sourceResult.data[0].id);
    }

    if (documentResult.ok && documentResult.data?.length) {
      setDocuments(documentResult.data);
      setSelectedDocumentIds(
        documentResult.data
          .filter((document) => document.sourceId === (sourceResult.data?.[0]?.id ?? selectedSourceId))
          .map((document) => document.id),
      );
    }

    if (sourceResult.ok || documentResult.ok) {
      setApiNotice(
        `Synced from ${sourceResult.endpoint ?? documentResult.endpoint ?? "knowledge API"}.`,
      );
    } else {
      setApiNotice(
        `API not ready (${sourceResult.error ?? documentResult.error}). Continuing with local planning data.`,
      );
    }

    setPendingAction(null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const title = uploadTitle.trim();
    if (!title) {
      setApiNotice("Add a document title before registering a document.");
      return;
    }

    setPendingAction("upload");

    const checksum = uploadChecksum.trim() || `sha256:local-${Date.now().toString(16)}`;
    const result = await uploadKnowledgeDocument({
      sourceId: selectedSource.id,
      title,
      owner: uploadOwner.trim() || selectedSource.owner,
      accessGroup: uploadAccessGroup.trim() || selectedSource.accessGroups[0],
      checksum,
      file: uploadFile,
    });

    const localDocument: KnowledgeDocument = result.data ?? {
      id: `local-${Date.now()}`,
      sourceId: selectedSource.id,
      title,
      checksum,
      status: "Draft",
      chunkCount: uploadFile ? Math.max(3, Math.ceil(uploadFile.size / 1800)) : 0,
      updatedAt: "Just now",
      sizeLabel: uploadFile ? formatBytes(uploadFile.size) : "Metadata only",
    };

    setDocuments((current) => [localDocument, ...current]);
    setSelectedDocumentIds((current) => [localDocument.id, ...current]);
    setSources((current) =>
      current.map((source) =>
        source.id === selectedSource.id
          ? {
              ...source,
              documentCount: source.documentCount + 1,
              status: source.status === "Ready" ? "Draft" : source.status,
            }
          : source,
      ),
    );
    setApiNotice(
      result.ok
        ? `Registered ${title} through ${result.endpoint}.`
        : `Registered ${title} locally. API response: ${result.error}.`,
    );
    setUploadTitle("");
    setUploadChecksum("");
    setUploadFile(null);
    setFileInputKey((current) => current + 1);
    setPendingAction(null);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setUploadFile(event.target.files?.[0] ?? null);
  }

  async function handleQueueIndex() {
    const documentIds = selectedDocuments.map((document) => document.id);

    if (!documentIds.length) {
      setIndexNotice("Select at least one document before queueing an index job.");
      return;
    }

    setPendingAction("index");
    const result = await queueKnowledgeIndex(selectedSource.id, documentIds);
    const queuedChunks = selectedDocuments.reduce(
      (total, document) => total + Math.max(document.chunkCount, 6),
      0,
    );

    setDocuments((current) =>
      current.map((document) =>
        documentIds.includes(document.id)
          ? { ...document, status: result.ok && result.data?.status === "Complete" ? "Indexed" : "Queued" }
          : document,
      ),
    );
    setSources((current) =>
      current.map((source) =>
        source.id === selectedSource.id ? { ...source, lastIndexedAt: "Queued now" } : source,
      ),
    );
    setIndexNotice(
      result.ok && result.data
        ? `${result.data.message} ${result.data.documentsQueued} document(s), ${result.data.chunksEstimated} estimated chunks.`
        : `Queued ${documentIds.length} document(s) locally with ${queuedChunks} estimated chunks. API response: ${result.error}.`,
    );
    setPendingAction(null);
  }

  async function handlePreviewRetrieval() {
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setApiNotice("Enter a retrieval question before previewing results.");
      return;
    }

    setPendingAction("preview");
    const result = await previewRetrieval(trimmedQuery, selectedSource.id);

    if (result.ok && result.data?.length) {
      setRetrievalResults(result.data);
      setApiNotice(`Retrieval preview loaded from ${result.endpoint}.`);
    } else {
      setRetrievalResults(buildLocalPreview(trimmedQuery, selectedSource, sourceDocuments));
      setApiNotice(
        `Retrieval preview is using local ranking because the API is not ready (${result.error}).`,
      );
    }

    setPendingAction(null);
  }

  return (
    <section className="page knowledgePage">
      <div className="header">
        <div>
          <p className="eyebrow">RAG data</p>
          <h1>Knowledge</h1>
          <p>
            Register source ownership, upload documents, queue indexing, and preview retrieval
            before an agent version can rely on the collection.
          </p>
        </div>
        <div className="buttonRow">
          <button
            className="button secondary"
            disabled={pendingAction === "sync" || isPending}
            type="button"
            onClick={() => startTransition(() => void syncWithApi())}
          >
            {pendingAction === "sync" ? "Syncing" : "Sync API"}
          </button>
        </div>
      </div>

      <div className="statGrid knowledgeStats">
        <div className="stat">
          <strong>{sources.length}</strong>
          <h3>Sources</h3>
          <p>{selectedSource.name} selected</p>
        </div>
        <div className="stat">
          <strong>{documents.length}</strong>
          <h3>Documents</h3>
          <p>{indexedDocumentCount} indexed</p>
        </div>
        <div className="stat">
          <strong>{chunkCount}</strong>
          <h3>Chunks</h3>
          <p>{queuedDocumentCount} queued for refresh</p>
        </div>
      </div>

      <section className="panel knowledgeNotice" aria-live="polite">
        <span className="badge neutral">API state</span>
        <p>{apiNotice}</p>
      </section>

      <section className="knowledgeFlow" aria-label="Knowledge ingestion flow">
        {["Sources", "Documents", "Upload", "Index", "Retrieval preview"].map((step, index) => (
          <div className="flowStep" key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
          </div>
        ))}
      </section>

      <div className="knowledgeGrid">
        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Sources</h2>
              <p>Choose the collection whose ownership and access rules apply to uploads.</p>
            </div>
          </div>
          <div className="sourceList" role="list">
            {sources.map((source) => (
              <button
                className={`sourceOption ${source.id === selectedSource.id ? "active" : ""}`}
                key={source.id}
                type="button"
                onClick={() => selectSource(source.id)}
              >
                <span>
                  <strong>{source.name}</strong>
                  <small>{source.owner}</small>
                </span>
                <span className={source.status === "Ready" ? "badge" : "badge warn"}>
                  {source.status}
                </span>
              </button>
            ))}
          </div>
          <dl className="metadataList">
            <div>
              <dt>Confidentiality</dt>
              <dd>{selectedSource.confidentiality}</dd>
            </div>
            <div>
              <dt>Access groups</dt>
              <dd>{selectedSource.accessGroups.join(", ")}</dd>
            </div>
            <div>
              <dt>Last indexed</dt>
              <dd>{selectedSource.lastIndexedAt ?? "Not indexed yet"}</dd>
            </div>
          </dl>
        </section>

        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Documents</h2>
              <p>Select documents to include in the next index job.</p>
            </div>
            <span className="badge neutral">{sourceDocuments.length} total</span>
          </div>
          <div className="documentList" role="list">
            {sourceDocuments.map((document) => (
              <label className="documentRow" key={document.id}>
                <input
                  checked={selectedDocumentIds.includes(document.id)}
                  type="checkbox"
                  onChange={() => toggleDocument(document.id)}
                />
                <span className="documentMain">
                  <strong>{document.title}</strong>
                  <small>
                    {document.checksum} · {document.sizeLabel} · {document.updatedAt}
                  </small>
                </span>
                <span className={`badge ${statusTone[document.status]}`}>{document.status}</span>
              </label>
            ))}
          </div>
        </section>
      </div>

      <div className="knowledgeGrid">
        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Upload</h2>
              <p>Add a new document with the minimum metadata needed for audit.</p>
            </div>
          </div>
          <form className="knowledgeForm" onSubmit={handleUpload}>
            <label>
              <span>Document title</span>
              <input
                name="title"
                placeholder="Example: Q2 support policy addendum"
                value={uploadTitle}
                onChange={(event) => setUploadTitle(event.target.value)}
              />
            </label>
            <div className="fieldGrid">
              <label>
                <span>Owner</span>
                <input value={uploadOwner} onChange={(event) => setUploadOwner(event.target.value)} />
              </label>
              <label>
                <span>Access group</span>
                <input
                  value={uploadAccessGroup}
                  onChange={(event) => setUploadAccessGroup(event.target.value)}
                />
              </label>
            </div>
            <label>
              <span>Checksum</span>
              <input
                placeholder="sha256:..."
                value={uploadChecksum}
                onChange={(event) => setUploadChecksum(event.target.value)}
              />
            </label>
            <label>
              <span>File</span>
              <input key={fileInputKey} type="file" onChange={handleFileChange} />
            </label>
            <button className="button" disabled={pendingAction === "upload"} type="submit">
              {pendingAction === "upload" ? "Registering" : "Upload document"}
            </button>
          </form>
        </section>

        <section className="panel indexPanel">
          <div className="panelHeader">
            <div>
              <h2>Index</h2>
              <p>Queue selected documents and review the expected retrieval surface.</p>
            </div>
            <span className="badge neutral">{selectedDocuments.length} selected</span>
          </div>
          <div className="indexSummary">
            <strong>{selectedSource.name}</strong>
            <p>{indexNotice}</p>
          </div>
          <button
            className="button"
            disabled={pendingAction === "index" || !selectedDocuments.length}
            type="button"
            onClick={handleQueueIndex}
          >
            {pendingAction === "index" ? "Queueing" : "Queue index"}
          </button>
        </section>
      </div>

      <section className="panel retrievalPanel">
        <div className="panelHeader">
          <div>
            <h2>Retrieval preview</h2>
            <p>Run a sample question against the selected source before wiring an agent to it.</p>
          </div>
        </div>
        <div className="retrievalControls">
          <label>
            <span>Question</span>
            <textarea
              rows={3}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <button
            className="button"
            disabled={pendingAction === "preview"}
            type="button"
            onClick={handlePreviewRetrieval}
          >
            {pendingAction === "preview" ? "Previewing" : "Preview retrieval"}
          </button>
        </div>
        <div className="retrievalResults" role="list">
          {retrievalResults.map((result) => (
            <article className="retrievalResult" key={result.id}>
              <div>
                <strong>{result.documentTitle}</strong>
                <span>{result.sourceName}</span>
              </div>
              <p>{result.excerpt}</p>
              <span className="score">{Math.round(result.score * 100)}% match</span>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
