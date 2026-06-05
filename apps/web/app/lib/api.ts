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
