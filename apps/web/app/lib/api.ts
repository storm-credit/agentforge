export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const MOCK_USERS = {
  finance: {
    "X-Agent-Forge-User": "fin1",
    "X-Agent-Forge-Department": "Finance",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
  },
  hr: {
    "X-Agent-Forge-User": "hr1",
    "X-Agent-Forge-Department": "HR",
    "X-Agent-Forge-Groups": "all-employees,hr-restricted",
    "X-Agent-Forge-Clearance": "restricted",
  },
} as const;

export type MockUserKey = keyof typeof MOCK_USERS;

export async function firstAgentId(): Promise<string | null> {
  const r = await fetch(`${API_BASE}/agents`);
  const list = await r.json();
  return list[0]?.id ?? null;
}

export async function ask(params: {
  agentId: string;
  message: string;
  language: "auto" | "ko" | "en";
  user: MockUserKey;
}) {
  const r = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...MOCK_USERS[params.user] },
    body: JSON.stringify({
      agent_id: params.agentId,
      input: { message: params.message },
      language: params.language,
    }),
  });
  if (!r.ok) throw new Error(`run failed: ${r.status}`);
  return r.json();
}

const OPERATOR = {
  "X-Agent-Forge-User": "operator",
  "X-Agent-Forge-Department": "Operations",
  "X-Agent-Forge-Roles": "admin",
  "X-Agent-Forge-Groups": "all-employees",
  "X-Agent-Forge-Clearance": "internal",
} as const;

export type KnowledgeSource = { id: string; name: string };
export type AgentSummary = {
  id: string; name: string; purpose: string; owner_department: string; status: string;
};

export async function listAgents(): Promise<AgentSummary[]> {
  const r = await fetch(`${API_BASE}/agents`);
  if (!r.ok) throw new Error(`list agents failed: ${r.status}`);
  return r.json();
}

export async function listSources(): Promise<KnowledgeSource[]> {
  const r = await fetch(`${API_BASE}/knowledge/sources`);
  if (!r.ok) throw new Error(`list sources failed: ${r.status}`);
  return r.json();
}

// 소스별 status==="indexed" 문서 수
export async function indexedDocCountBySource(): Promise<Record<string, number>> {
  const r = await fetch(`${API_BASE}/knowledge/documents`);
  if (!r.ok) throw new Error(`list documents failed: ${r.status}`);
  const docs: Array<{ knowledge_source_id: string; status: string }> = await r.json();
  const counts: Record<string, number> = {};
  for (const d of docs) {
    if (d.status === "indexed") {
      counts[d.knowledge_source_id] = (counts[d.knowledge_source_id] ?? 0) + 1;
    }
  }
  return counts;
}

export async function createAgent(input: {
  name: string; purpose: string; owner_department: string;
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({ ...input, status: "draft" }),
  });
  if (!r.ok) throw new Error(`create agent failed: ${r.status}`);
  return r.json();
}

export async function createVersion(input: {
  agent_id: string; knowledge_source_ids: string[]; temperature?: number;
}): Promise<{ id: string }> {
  const config: Record<string, unknown> = {
    citation_required: true,
    knowledge_source_ids: input.knowledge_source_ids,
  };
  if (input.temperature !== undefined) config.temperature = input.temperature;
  const r = await fetch(`${API_BASE}/agents/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({
      agent_id: input.agent_id,
      version: 1,
      status: "draft",
      config,
    }),
  });
  if (!r.ok) throw new Error(`create version failed: ${r.status}`);
  return r.json();
}

export async function publishVersion(versionId: string): Promise<{ id: string; status: string }> {
  const r = await fetch(`${API_BASE}/agents/versions/${versionId}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({ reason: "published via Agent Studio" }),
  });
  if (!r.ok) throw new Error(`publish failed: ${r.status}`);
  return r.json();
}

export type DocumentSummary = {
  id: string; knowledge_source_id: string; title: string; status: string;
};

export async function listDocuments(): Promise<DocumentSummary[]> {
  const r = await fetch(`${API_BASE}/knowledge/documents`);
  if (!r.ok) throw new Error(`list documents failed: ${r.status}`);
  return r.json();
}

export async function sha256Hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function createSource(input: {
  name: string; owner_department: string;
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/knowledge/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify(input),
  });
  if (!r.ok) throw new Error(`create source failed: ${r.status}`);
  return r.json();
}

export async function registerDocument(input: {
  knowledge_source_id: string;
  title: string;
  mime_type: string;
  confidentiality_level: string;
  access_groups: string[];
  object_uri: string;
  checksum: string;
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/knowledge/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({ ...input, status: "registered" }),
  });
  if (!r.ok) throw new Error(`register document failed: ${r.status}`);
  return r.json();
}

export async function uploadDocument(input: {
  knowledge_source_id: string;
  title: string;
  file: File;
  confidentiality_level: string;
  access_groups: string[];
}): Promise<{
  document: { id: string; status: string };
  index_job: {
    status: string;
    chunk_count: number;
    error_code: string | null;
    error_message: string | null;
  };
}> {
  const form = new FormData();
  form.set("knowledge_source_id", input.knowledge_source_id);
  form.set("title", input.title);
  form.set("confidentiality_level", input.confidentiality_level);
  form.set("access_groups", input.access_groups.join(","));
  form.set("file", input.file);

  const r = await fetch(`${API_BASE}/knowledge/documents/upload`, {
    method: "POST",
    headers: { ...OPERATOR },
    body: form,
  });
  if (!r.ok) throw new Error(`upload failed: ${r.status}`);
  return r.json();
}

export async function indexDocument(input: {
  document_id: string; source_text: string;
}): Promise<{ status: string; chunk_count: number; error_code: string | null; error_message: string | null }> {
  const r = await fetch(`${API_BASE}/knowledge/documents/${input.document_id}/index-jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({
      parser_profile: "default-txt-md",
      embedding_model: "bge-m3",
      source_text: input.source_text,
    }),
  });
  if (!r.ok) throw new Error(`index failed: ${r.status}`);
  return r.json();
}

export type RunSummary = {
  id: string;
  input: { message?: string };
  status: string;
  latency_ms: number;
  started_at: string | null;
  answer: string;
  citations: Array<{ title: string; citation_locator: string | null }>;
  guardrail: Record<string, unknown>;
};

export type RunStep = {
  step_order: number;
  step_type: string;
  status: string;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  latency_ms: number;
  error_code: string | null;
  error_message: string | null;
};

export type RetrievalHit = {
  rank_original: number;
  title: string;
  citation_locator: string | null;
  score_vector: number;
  used_in_context: boolean;
  used_as_citation: boolean;
  chunk_id: string | null;
  content?: string | null;
  acl_filter_snapshot: Record<string, unknown>;
};

export async function listRuns(): Promise<RunSummary[]> {
  const r = await fetch(`${API_BASE}/runs`);
  if (!r.ok) throw new Error(`list runs failed: ${r.status}`);
  return r.json();
}

export async function getRunSteps(runId: string): Promise<RunStep[]> {
  const r = await fetch(`${API_BASE}/runs/${runId}/steps`);
  if (!r.ok) throw new Error(`get steps failed: ${r.status}`);
  return r.json();
}

export async function getRunHits(runId: string): Promise<RetrievalHit[]> {
  const r = await fetch(`${API_BASE}/runs/${runId}/retrieval-hits`);
  if (!r.ok) throw new Error(`get hits failed: ${r.status}`);
  return r.json();
}
