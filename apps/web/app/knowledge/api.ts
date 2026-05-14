export type KnowledgeSourceStatus = "Ready" | "Draft" | "Needs review";

export type DocumentIndexStatus = "Indexed" | "Queued" | "Draft" | "Failed";

export type KnowledgeSource = {
  id: string;
  name: string;
  owner: string;
  confidentiality: "Public" | "Internal" | "Restricted";
  accessGroups: string[];
  status: KnowledgeSourceStatus;
  documentCount: number;
  indexedCount: number;
  lastIndexedAt: string | null;
};

export type KnowledgeDocument = {
  id: string;
  sourceId: string;
  title: string;
  checksum: string;
  status: DocumentIndexStatus;
  chunkCount: number;
  updatedAt: string;
  sizeLabel: string;
};

export type RetrievalPreviewResult = {
  id: string;
  documentTitle: string;
  sourceName: string;
  excerpt: string;
  score: number;
};

export type IndexJobSummary = {
  sourceId: string;
  status: "Queued" | "Running" | "Complete";
  message: string;
  documentsQueued: number;
  chunksEstimated: number;
};

export type UploadDocumentInput = {
  sourceId: string;
  title: string;
  owner: string;
  accessGroup: string;
  checksum: string;
  file?: File | null;
};

export type KnowledgeApiResult<T> = {
  ok: boolean;
  data?: T;
  endpoint?: string;
  error?: string;
};

type BackendKnowledgeSource = {
  id: string;
  name: string;
  owner_department: string;
  default_confidentiality_level: string;
  status: string;
  updated_at: string;
};

type BackendDocument = {
  id: string;
  knowledge_source_id: string;
  title: string;
  checksum: string;
  status: string;
  access_groups: string[];
  updated_at: string;
};

type BackendIndexJob = {
  status: string;
  chunk_count: number;
  error_code: string | null;
};

type BackendRetrievalPreviewResponse = {
  hits: Array<{
    document_id: string;
    title: string;
    citation: string;
    citation_locator: string | null;
    score: number;
  }>;
};

const endpointRoots = buildEndpointRoots();
const requestTimeoutMs = 2500;

function buildEndpointRoots() {
  const configuredBase = process.env.NEXT_PUBLIC_AGENT_FORGE_API_BASE_URL;
  const roots = [];

  if (configuredBase) {
    const normalizedBase = configuredBase.replace(/\/$/, "");
    roots.push(
      normalizedBase.endsWith("/knowledge") ? normalizedBase : `${normalizedBase}/knowledge`,
    );
  }

  roots.push("/api/v1/knowledge", "/api/knowledge");
  return Array.from(new Set(roots));
}

function joinEndpoint(root: string, path: string) {
  const normalizedRoot = root.endsWith("/") ? root.slice(0, -1) : root;
  const normalizedPath = path.startsWith("/") ? path.slice(1) : path;
  return `${normalizedRoot}/${normalizedPath}`;
}

function withQuery(path: string, query: Record<string, string | undefined>) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value) {
      params.set(key, value);
    }
  }

  const serialized = params.toString();
  return serialized ? `${path}?${serialized}` : path;
}

async function requestKnowledge<T>(
  paths: string[],
  init?: RequestInit,
): Promise<KnowledgeApiResult<T>> {
  let lastError = "Knowledge API is not available yet.";

  for (const root of endpointRoots) {
    for (const path of paths) {
      const endpoint = joinEndpoint(root, path);
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs);

      try {
        const response = await fetch(endpoint, {
          ...init,
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
            ...init?.headers,
          },
        });

        if (!response.ok) {
          lastError = `${response.status} ${response.statusText}`.trim();
          continue;
        }

        if (response.status === 204) {
          return { ok: true, endpoint };
        }

        const data = (await response.json()) as T;
        return { ok: true, data, endpoint };
      } catch (error) {
        lastError = error instanceof Error ? error.message : "Knowledge API request failed.";
      } finally {
        window.clearTimeout(timeout);
      }
    }
  }

  return { ok: false, error: lastError };
}

export async function fetchKnowledgeSources(): Promise<KnowledgeApiResult<KnowledgeSource[]>> {
  const result = await requestKnowledge<BackendKnowledgeSource[]>(["sources"]);

  if (!result.ok || !result.data) {
    return withoutData(result);
  }

  return {
    ...result,
    data: result.data.map(mapKnowledgeSource),
  };
}

export async function fetchKnowledgeDocuments(
  sourceId?: string,
): Promise<KnowledgeApiResult<KnowledgeDocument[]>> {
  const result = await requestKnowledge<BackendDocument[]>(["documents"]);

  if (!result.ok || !result.data) {
    return withoutData(result);
  }

  const documents = sourceId
    ? result.data.filter((document) => document.knowledge_source_id === sourceId)
    : result.data;

  return {
    ...result,
    data: documents.map(mapKnowledgeDocument),
  };
}

export async function uploadKnowledgeDocument(
  input: UploadDocumentInput,
): Promise<KnowledgeApiResult<KnowledgeDocument>> {
  if (!input.file) {
    return {
      ok: false,
      error: "Select a file to send the upload through the API.",
    } satisfies KnowledgeApiResult<KnowledgeDocument>;
  }

  const path = withQuery("documents/upload", {
    knowledge_source_id: input.sourceId,
    title: input.title,
    access_groups: input.accessGroup,
  });
  const result = await requestKnowledge<BackendDocument>([path], {
    method: "POST",
    body: input.file,
    headers: {
      "Content-Type": input.file.type || "application/octet-stream",
      "X-Agent-Forge-Filename": input.file.name,
    },
  });

  if (!result.ok || !result.data) {
    return withoutData(result);
  }

  return {
    ...result,
    data: mapKnowledgeDocument(result.data),
  };
}

export async function queueKnowledgeIndex(
  sourceId: string,
  documentIds: string[],
): Promise<KnowledgeApiResult<IndexJobSummary>> {
  let endpoint: string | undefined;
  let completed = 0;
  let chunksEstimated = 0;
  let lastError = "";

  for (const documentId of documentIds) {
    const result = await requestKnowledge<BackendIndexJob>(
      [`documents/${documentId}/index-jobs`],
      {
        method: "POST",
        body: JSON.stringify({}),
      },
    );

    if (!result.ok || !result.data) {
      lastError = result.error ?? "Index request failed.";
      continue;
    }

    endpoint = result.endpoint;
    if (result.data.status === "succeeded") {
      completed += 1;
      chunksEstimated += Math.max(1, result.data.chunk_count);
    } else if (result.data.status === "failed") {
      lastError = result.data.error_code ?? "Index job failed.";
    }
  }

  if (completed === documentIds.length && documentIds.length > 0) {
    return {
      ok: true,
      endpoint,
      data: {
        sourceId,
        status: "Complete",
        message: "Indexed uploaded object storage document(s).",
        documentsQueued: completed,
        chunksEstimated,
      },
    } satisfies KnowledgeApiResult<IndexJobSummary>;
  }

  return {
    ok: false,
    endpoint,
    error: lastError || "No index jobs completed.",
  } satisfies KnowledgeApiResult<IndexJobSummary>;
}

export async function previewRetrieval(
  query: string,
  sourceId: string,
): Promise<KnowledgeApiResult<RetrievalPreviewResult[]>> {
  const result = await requestKnowledge<BackendRetrievalPreviewResponse>(["retrieval/preview"], {
    method: "POST",
    body: JSON.stringify({
      query,
      knowledge_source_ids: [sourceId],
      top_k: 5,
    }),
  });

  if (!result.ok || !result.data) {
    return withoutData(result);
  }

  return {
    ...result,
    data: result.data.hits.map((hit) => ({
      id: hit.document_id,
      documentTitle: hit.title,
      sourceName: "Selected source",
      excerpt: hit.citation_locator ?? hit.citation,
      score: hit.score,
    })),
  };
}

function mapKnowledgeSource(source: BackendKnowledgeSource): KnowledgeSource {
  return {
    id: source.id,
    name: source.name,
    owner: source.owner_department,
    confidentiality: toConfidentiality(source.default_confidentiality_level),
    accessGroups: ["Configured per document"],
    status: source.status === "active" ? "Ready" : "Draft",
    documentCount: 0,
    indexedCount: 0,
    lastIndexedAt: formatDate(source.updated_at),
  };
}

function withoutData<T>(result: KnowledgeApiResult<unknown>): KnowledgeApiResult<T> {
  return {
    ok: false,
    endpoint: result.endpoint,
    error: result.error,
  };
}

function mapKnowledgeDocument(document: BackendDocument): KnowledgeDocument {
  return {
    id: document.id,
    sourceId: document.knowledge_source_id,
    title: document.title,
    checksum: document.checksum,
    status: toDocumentStatus(document.status),
    chunkCount: document.status === "indexed" ? 1 : 0,
    updatedAt: formatDate(document.updated_at),
    sizeLabel: document.access_groups.length
      ? document.access_groups.join(", ")
      : "No ACL groups",
  };
}

function toConfidentiality(value: string): KnowledgeSource["confidentiality"] {
  if (value === "public") {
    return "Public";
  }
  if (value === "restricted") {
    return "Restricted";
  }
  return "Internal";
}

function toDocumentStatus(value: string): DocumentIndexStatus {
  if (value === "indexed") {
    return "Indexed";
  }
  if (value === "index_failed") {
    return "Failed";
  }
  if (value === "queued") {
    return "Queued";
  }
  return "Draft";
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Just now";
  }
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
