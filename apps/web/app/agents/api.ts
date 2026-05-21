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
  question: string;
  knowledge: string;
};

const requestTimeoutMs = 2500;

export async function submitAgentRun(request: AgentRunRequest): Promise<AgentRunResult> {
  const apiResult = await submitApiRun(request);

  if (apiResult) {
    return apiResult;
  }

  return buildLocalRun(request);
}

async function submitApiRun(request: AgentRunRequest): Promise<AgentRunResult | null> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs);

  try {
    const response = await fetch("/api/v1/runs", {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        agent_id: request.agentId,
        agent_name: request.agentName,
        input: {
          message: request.question,
        },
        metadata: {
          source: "agent-studio-test-chat",
        },
      }),
    });

    if (!response.ok) {
      return null;
    }

    return normalizeRunPayload(await response.json());
  } catch {
    return null;
  } finally {
    window.clearTimeout(timeout);
  }
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
      (citations.length > 0 ? "passed" : "not_applicable_no_citations"),
    source: "api",
  };
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

function arrayField(record: Record<string, unknown>, key: string): unknown[] {
  const value = record[key];
  return Array.isArray(value) ? value : [];
}

function stringField(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}
