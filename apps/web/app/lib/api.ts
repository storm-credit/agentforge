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
  agent_id: string; knowledge_source_ids: string[];
}): Promise<{ id: string }> {
  const r = await fetch(`${API_BASE}/agents/versions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...OPERATOR },
    body: JSON.stringify({
      agent_id: input.agent_id,
      version: 1,
      status: "draft",
      config: { citation_required: true, knowledge_source_ids: input.knowledge_source_ids },
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
