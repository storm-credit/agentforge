export type AgentRunCitation = {
  id: string;
  documentId: string;
  title: string;
  locator: string;
};

export type AgentRunResult = {
  answer: string;
  status: string;
  runId: string;
  citations: AgentRunCitation[];
  guardrailStatus: string;
  citationStatus: string;
  source: "api" | "local";
};

export type AgentRunRequest = {
  agentId: string;
  agentName: string;
  agentVersionId?: string;
  question: string;
  knowledge: string;
  knowledgeSourceIds?: string[];
};

export type AgentOption = {
  key: string;
  id: string;
  name: string;
  owner: string;
  version: string;
  status: string;
  gate: string;
  knowledge: string;
  modelRoute: string;
  next: string;
  tone: "warn" | "neutral" | "danger";
  canTest: boolean;
  source: "api" | "seed";
  agentVersionId?: string;
  knowledgeSourceIds: string[];
};

export type AgentApiResult<T> = {
  ok: boolean;
  data?: T;
  endpoint?: string;
  error?: string;
};

const agentEndpointRoots = buildEndpointRoots("agents");
const runEndpointRoots = buildEndpointRoots("runs");
const requestTimeoutMs = 2500;

export async function fetchAgentCatalog(): Promise<AgentApiResult<AgentOption[]>> {
  const agentsResult = await requestAgentApi<unknown>(agentEndpointRoots, [""]);

  if (!agentsResult.ok || !agentsResult.data) {
    return withoutData(agentsResult);
  }

  const agentRecords = arrayPayload(agentsResult.data)
    .map(asRecord)
    .filter(
      (item): item is Record<string, unknown> =>
        item !== null && Boolean(stringField(item, "id")),
    );

  if (agentRecords.length === 0) {
    return {
      ok: false,
      endpoint: agentsResult.endpoint,
      error: "Agent API returned no agents.",
    };
  }

  const versionResults = await Promise.all(
    agentRecords.map(async (agent) => ({
      agent,
      result: await requestAgentApi<unknown>(
        agentEndpointRoots,
        [`${encodeURIComponent(stringField(agent, "id") ?? "")}/versions`],
      ),
    })),
  );

  const options = versionResults.flatMap(({ agent, result }) => {
    if (!result.ok || !result.data) {
      return [];
    }

    return arrayPayload(result.data)
      .map((version) => mapAgentVersion(agent, version))
      .filter((item): item is AgentOption => item !== null);
  });

  if (options.length === 0) {
    return {
      ok: false,
      endpoint: agentsResult.endpoint,
      error: "Agent API returned no published or validated versions.",
    };
  }

  return {
    ok: true,
    data: options,
    endpoint: versionResults.find(({ result }) => result.endpoint)?.result.endpoint ?? agentsResult.endpoint,
  };
}

export async function submitAgentRun(request: AgentRunRequest): Promise<AgentRunResult> {
  const apiResult = await submitApiRun(request);

  if (apiResult) {
    return apiResult;
  }

  return buildLocalRun(request);
}

async function submitApiRun(request: AgentRunRequest): Promise<AgentRunResult | null> {
  const body: Record<string, unknown> = {
    agent_id: request.agentId,
    agent_name: request.agentName,
    input: {
      message: request.question,
    },
    metadata: {
      source: "agent-studio-test-chat",
    },
  };

  if (request.agentVersionId) {
    body.agent_version_id = request.agentVersionId;
  }

  if (request.knowledgeSourceIds?.length) {
    body.knowledge_source_ids = request.knowledgeSourceIds;
  }

  const result = await requestAgentApi<unknown>(runEndpointRoots, [""], {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!result.ok || !result.data) {
    return null;
  }

  return normalizeRunPayload(result.data);
}

function buildLocalRun(request: AgentRunRequest): AgentRunResult {
  const normalizedQuestion = request.question.toLowerCase();
  const noContext =
    normalizedQuestion.includes("no context") ||
    normalizedQuestion.includes("unsupported") ||
    normalizedQuestion.includes("private") ||
    normalizedQuestion.includes("unknown");

  if (noContext) {
    return {
      answer:
        "I cannot answer from the selected agent knowledge source. No authorized context was found for this request.",
      status: "refused",
      runId: `local-${request.agentId}-refusal`,
      citations: [],
      guardrailStatus: "refusal_no_context",
      citationStatus: "not_applicable_no_citations",
      source: "local",
    };
  }

  const citation =
    request.agentId === "security-policy"
      ? {
          id: "SEC-001",
          documentId: "SEC-001",
          title: "External Data Transfer Procedure",
          locator: "section:approval-flow",
        }
      : {
          id: "POL-001",
          documentId: "POL-001",
          title: "Policy library",
          locator: "section:pilot-guidance",
        };

  return {
    answer: `${request.agentName} would answer from ${request.knowledge} and require cited policy evidence before release use.`,
    status: "succeeded",
    runId: `local-${request.agentId}-answer`,
    citations: [citation],
    guardrailStatus: "answer_allowed",
    citationStatus: "passed",
    source: "local",
  };
}

function normalizeRunPayload(payload: unknown): AgentRunResult | null {
  const record = asRecord(payload);

  if (!record) {
    return null;
  }

  const guardrail = asRecord(record.guardrail) ?? asRecord(record.guardrails);
  const validation = asRecord(record.validation) ?? asRecord(record.citation_validation);
  const citations = arrayField(record, "citations").map(mapCitation).filter((item) => item !== null);
  const citationValidationPassed = booleanField(guardrail ?? {}, "citation_validation_pass");

  return {
    answer:
      stringField(record, "answer") ??
      stringField(record, "final_answer") ??
      stringField(record, "output") ??
      stringField(record, "response") ??
      "Run completed without an answer payload.",
    status: stringField(record, "status") ?? "succeeded",
    runId: stringField(record, "id") ?? stringField(record, "run_id") ?? "runtime-run",
    citations,
    guardrailStatus:
      stringField(guardrail ?? {}, "status") ??
      stringField(guardrail ?? {}, "outcome") ??
      stringField(record, "guardrail_status") ??
      "unknown",
    citationStatus:
      stringField(validation ?? {}, "status") ??
      stringField(record, "citation_status") ??
      (citationValidationPassed !== undefined ? (citationValidationPassed ? "passed" : "failed") : undefined) ??
      (citations.length > 0 ? "passed" : "not_applicable_no_citations"),
    source: "api",
  };
}

function buildEndpointRoots(resource: "agents" | "runs") {
  const configuredBase = process.env.NEXT_PUBLIC_AGENT_FORGE_API_BASE_URL;
  const roots = [];

  if (configuredBase) {
    const normalizedBase = configuredBase.replace(/\/$/, "");
    roots.push(normalizedBase.endsWith(`/${resource}`) ? normalizedBase : `${normalizedBase}/${resource}`);
  }

  roots.push(`/api/v1/${resource}`, `/api/${resource}`);
  return Array.from(new Set(roots));
}

function joinEndpoint(root: string, path: string) {
  const normalizedRoot = root.endsWith("/") ? root.slice(0, -1) : root;
  const normalizedPath = path.startsWith("/") ? path.slice(1) : path;

  return normalizedPath ? `${normalizedRoot}/${normalizedPath}` : normalizedRoot;
}

async function requestAgentApi<T>(
  roots: string[],
  paths: string[],
  init?: RequestInit,
): Promise<AgentApiResult<T>> {
  let lastError = "Agent API is not available yet.";

  for (const root of roots) {
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

        return {
          ok: true,
          data: (await response.json()) as T,
          endpoint,
        };
      } catch (error) {
        lastError = error instanceof Error ? error.message : "Agent API request failed.";
      } finally {
        window.clearTimeout(timeout);
      }
    }
  }

  return { ok: false, error: lastError };
}

function mapAgentVersion(agentPayload: unknown, versionPayload: unknown): AgentOption | null {
  const agent = asRecord(agentPayload);
  const version = asRecord(versionPayload);

  if (!agent || !version) {
    return null;
  }

  const agentId = stringField(agent, "id");
  const agentName = stringField(agent, "name");
  const versionId = stringField(version, "id");
  const rawStatus = stringField(version, "status") ?? stringField(agent, "status") ?? "draft";
  const normalizedStatus = rawStatus.toLowerCase();

  if (!agentId || !agentName || !isTestableVersionStatus(normalizedStatus)) {
    return null;
  }

  const config = asRecord(version.config) ?? {};
  const modelPolicy = asRecord(config.model_policy) ?? asRecord(config.modelPolicy);
  const stages = asRecord(modelPolicy?.stages);
  const answerGenerator = asRecord(stages?.answer_generator) ?? asRecord(stages?.answerGenerator);
  const knowledgeSourceIds = arrayField(config, "knowledge_source_ids")
    .concat(arrayField(config, "knowledgeSourceIds"))
    .filter((item): item is string => typeof item === "string" && item.length > 0);
  const versionLabel = formatVersionLabel(version);
  const statusLabel = titleCase(rawStatus);

  return {
    key: `${agentId}:${versionId ?? versionLabel}`,
    id: agentId,
    name: agentName,
    owner:
      stringField(agent, "owner_department") ??
      stringField(agent, "ownerDepartment") ??
      stringField(agent, "owner") ??
      "Unassigned",
    version: versionLabel,
    status: statusLabel,
    gate: gateLabel(normalizedStatus, version, config),
    knowledge: knowledgeLabel(knowledgeSourceIds),
    modelRoute:
      stringField(modelPolicy ?? {}, "budget_class") ??
      stringField(modelPolicy ?? {}, "budgetClass") ??
      stringField(answerGenerator ?? {}, "tier") ??
      "standard",
    next: normalizedStatus === "published" ? "Trace Viewer link" : "Publish version",
    tone: normalizedStatus === "published" ? "neutral" : "warn",
    canTest: true,
    source: "api",
    agentVersionId: versionId,
    knowledgeSourceIds,
  };
}

function isTestableVersionStatus(status: string) {
  return status === "published" || status === "validated";
}

function formatVersionLabel(version: Record<string, unknown>) {
  const numericVersion = numericField(version, "version");
  if (numericVersion !== undefined) {
    return `v${numericVersion}`;
  }

  return stringField(version, "version") ?? "version";
}

function gateLabel(
  normalizedStatus: string,
  version: Record<string, unknown>,
  config: Record<string, unknown>,
) {
  const score =
    ratioField(version, "gate") ??
    ratioField(version, "gate_score") ??
    ratioField(config, "gate_score") ??
    ratioField(config, "release_gate_score");

  if (score !== undefined) {
    return `${Math.round(score * 100)}%`;
  }

  return normalizedStatus === "published" ? "Live" : "Ready";
}

function knowledgeLabel(knowledgeSourceIds: string[]) {
  if (knowledgeSourceIds.length === 0) {
    return "Agent config";
  }

  if (knowledgeSourceIds.length <= 2) {
    return knowledgeSourceIds.join(", ");
  }

  return `${knowledgeSourceIds.length} knowledge sources`;
}

function titleCase(value: string) {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1).toLowerCase()}`)
    .join(" ");
}

function mapCitation(payload: unknown): AgentRunCitation | null {
  const record = asRecord(payload);

  if (!record) {
    return null;
  }

  const documentId = stringField(record, "document_id") ?? stringField(record, "documentId");
  const title = stringField(record, "title") ?? documentId;

  if (!documentId || !title) {
    return null;
  }

  return {
    id: stringField(record, "id") ?? documentId,
    documentId,
    title,
    locator:
      stringField(record, "citation_locator") ??
      stringField(record, "locator") ??
      stringField(record, "section") ??
      "locator unavailable",
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }

  return value as Record<string, unknown>;
}

function arrayPayload(payload: unknown): unknown[] {
  if (Array.isArray(payload)) {
    return payload;
  }

  const record = asRecord(payload);
  if (!record) {
    return [];
  }

  for (const key of ["items", "data", "agents", "versions"]) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value;
    }
  }

  return [];
}

function arrayField(record: Record<string, unknown>, key: string): unknown[] {
  const value = record[key];
  return Array.isArray(value) ? value : [];
}

function ratioField(record: Record<string, unknown>, key: string) {
  const value = numericField(record, key);

  if (value === undefined) {
    return undefined;
  }

  return value > 1 ? value / 100 : value;
}

function numericField(record: Record<string, unknown>, key: string): number | undefined {
  const value = record[key];

  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  return undefined;
}

function stringField(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function booleanField(record: Record<string, unknown>, key: string): boolean | undefined {
  const value = record[key];
  return typeof value === "boolean" ? value : undefined;
}

function withoutData<T>(result: AgentApiResult<unknown>): AgentApiResult<T> {
  return {
    ok: false,
    endpoint: result.endpoint,
    error: result.error,
  };
}
