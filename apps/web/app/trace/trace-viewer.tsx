"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { EvalCitation, EvalRetrievalHit, EvalTraceStep, RuntimeTraceEvidence } from "../eval/api";
import { fetchRuntimeTrace } from "../eval/api";

type NoticeTone = "" | "neutral" | "warn" | "danger";

type Notice = {
  text: string;
  tone: NoticeTone;
};

export function TraceViewer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const runIdParam = searchParams.get("run_id") ?? "";
  const [runId, setRunId] = useState(runIdParam);
  const [traceEvidence, setTraceEvidence] = useState<RuntimeTraceEvidence | null>(null);
  const [notice, setNotice] = useState<Notice>({
    text: runIdParam ? "Loading runtime trace evidence." : "Enter a persisted runtime run ID.",
    tone: runIdParam ? "neutral" : "warn",
  });
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setRunId(runIdParam);

    if (!runIdParam) {
      setTraceEvidence(null);
      setNotice({ text: "Enter a persisted runtime run ID.", tone: "warn" });
      return;
    }

    startTransition(() => {
      void loadTrace(runIdParam);
    });
  }, [runIdParam]);

  async function loadTrace(nextRunId: string) {
    setNotice({ text: `Loading runtime trace for ${nextRunId}.`, tone: "neutral" });
    const result = await fetchRuntimeTrace(nextRunId);

    if (result.ok && result.data) {
      setTraceEvidence(result.data);
      setNotice({
        text: `Loaded runtime trace from ${result.endpoint ?? "runs API"}.`,
        tone: "",
      });
      return;
    }

    setTraceEvidence(null);
    setNotice({
      text: `Runtime trace unavailable for ${nextRunId} (${result.error ?? "request failed"}).`,
      tone: "danger",
    });
  }

  function submitRunId(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextRunId = runId.trim();

    if (!nextRunId) {
      setTraceEvidence(null);
      setNotice({ text: "Enter a persisted runtime run ID.", tone: "warn" });
      router.push("/trace");
      return;
    }

    router.push(`/trace?run_id=${encodeURIComponent(nextRunId)}`);
  }

  return (
    <section className="page traceViewerPage">
      <div className="header">
        <div>
          <p className="eyebrow">Runtime evidence</p>
          <h1>Trace Viewer</h1>
          <p>
            Open a persisted runtime run, inspect ordered steps, compare retrieval hits,
            and verify citations from a shareable run URL.
          </p>
        </div>
        <form className="traceSearchForm" onSubmit={submitRunId}>
          <label>
            Run ID
            <input
              aria-label="Run ID"
              placeholder="runtime-run-id"
              value={runId}
              onChange={(event) => setRunId(event.target.value)}
            />
          </label>
          <button className="button" disabled={isPending} type="submit">
            {isPending ? "Loading" : "Load trace"}
          </button>
        </form>
      </div>

      <section className="panel evalNotice" aria-live="polite">
        <span className={`badge ${notice.tone}`}>Trace API</span>
        <p>{notice.text}</p>
      </section>

      {traceEvidence ? (
        <>
          <section className="statGrid traceStatusGrid">
            <div className="stat">
              <strong>{traceEvidence.status}</strong>
              <h3>Status</h3>
              <p>{runIdParam}</p>
            </div>
            <div className="stat">
              <strong>{formatLatency(traceEvidence.latencyMs)}</strong>
              <h3>Latency</h3>
              <p>{traceEvidence.trace.length} step(s)</p>
            </div>
            <div className="stat">
              <strong>{traceEvidence.deniedCount}</strong>
              <h3>Denied retrieval</h3>
              <p>{traceEvidence.retrievalHits.length} retrieval hit(s)</p>
            </div>
          </section>

          <section className="panel tracePanel">
            <div className="panelHeader">
              <div>
                <h2>Runtime path</h2>
                <p>{traceEvidence.endpoint ?? "runs API"} evidence.</p>
              </div>
              <span className={`badge ${runTone(traceEvidence.status)}`}>{traceEvidence.status}</span>
            </div>

            <dl className="detailGrid">
              <div>
                <dt>Run</dt>
                <dd>{runIdParam}</dd>
              </div>
              <div>
                <dt>Endpoint</dt>
                <dd>{traceEvidence.endpoint ?? "runs API"}</dd>
              </div>
              <div>
                <dt>Latency</dt>
                <dd>{formatLatency(traceEvidence.latencyMs)}</dd>
              </div>
              <div>
                <dt>Denied retrieval</dt>
                <dd>{traceEvidence.deniedCount}</dd>
              </div>
            </dl>

            <div className="findingBox">
              <strong>Finding</strong>
              <p>{traceEvidence.finding}</p>
            </div>

            <TraceStepList steps={traceEvidence.trace} />
            <RetrievalComparison hits={traceEvidence.retrievalHits} />
            <CitationList citations={traceEvidence.citations} />
          </section>
        </>
      ) : (
        <section className="panel">
          <p className="emptyState">No runtime trace is loaded.</p>
        </section>
      )}
    </section>
  );
}

function TraceStepList({ steps }: { steps: EvalTraceStep[] }) {
  if (!steps.length) {
    return <p className="emptyState">No runtime steps returned for this run.</p>;
  }

  return (
    <div className="traceSteps">
      {steps.map((step, index) => (
        <article className="traceStep" key={`${step.name}-${index}`}>
          <span className="stepIndex">{index + 1}</span>
          <div>
            <strong>{step.name}</strong>
            <p>{step.detail}</p>
            {hasStepPayload(step) ? (
              <details className="tracePayload">
                <summary>Payload</summary>
                <div className="payloadGrid">
                  <div>
                    <span>Input</span>
                    <pre>{formatPayload(step.inputSummary)}</pre>
                  </div>
                  <div>
                    <span>Output</span>
                    <pre>{formatPayload(step.outputSummary)}</pre>
                  </div>
                </div>
                {step.errorCode || step.errorMessage ? (
                  <p>
                    {step.errorCode ?? "error"}: {step.errorMessage ?? "No message"}
                  </p>
                ) : null}
              </details>
            ) : null}
          </div>
          <span className={`badge ${stepTone(step.status)}`}>{step.status}</span>
        </article>
      ))}
    </div>
  );
}

function RetrievalComparison({ hits }: { hits: EvalRetrievalHit[] }) {
  return (
    <div className="citationSection">
      <h3>Retrieval comparison</h3>
      {hits.length ? (
        <div className="retrievalHitGrid">
          {hits.map((hit) => (
            <article className="citationRow" key={hit.id}>
              <div>
                <strong>{hit.title}</strong>
                <small>
                  rank {hit.rank} / score {formatScore(hit.score)} / {hit.documentId}
                </small>
              </div>
              <p>{hit.locator}</p>
              <span className={`badge ${hit.usedAsCitation ? "" : "neutral"}`}>
                {hit.usedAsCitation ? "Used as citation" : "Context only"}
              </span>
              <small>
                ACL {hit.aclSubjects.length ? hit.aclSubjects.join(", ") : "snapshot unavailable"}
              </small>
            </article>
          ))}
        </div>
      ) : (
        <p className="emptyState">No retrieval hits returned for this run.</p>
      )}
    </div>
  );
}

function CitationList({ citations }: { citations: EvalCitation[] }) {
  return (
    <div className="citationSection">
      <h3>Citation detail</h3>
      {citations.length ? (
        <div className="citationList">
          {citations.map((citation) => (
            <article className="citationRow" key={citation.id}>
              <div>
                <strong>{citation.title}</strong>
                <small>
                  {citation.documentId} - {citation.locator}
                </small>
              </div>
              <p>{citation.excerpt}</p>
              <span
                className={`badge ${
                  citation.match === "Expected"
                    ? ""
                    : citation.match === "Forbidden"
                      ? "danger"
                      : "warn"
                }`}
              >
                {citation.match}
              </span>
            </article>
          ))}
        </div>
      ) : (
        <p className="emptyState">No citations returned for this run.</p>
      )}
    </div>
  );
}

function hasStepPayload(step: EvalTraceStep) {
  return Boolean(
    Object.keys(step.inputSummary ?? {}).length
      || Object.keys(step.outputSummary ?? {}).length
      || step.errorCode
      || step.errorMessage,
  );
}

function stepTone(status: EvalTraceStep["status"]) {
  if (status === "succeeded") {
    return "";
  }
  if (status === "running" || status === "skipped") {
    return "neutral";
  }
  return "danger";
}

function runTone(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "succeeded" || normalized === "passed") {
    return "";
  }
  if (normalized === "running" || normalized === "queued" || normalized === "pending") {
    return "neutral";
  }
  return "warn";
}

function formatPayload(payload: Record<string, unknown> | undefined) {
  if (!payload || Object.keys(payload).length === 0) {
    return "none";
  }
  return JSON.stringify(payload, null, 2);
}

function formatLatency(value: number) {
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  return `${(value / 1000).toFixed(1)} sec`;
}

function formatScore(value: number) {
  return value.toFixed(2);
}
