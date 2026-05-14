export type AuditEvent = {
  id: string;
  eventType: string;
  actorId: string;
  actorDepartment: string;
  targetType: string;
  targetId: string;
  reason: string;
  payload: Record<string, unknown>;
  createdAt: string;
};

export type AuditApiResult = {
  ok: boolean;
  data?: AuditEvent[];
  endpoint?: string;
  error?: string;
};

const requestTimeoutMs = 2500;
const endpointRoots = buildEndpointRoots();

function buildEndpointRoots() {
  const configuredBase = process.env.NEXT_PUBLIC_AGENT_FORGE_API_BASE_URL;
  const roots = [];

  if (configuredBase) {
    const normalizedBase = configuredBase.replace(/\/$/, "");
    roots.push(normalizedBase.endsWith("/audit") ? normalizedBase : `${normalizedBase}/audit`);
  }

  roots.push("/api/v1/audit", "/api/audit");
  return Array.from(new Set(roots));
}

function joinEndpoint(root: string, path: string) {
  const normalizedRoot = root.endsWith("/") ? root.slice(0, -1) : root;
  const normalizedPath = path.startsWith("/") ? path.slice(1) : path;
  return `${normalizedRoot}/${normalizedPath}`;
}

export async function fetchAuditEvents(params: {
  eventType?: string;
  targetType?: string;
  query?: string;
}): Promise<AuditApiResult> {
  const searchParams = new URLSearchParams({ limit: "50" });
  if (params.eventType) {
    searchParams.set("event_type", params.eventType);
  }
  if (params.targetType) {
    searchParams.set("target_type", params.targetType);
  }
  if (params.query) {
    searchParams.set("q", params.query);
  }

  let lastError = "Audit API is not available yet.";

  for (const root of endpointRoots) {
    const endpoint = joinEndpoint(root, `events?${searchParams.toString()}`);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs);

    try {
      const response = await fetch(endpoint, { signal: controller.signal });
      if (!response.ok) {
        lastError = `${response.status} ${response.statusText}`.trim();
        continue;
      }

      const data = (await response.json()) as unknown[];
      return {
        ok: true,
        data: data.map(mapAuditEvent).filter((event): event is AuditEvent => event !== null),
        endpoint,
      };
    } catch (error) {
      lastError = error instanceof Error ? error.message : "Audit API request failed.";
    } finally {
      window.clearTimeout(timeout);
    }
  }

  return { ok: false, error: lastError };
}

function mapAuditEvent(payload: unknown): AuditEvent | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Record<string, unknown>;
  const id = stringField(record, "id");
  if (!id) {
    return null;
  }

  return {
    id,
    eventType: stringField(record, "event_type") ?? stringField(record, "eventType") ?? "event",
    actorId: stringField(record, "actor_id") ?? stringField(record, "actorId") ?? "system",
    actorDepartment:
      stringField(record, "actor_department") ?? stringField(record, "actorDepartment") ?? "unknown",
    targetType: stringField(record, "target_type") ?? stringField(record, "targetType") ?? "target",
    targetId: stringField(record, "target_id") ?? stringField(record, "targetId") ?? "target",
    reason: stringField(record, "reason") ?? "",
    payload: asRecord(record.payload) ?? {},
    createdAt: stringField(record, "created_at") ?? stringField(record, "createdAt") ?? "",
  };
}

function stringField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}
