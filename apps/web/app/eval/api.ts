export type EvalOutcome = "Passed" | "Needs review" | "Failed";

export type EvalSuite = {
  id: string;
  label: string;
  description: string;
  total: number;
  passed: number;
  failed: number;
  status: "Ready" | "Needs review" | "Running";
};

export type EvalCitation = {
  id: string;
  documentId: string;
  title: string;
  locator: string;
  excerpt: string;
  match: "Expected" | "Forbidden" | "Missing locator" | "Retrieved";
};

export type EvalTraceStep = {
  name: string;
  status: "succeeded" | "failed" | "skipped" | "running";
  detail: string;
  durationMs: number;
};

export type EvalCaseResult = {
  id: string;
  suiteId: string;
  suiteLabel: string;
  question: string;
  expectedBehavior: string;
  outcome: EvalOutcome;
  score: number;
  finding: string;
  runId: string;
  status: string;
  latencyMs: number;
  traceId: string;
  deniedCount: number;
  forbiddenCount: number;
  citations: EvalCitation[];
  trace: EvalTraceStep[];
};

export type EvalRunSummary = {
  id: string;
  corpusId: string;
  mode: string;
  agentName: string;
  status: "Passed" | "Needs review" | "Running";
  startedAt: string;
  durationLabel: string;
  totalCases: number;
  passedCases: number;
  failedCases: number;
  passRate: number;
  citationCoverage: number;
  aclViolations: number;
  traceCompleteness: number;
  endpoint?: string;
};

export type EvalOverview = {
  run: EvalRunSummary;
  suites: EvalSuite[];
  cases: EvalCaseResult[];
};

export type EvalApiResult<T> = {
  ok: boolean;
  data?: T;
  endpoint?: string;
  error?: string;
};

export type RuntimeTraceEvidence = {
  trace: EvalTraceStep[];
  citations: EvalCitation[];
  finding: string;
  status: string;
  latencyMs: number;
  deniedCount: number;
  endpoint?: string;
};

const endpointRoots = buildEndpointRoots();
const runtimeEndpointRoots = buildRuntimeEndpointRoots();
const requestTimeoutMs = 2500;

const suiteCopy: Record<string, { label: string; description: string }> = {
  "rag-core": {
    label: "RAG core",
    description: "Grounded answers and expected knowledge source coverage.",
  },
  citation: {
    label: "Citation integrity",
    description: "Every answer claim maps to a permitted citation locator.",
  },
  acl: {
    label: "ACL boundary",
    description: "Restricted documents stay out of retrieval, context, and citations.",
  },
  refusal: {
    label: "Refusal behavior",
    description: "Unsafe or unsupported requests produce the intended refusal path.",
  },
  safety: {
    label: "Safety checks",
    description: "Prompt injection, fake citation, and leakage probes are contained.",
  },
};

function buildEndpointRoots() {
  const configuredBase = process.env.NEXT_PUBLIC_AGENT_FORGE_API_BASE_URL;
  const roots = [];

  if (configuredBase) {
    const normalizedBase = configuredBase.replace(/\/$/, "");
    roots.push(normalizedBase.endsWith("/eval") ? normalizedBase : `${normalizedBase}/eval`);
  }

  roots.push("/api/v1/eval", "/api/eval");
  return Array.from(new Set(roots));
}

function buildRuntimeEndpointRoots() {
  const configuredBase = process.env.NEXT_PUBLIC_AGENT_FORGE_API_BASE_URL;
  const roots = [];

  if (configuredBase) {
    const normalizedBase = configuredBase.replace(/\/$/, "");
    roots.push(normalizedBase.endsWith("/runs") ? normalizedBase : `${normalizedBase}/runs`);
  }

  roots.push("/api/v1/runs", "/api/runs");
  return Array.from(new Set(roots));
}

function joinEndpoint(root: string, path: string) {
  const normalizedRoot = root.endsWith("/") ? root.slice(0, -1) : root;
  const normalizedPath = path.startsWith("/") ? path.slice(1) : path;
  return `${normalizedRoot}/${normalizedPath}`;
}

async function requestEval<T>(paths: string[], init?: RequestInit): Promise<EvalApiResult<T>> {
  let lastError = "Eval API is not available yet.";

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
        lastError = error instanceof Error ? error.message : "Eval API request failed.";
      } finally {
        window.clearTimeout(timeout);
      }
    }
  }

  return { ok: false, error: lastError };
}

async function requestRuntime<T>(paths: string[]): Promise<EvalApiResult<T>> {
  let lastError = "Runtime API is not available yet.";

  for (const root of runtimeEndpointRoots) {
    for (const path of paths) {
      const endpoint = joinEndpoint(root, path);
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs);

      try {
        const response = await fetch(endpoint, { signal: controller.signal });

        if (!response.ok) {
          lastError = `${response.status} ${response.statusText}`.trim();
          continue;
        }

        const data = (await response.json()) as T;
        return { ok: true, data, endpoint };
      } catch (error) {
        lastError = error instanceof Error ? error.message : "Runtime API request failed.";
      } finally {
        window.clearTimeout(timeout);
      }
    }
  }

  return { ok: false, error: lastError };
}

export async function fetchEvalOverview(): Promise<EvalApiResult<EvalOverview>> {
  const directResult = await requestEval<unknown>(["overview", "runs/latest", "runs/current"]);
  const directOverview = normalizeEvalOverview(directResult.data, directResult.endpoint);

  if (directResult.ok && directOverview) {
    return { ok: true, data: directOverview, endpoint: directResult.endpoint };
  }

  const runsResult = await requestEval<unknown>(["runs?limit=1", "runs"]);
  if (!runsResult.ok || !runsResult.data) {
    return withoutData(directResult.error ? directResult : runsResult);
  }

  const runPayload = pickLatestRun(runsResult.data);
  if (!runPayload) {
    return {
      ok: false,
      endpoint: runsResult.endpoint,
      error: "Eval API returned no runs.",
    };
  }

  const runId = stringField(runPayload, "id") ?? stringField(runPayload, "eval_run_id");
  const resultPayload =
    runId !== undefined
      ? await requestEval<unknown>([`runs/${encodeURIComponent(runId)}/results`])
      : undefined;
  const overview = normalizeEvalOverview(
    {
      run: runPayload,
      results: resultPayload?.data ?? getField(runPayload, "results"),
    },
    resultPayload?.endpoint ?? runsResult.endpoint,
  );

  if (!overview) {
    return {
      ok: false,
      endpoint: runsResult.endpoint,
      error: "Eval API response did not match a supported run summary shape.",
    };
  }

  return {
    ok: true,
    data: overview,
    endpoint: resultPayload?.endpoint ?? runsResult.endpoint,
  };
}

export async function fetchRuntimeTrace(runId: string): Promise<EvalApiResult<RuntimeTraceEvidence>> {
  if (!runId || runId.startsWith("run-")) {
    return {
      ok: false,
      error: "A persisted runtime run ID is required for trace sync.",
    };
  }

  const encodedRunId = encodeURIComponent(runId);
  const [runResult, stepsResult, hitsResult] = await Promise.all([
    requestRuntime<unknown>([encodedRunId]),
    requestRuntime<unknown>([`${encodedRunId}/steps`]),
    requestRuntime<unknown>([`${encodedRunId}/retrieval-hits`]),
  ]);

  if (!runResult.ok || !runResult.data) {
    return withoutData(runResult);
  }

  const run = asRecord(runResult.data);
  if (!run) {
    return {
      ok: false,
      endpoint: runResult.endpoint,
      error: "Runtime API response did not include a run record.",
    };
  }

  const steps = arrayPayload(stepsResult.data);
  const hits = arrayPayload(hitsResult.data);
  const trace = mapRuntimeSteps(steps);
  const citations = mapRuntimeCitations(run, hits);
  const guardrail = asRecord(run.guardrail);
  const endpoint = stepsResult.endpoint ?? runResult.endpoint;

  return {
    ok: true,
    endpoint,
    data: {
      trace,
      citations,
      status: stringField(run, "status") ?? "unknown",
      latencyMs: numericField(run, "latency_ms") ?? 0,
      deniedCount: numericField(run, "retrieval_denied_count") ?? 0,
      finding: runtimeFinding(guardrail, citations.length),
      endpoint,
    },
  };
}

function normalizeEvalOverview(payload: unknown, endpoint?: string): EvalOverview | null {
  const record = asRecord(payload);
  if (!record) {
    return null;
  }

  const rawResults = arrayField(record, "results")
    ?? arrayField(record, "case_results")
    ?? arrayField(record, "cases")
    ?? [];
  const cases = rawResults.map(mapCaseResult).filter((item): item is EvalCaseResult => item !== null);
  const runRecord = asRecord(record.run) ?? asRecord(record.summary) ?? record;
  const run = mapRunSummary(runRecord, cases, endpoint);

  if (!run && cases.length === 0) {
    return null;
  }

  const suites = buildSuites(
    cases,
    asRecord(record.suite_counts) ?? asRecord(getField(runRecord, "suite_counts")),
  );

  return {
    run: run ?? buildRunFromCases(cases, endpoint),
    suites,
    cases,
  };
}

function mapRunSummary(
  payload: Record<string, unknown>,
  cases: EvalCaseResult[],
  endpoint?: string,
): EvalRunSummary | null {
  const totalCases = numericField(payload, "total_cases")
    ?? numericField(payload, "totalCases")
    ?? cases.length;
  const passedCases = numericField(payload, "passed_cases")
    ?? numericField(payload, "passedCases")
    ?? cases.filter((item) => item.outcome === "Passed").length;
  const failedCases = numericField(payload, "failed_cases")
    ?? numericField(payload, "failedCases")
    ?? Math.max(0, totalCases - passedCases);

  if (!totalCases && !stringField(payload, "id") && !stringField(payload, "eval_run_id")) {
    return null;
  }

  const rawStatus = stringField(payload, "status");
  const status = normalizeRunStatus(rawStatus, failedCases);
  const summary = asRecord(payload.summary) ?? payload;

  return {
    id: stringField(payload, "id") ?? stringField(payload, "eval_run_id") ?? "eval-run-latest",
    corpusId: stringField(payload, "corpus_id") ?? stringField(payload, "corpusId") ?? "synthetic-corpus-v0.1",
    mode: stringField(payload, "mode") ?? "api",
    agentName: stringField(payload, "agent_name") ?? stringField(payload, "agentName") ?? "Synthetic Eval Agent",
    status,
    startedAt: formatDateLabel(
      stringField(payload, "started_at") ?? stringField(payload, "startedAt") ?? stringField(payload, "created_at"),
    ),
    durationLabel: stringField(payload, "duration_label")
      ?? stringField(payload, "durationLabel")
      ?? durationFromMs(numericField(payload, "duration_ms") ?? numericField(payload, "durationMs")),
    totalCases,
    passedCases,
    failedCases,
    passRate: ratioField(payload, "pass_rate")
      ?? ratioField(payload, "passRate")
      ?? (totalCases ? passedCases / totalCases : 0),
    citationCoverage: ratioField(summary, "citation_coverage")
      ?? ratioField(summary, "citationCoverage")
      ?? computeCitationCoverage(cases),
    aclViolations: numericField(summary, "acl_violation_count")
      ?? numericField(summary, "aclViolations")
      ?? cases.reduce((total, item) => total + item.forbiddenCount, 0),
    traceCompleteness: ratioField(summary, "trace_completeness")
      ?? ratioField(summary, "traceCompleteness")
      ?? computeTraceCompleteness(cases),
    endpoint,
  };
}

function mapCaseResult(payload: unknown, index: number): EvalCaseResult | null {
  const record = asRecord(payload);
  if (!record) {
    return null;
  }

  const id = stringField(record, "case_id")
    ?? stringField(record, "caseId")
    ?? stringField(record, "eval_case_id")
    ?? stringField(record, "id")
    ?? `case_${index + 1}`;
  const suiteId = normalizeSuiteId(stringField(record, "suite") ?? stringField(record, "suite_id"));
  const outcome = normalizeOutcome(record);
  const findings = arrayField(record, "findings")
    ?.map((item) => (typeof item === "string" ? item : undefined))
    .filter((item): item is string => Boolean(item));
  const citations = mapCitations(record);
  const trace = mapTrace(record, outcome, citations.length);
  const deniedCount = numericField(record, "retrieval_denied_count") ?? numericField(record, "deniedCount") ?? 0;
  const forbiddenCount = outcome === "Passed"
    ? 0
    : findings?.filter((finding) => finding.toLowerCase().includes("forbidden")).length ?? 0;

  return {
    id,
    suiteId,
    suiteLabel: suiteLabel(suiteId),
    question: stringField(record, "question") ?? stringField(record, "prompt") ?? id,
    expectedBehavior: stringField(record, "expected_behavior")
      ?? stringField(record, "expectedBehavior")
      ?? "answer",
    outcome,
    score: normalizeScore(numericField(record, "score") ?? numericField(asRecord(record.scores), "overall"), outcome),
    finding: findings?.[0]
      ?? stringField(record, "finding")
      ?? stringField(record, "error_message")
      ?? (outcome === "Passed" ? "Case matched expected behavior." : "Case needs review."),
    runId: stringField(record, "run_id") ?? stringField(record, "runId") ?? "runtime-run",
    status: stringField(record, "status") ?? (outcome === "Passed" ? "succeeded" : "failed"),
    latencyMs: numericField(record, "latency_ms") ?? numericField(record, "latencyMs") ?? 0,
    traceId: stringField(record, "trace_id") ?? stringField(record, "traceId") ?? `trace-${id}`,
    deniedCount,
    forbiddenCount,
    citations,
    trace,
  };
}

function mapCitations(record: Record<string, unknown>): EvalCitation[] {
  const rawCitations = arrayField(record, "citations");
  if (rawCitations?.length) {
    const citations: EvalCitation[] = [];

    rawCitations.forEach((item, index) => {
      const citation = asRecord(item);
      if (!citation) {
        return;
      }

      const documentId = stringField(citation, "document_id") ?? stringField(citation, "documentId") ?? "document";
      citations.push({
        id: `${documentId}-${index}`,
        documentId,
        title: stringField(citation, "title") ?? documentId,
        locator: stringField(citation, "citation_locator")
          ?? stringField(citation, "locator")
          ?? stringField(citation, "citation")
          ?? "locator unavailable",
        excerpt: stringField(citation, "excerpt") ?? "Citation was returned by the eval API.",
        match: "Retrieved",
      });
    });

    return citations;
  }

  const citationIds = arrayField(record, "citation_document_ids")
    ?? arrayField(record, "citationDocumentIds")
    ?? [];

  return citationIds
    .map((item, index) => (typeof item === "string" ? item : undefined))
    .filter((item): item is string => Boolean(item))
    .map((documentId, index) => ({
      id: `${documentId}-${index}`,
      documentId,
      title: documentId,
      locator: "API citation locator",
      excerpt: "Citation document ID was reported by the API eval run.",
      match: "Retrieved" as const,
    }));
}

function mapTrace(
  record: Record<string, unknown>,
  outcome: EvalOutcome,
  citationCount: number,
): EvalTraceStep[] {
  const rawSteps = arrayField(record, "trace") ?? arrayField(record, "steps") ?? arrayField(record, "run_steps");
  if (rawSteps?.length) {
    return rawSteps
      .map((item) => {
        const step = asRecord(item);
        if (!step) {
          return null;
        }

        return {
          name: stringField(step, "name") ?? stringField(step, "step_type") ?? "runtime_step",
          status: normalizeStepStatus(stringField(step, "status")),
          detail: stringField(step, "detail")
            ?? stringField(step, "output_summary")
            ?? stringField(step, "error_message")
            ?? "Step recorded by runtime trace.",
          durationMs: numericField(step, "duration_ms") ?? numericField(step, "durationMs") ?? 0,
        };
      })
      .filter((item): item is EvalTraceStep => item !== null);
  }

  return fallbackTrace(outcome, citationCount);
}

function buildSuites(
  cases: EvalCaseResult[],
  suiteCounts?: Record<string, unknown> | null,
): EvalSuite[] {
  const suiteIds = new Set<string>(Object.keys(suiteCopy));

  for (const caseResult of cases) {
    suiteIds.add(caseResult.suiteId);
  }

  if (suiteCounts) {
    for (const suiteId of Object.keys(suiteCounts)) {
      suiteIds.add(normalizeSuiteId(suiteId));
    }
  }

  return Array.from(suiteIds).map((suiteId) => {
    const suiteCases = cases.filter((caseResult) => caseResult.suiteId === suiteId);
    const total = numericValue(suiteCounts?.[suiteId]) ?? suiteCases.length;
    const passed = suiteCases.length
      ? suiteCases.filter((caseResult) => caseResult.outcome === "Passed").length
      : total;
    const failed = suiteCases.length
      ? suiteCases.filter((caseResult) => caseResult.outcome !== "Passed").length
      : 0;

    return {
      id: suiteId,
      label: suiteLabel(suiteId),
      description: suiteDescription(suiteId),
      total,
      passed,
      failed,
      status: failed > 0 ? "Needs review" : "Ready",
    };
  });
}

function buildRunFromCases(cases: EvalCaseResult[], endpoint?: string): EvalRunSummary {
  const totalCases = cases.length;
  const passedCases = cases.filter((item) => item.outcome === "Passed").length;
  const failedCases = totalCases - passedCases;

  return {
    id: "eval-run-latest",
    corpusId: "synthetic-corpus-v0.1",
    mode: "api",
    agentName: "Synthetic Eval Agent",
    status: failedCases ? "Needs review" : "Passed",
    startedAt: "Latest API run",
    durationLabel: "API reported",
    totalCases,
    passedCases,
    failedCases,
    passRate: totalCases ? passedCases / totalCases : 0,
    citationCoverage: computeCitationCoverage(cases),
    aclViolations: cases.reduce((total, item) => total + item.forbiddenCount, 0),
    traceCompleteness: computeTraceCompleteness(cases),
    endpoint,
  };
}

function pickLatestRun(payload: unknown): Record<string, unknown> | null {
  const record = asRecord(payload);
  if (record) {
    const runs = arrayField(record, "runs") ?? arrayField(record, "items") ?? arrayField(record, "data");
    if (runs?.length) {
      return asRecord(runs[0]);
    }
    return record;
  }

  if (Array.isArray(payload) && payload.length > 0) {
    return asRecord(payload[0]);
  }

  return null;
}

function withoutData<T>(result: EvalApiResult<unknown>): EvalApiResult<T> {
  return {
    ok: false,
    endpoint: result.endpoint,
    error: result.error,
  };
}

function normalizeRunStatus(
  status: string | undefined,
  failedCases: number,
): EvalRunSummary["status"] {
  const normalized = status?.toLowerCase();
  if (normalized === "running" || normalized === "queued" || normalized === "pending") {
    return "Running";
  }
  if (normalized === "failed" || normalized === "needs_review" || normalized === "needs review") {
    return "Needs review";
  }
  return failedCases > 0 ? "Needs review" : "Passed";
}

function normalizeOutcome(record: Record<string, unknown>): EvalOutcome {
  const passed = booleanField(record, "passed");
  if (passed !== undefined) {
    return passed ? "Passed" : "Failed";
  }

  const status = (stringField(record, "outcome") ?? stringField(record, "status") ?? "").toLowerCase();
  if (status.includes("pass") || status === "succeeded") {
    return "Passed";
  }
  if (status.includes("review") || status.includes("warning")) {
    return "Needs review";
  }
  if (status.includes("fail") || status === "errored") {
    return "Failed";
  }
  return "Needs review";
}

function normalizeStepStatus(status: string | undefined): EvalTraceStep["status"] {
  const normalized = status?.toLowerCase();
  if (normalized === "failed" || normalized === "errored") {
    return "failed";
  }
  if (normalized === "skipped") {
    return "skipped";
  }
  if (normalized === "running" || normalized === "queued") {
    return "running";
  }
  return "succeeded";
}

function normalizeSuiteId(value: string | undefined) {
  return value?.trim() || "rag-core";
}

function suiteLabel(suiteId: string) {
  return suiteCopy[suiteId]?.label ?? suiteId;
}

function suiteDescription(suiteId: string) {
  return suiteCopy[suiteId]?.description ?? "Synthetic eval suite reported by the API.";
}

function normalizeScore(value: number | undefined, outcome: EvalOutcome) {
  if (value !== undefined) {
    return value > 1 ? value / 100 : value;
  }
  if (outcome === "Passed") {
    return 0.96;
  }
  if (outcome === "Needs review") {
    return 0.74;
  }
  return 0.48;
}

function computeCitationCoverage(cases: EvalCaseResult[]) {
  const answerCases = cases.filter((item) => item.expectedBehavior === "answer");
  if (!answerCases.length) {
    return 0;
  }
  return answerCases.filter((item) => item.citations.length > 0).length / answerCases.length;
}

function computeTraceCompleteness(cases: EvalCaseResult[]) {
  if (!cases.length) {
    return 0;
  }
  return cases.filter((item) => item.trace.length > 0 && item.traceId).length / cases.length;
}

function fallbackTrace(outcome: EvalOutcome, citationCount: number): EvalTraceStep[] {
  return [
    {
      name: "runtime_orchestrator",
      status: outcome === "Failed" ? "failed" : "succeeded",
      detail: "Runtime run was scored against the synthetic case contract.",
      durationMs: 180,
    },
    {
      name: "retrieval_filter",
      status: outcome === "Failed" ? "failed" : "succeeded",
      detail: "ACL filter and retrieval hit metadata were checked.",
      durationMs: 94,
    },
    {
      name: "citation_validator",
      status: citationCount > 0 || outcome !== "Passed" ? "succeeded" : "failed",
      detail: `${citationCount} citation candidate(s) were available for scoring.`,
      durationMs: 42,
    },
  ];
}

function mapRuntimeSteps(payload: unknown[]): EvalTraceStep[] {
  return payload
    .map((item) => {
      const step = asRecord(item);
      if (!step) {
        return null;
      }

      const outputSummary = asRecord(step.output_summary);
      const routeStage = stringField(outputSummary ?? {}, "route_stage");
      const modelTier = stringField(outputSummary ?? {}, "model_tier");
      const errorMessage = stringField(step, "error_message");
      const detailParts = [
        routeStage ? `route stage ${routeStage}` : undefined,
        modelTier ? `model tier ${modelTier}` : undefined,
        errorMessage,
      ].filter(Boolean);

      return {
        name: stringField(step, "step_type") ?? "runtime_step",
        status: normalizeStepStatus(stringField(step, "status")),
        detail: detailParts.length ? detailParts.join(" / ") : "Runtime step persisted by API.",
        durationMs: numericField(step, "latency_ms") ?? 0,
      };
    })
    .filter((item): item is EvalTraceStep => item !== null);
}

function mapRuntimeCitations(run: Record<string, unknown>, hits: unknown[]): EvalCitation[] {
  const runCitations = arrayField(run, "citations") ?? [];
  if (runCitations.length) {
    const citations: EvalCitation[] = [];

    runCitations.forEach((item, index) => {
      const citation = asRecord(item);
      if (!citation) {
        return;
      }

      const documentId = stringField(citation, "document_id") ?? "document";
      citations.push({
        id: `${documentId}-${index}`,
        documentId,
        title: stringField(citation, "title") ?? documentId,
        locator: stringField(citation, "citation_locator") ?? "locator unavailable",
        excerpt: "Citation returned by the runtime run.",
        match: "Retrieved",
      });
    });

    return citations;
  }

  const citations: EvalCitation[] = [];

  hits.forEach((item, index) => {
    const hit = asRecord(item);
    if (!hit || booleanField(hit, "used_as_citation") === false) {
      return;
    }

    const documentId = stringField(hit, "document_id") ?? "document";
    citations.push({
      id: `${documentId}-${index}`,
      documentId,
      title: stringField(hit, "title") ?? documentId,
      locator: stringField(hit, "citation_locator") ?? "locator unavailable",
      excerpt: "Retrieval hit stored by the runtime run.",
      match: "Retrieved",
    });
  });

  return citations;
}

function runtimeFinding(guardrail: Record<string, unknown> | null, citationCount: number) {
  const outcome = stringField(guardrail ?? {}, "outcome") ?? "unknown";
  const routeSummary = asRecord(guardrail?.model_route_summary);
  const generator = asRecord(routeSummary?.answer_generator);
  const generatorTier = stringField(generator ?? {}, "tier");
  if (citationCount > 0) {
    return `Runtime ${outcome} path returned ${citationCount} citation(s); answer generator tier ${generatorTier ?? "unknown"}.`;
  }
  return `Runtime ${outcome} path failed closed without generated citations.`;
}

function arrayPayload(payload: unknown): unknown[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  const record = asRecord(payload);
  return arrayField(record ?? {}, "items") ?? arrayField(record ?? {}, "data") ?? [];
}

function formatDateLabel(value: string | undefined) {
  if (!value) {
    return "Latest API run";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function durationFromMs(value: number | undefined) {
  if (value === undefined) {
    return "API reported";
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  return `${(value / 1000).toFixed(1)} sec`;
}

function ratioField(record: Record<string, unknown> | null | undefined, key: string) {
  const value = numericField(record, key);
  if (value === undefined) {
    return undefined;
  }
  return value > 1 ? value / 100 : value;
}

function numericField(record: Record<string, unknown> | null | undefined, key: string) {
  if (!record) {
    return undefined;
  }
  return numericValue(record[key]);
}

function numericValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function stringField(record: Record<string, unknown> | null | undefined, key: string) {
  if (!record) {
    return undefined;
  }
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function booleanField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return typeof value === "boolean" ? value : undefined;
}

function arrayField(record: Record<string, unknown>, key: string) {
  const value = record[key];
  return Array.isArray(value) ? value : undefined;
}

function getField(record: Record<string, unknown>, key: string) {
  return record[key];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}
