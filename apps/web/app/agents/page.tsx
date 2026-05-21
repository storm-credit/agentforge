"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState, useTransition } from "react";
import { AgentRunResult, submitAgentRun } from "./api";

const agents = [
  {
    id: "policy-rag",
    name: "Policy RAG Assistant",
    owner: "Risk Operations",
    version: "v1",
    status: "Pilot published",
    gate: "83%",
    knowledge: "Policy library",
    modelRoute: "standard",
    next: "Trace Viewer link",
    tone: "warn",
    canTest: true,
  },
  {
    id: "it-procedure",
    name: "IT Procedure Helper",
    owner: "IT Operations",
    version: "draft",
    status: "Draft",
    gate: "42%",
    knowledge: "Operating procedures",
    modelRoute: "smoke",
    next: "Index source docs",
    tone: "neutral",
    canTest: false,
  },
  {
    id: "security-policy",
    name: "Security Policy Assistant",
    owner: "Security",
    version: "v1",
    status: "Validated",
    gate: "71%",
    knowledge: "Security policy docs",
    modelRoute: "release-gate",
    next: "Run ACL suite",
    tone: "warn",
    canTest: true,
  },
];

const modelStages = [
  { stage: "Pre-check", tier: "fast-small", budget: "400 tokens" },
  { stage: "Planner", tier: "fast-small", budget: "800 tokens" },
  { stage: "Retriever", tier: "deterministic", budget: "ACL first" },
  { stage: "Answer generator", tier: "standard-rag", budget: "2400 tokens" },
  { stage: "Critic", tier: "fast-small -> deep-review", budget: "1 escalation" },
];

const gates = [
  { label: "Agent card", state: "Ready" },
  { label: "Knowledge source", state: "Ready" },
  { label: "Eval report", state: "Ready" },
  { label: "Trace review", state: "Needs review" },
];

export default function AgentsPage() {
  const [selectedAgentName, setSelectedAgentName] = useState(agents[0].name);
  const [question, setQuestion] = useState(
    "What policy evidence should this agent cite before a pilot answer?",
  );
  const [runResult, setRunResult] = useState<AgentRunResult | null>(null);
  const [chatError, setChatError] = useState("");
  const [isPending, startTransition] = useTransition();
  const selectedAgent = agents.find((agent) => agent.name === selectedAgentName) ?? agents[0];
  const canTestSelectedAgent = selectedAgent.canTest;
  const traceHref = runResult ? `/trace?run_id=${encodeURIComponent(runResult.runId)}` : "/trace";
  const citationSummary = useMemo(() => {
    if (!runResult) {
      return "No test run yet";
    }

    return runResult.citations.length > 0
      ? `${runResult.citations.length} citation(s)`
      : "No citations";
  }, [runResult]);

  function handleAgentSelect(agentName: string) {
    setSelectedAgentName(agentName);
    setRunResult(null);
    setChatError("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canTestSelectedAgent) {
      setChatError("Only published or validated agents can be tested from this draft surface.");
      return;
    }

    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setChatError("Enter a message before starting a test run.");
      return;
    }

    setChatError("");
    startTransition(async () => {
      const result = await submitAgentRun({
        agentId: selectedAgent.id,
        agentName: selectedAgent.name,
        question: trimmedQuestion,
        knowledge: selectedAgent.knowledge,
      });

      setRunResult(result);
    });
  }

  return (
    <section className="page agentsPage">
      <div className="header">
        <div>
          <p className="eyebrow">Builder</p>
          <h1>Agents</h1>
          <p>
            Govern agent versions from draft configuration through model routing, knowledge
            binding, eval gates, and trace review.
          </p>
        </div>
        <div className="buttonRow">
          <button className="button" disabled title="Agent draft API is pending" type="button">
            New draft
          </button>
          <button className="button secondary" disabled title="Validation API is pending" type="button">
            Validate
          </button>
        </div>
      </div>

      <section className="nextAction">
        <div>
          <span className="badge warn">Release blocker</span>
          <strong>{selectedAgent.next} is required before the pilot version is release-ready.</strong>
        </div>
        <span className="badge neutral">Budget: {selectedAgent.modelRoute}</span>
      </section>

      <div className="agentWorkbench">
        <section className="panel agentListPanel">
          <div className="panelHeader">
            <div>
              <h2>Agent versions</h2>
              <p>Current pilot inventory and readiness state.</p>
            </div>
          </div>
          <div className="agentRows">
            {agents.map((agent) => (
              <button
                aria-pressed={agent.name === selectedAgent.name}
                className="agentRow"
                key={agent.name}
                onClick={() => handleAgentSelect(agent.name)}
                type="button"
              >
                <div>
                  <strong>{agent.name}</strong>
                  <span>
                    {agent.owner} / {agent.version} / {agent.knowledge}
                  </span>
                </div>
                <span className={`badge ${agent.tone}`}>{agent.status}</span>
                <strong>{agent.gate}</strong>
              </button>
            ))}
          </div>
        </section>

        <aside className="panel agentDetailPanel">
          <div className="panelHeader">
            <div>
              <h2>{selectedAgent.name}</h2>
              <p>
                {selectedAgent.owner} owns this {selectedAgent.status.toLowerCase()} version.
              </p>
            </div>
            <span className="badge warn">Gate {selectedAgent.gate}</span>
          </div>

          <dl className="detailGrid">
            <div>
              <dt>Version</dt>
              <dd>{selectedAgent.version}</dd>
            </div>
            <div>
              <dt>Knowledge</dt>
              <dd>{selectedAgent.knowledge}</dd>
            </div>
            <div>
              <dt>Model route</dt>
              <dd>{selectedAgent.modelRoute}</dd>
            </div>
            <div>
              <dt>Next action</dt>
              <dd>{selectedAgent.next}</dd>
            </div>
          </dl>

          <div className="gateStack">
            {gates.map((gate) => (
              <div className="gateRow" key={gate.label}>
                <span>{gate.label}</span>
                <span className={`badge ${gate.state === "Needs review" ? "warn" : ""}`}>
                  {gate.state}
                </span>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <section className="panel testChatPanel" aria-labelledby="test-chat-heading">
        <div className="panelHeader">
          <div>
            <h2 id="test-chat-heading">Test chat</h2>
            <p>Send a local draft run against the selected published or validated agent.</p>
          </div>
          <span className={`badge ${canTestSelectedAgent ? "neutral" : "warn"}`}>
            {canTestSelectedAgent ? "Ready to test" : "Draft locked"}
          </span>
        </div>

        <div className="testChatGrid">
          <form className="testChatForm" onSubmit={handleSubmit}>
            <label>
              Message
              <textarea
                disabled={!canTestSelectedAgent || isPending}
                onChange={(event) => setQuestion(event.target.value)}
                value={question}
              />
            </label>
            <div className="buttonRow">
              <button className="button" disabled={!canTestSelectedAgent || isPending} type="submit">
                {isPending ? "Running..." : "Send test"}
              </button>
              <button
                className="button secondary"
                disabled={!canTestSelectedAgent || isPending}
                onClick={() => setQuestion("Ask an unsupported no context question about a private contract.")}
                type="button"
              >
                No-context probe
              </button>
            </div>
            {chatError ? <p className="formNotice danger">{chatError}</p> : null}
          </form>

          <div className="testChatResult" aria-live="polite">
            <dl className="runSummaryGrid compact">
              <div>
                <dt>Status</dt>
                <dd>{runResult?.status ?? "Idle"}</dd>
              </div>
              <div>
                <dt>Run ID</dt>
                <dd>{runResult?.runId ?? "Not started"}</dd>
              </div>
              <div>
                <dt>Guardrail</dt>
                <dd>{runResult?.guardrailStatus ?? "Pending"}</dd>
              </div>
              <div>
                <dt>Citation validation</dt>
                <dd>{runResult?.citationStatus ?? "Pending"}</dd>
              </div>
            </dl>

            <div className="answerBox">
              <strong>Answer</strong>
              <p>{runResult?.answer ?? "The next test answer will appear here."}</p>
            </div>

            <div className="citationChipList" aria-label="Citations">
              <span className="badge neutral">{citationSummary}</span>
              {runResult?.citations.map((citation) => (
                <span className="citationChip" key={`${citation.documentId}-${citation.locator}`}>
                  {citation.title} / {citation.locator}
                </span>
              ))}
            </div>

            <Link
              aria-disabled={!runResult}
              className={`button secondary traceLink ${runResult ? "" : "disabled"}`}
              href={traceHref}
            >
              Open trace
            </Link>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panelHeader">
          <div>
            <h2>Model routing profile</h2>
            <p>Stage-level budget for the selected agent version.</p>
          </div>
          <span className="badge neutral">model-routing-policy/v0.1</span>
        </div>
        <div className="modelRouteGrid">
          {modelStages.map((stage) => (
            <article className="routeStep" key={stage.stage}>
              <strong>{stage.stage}</strong>
              <span>{stage.tier}</span>
              <small>{stage.budget}</small>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}
