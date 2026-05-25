"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";
import type { AgentKnowledgeSource, AgentOption, AgentRunResult } from "./api";
import {
  createDraftAgentWithVersion,
  fetchAgentCatalog,
  fetchKnowledgeSources,
  publishAgentVersion,
  submitAgentRun,
  validateAgentVersion,
} from "./api";

const seedAgents: AgentOption[] = [
  {
    key: "seed-policy-rag",
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
    source: "seed",
    lifecycleStatus: "published",
    knowledgeSourceIds: [],
  },
  {
    key: "seed-it-procedure",
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
    source: "seed",
    lifecycleStatus: "draft",
    knowledgeSourceIds: [],
  },
  {
    key: "seed-security-policy",
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
    canTest: false,
    source: "seed",
    lifecycleStatus: "validated",
    knowledgeSourceIds: [],
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
  const [agents, setAgents] = useState(seedAgents);
  const [selectedAgentKey, setSelectedAgentKey] = useState(seedAgents[0].key);
  const [question, setQuestion] = useState(
    "What policy evidence should this agent cite before a pilot answer?",
  );
  const [runResult, setRunResult] = useState<AgentRunResult | null>(null);
  const [chatError, setChatError] = useState("");
  const [draftName, setDraftName] = useState("Policy Intake Assistant");
  const [draftPurpose, setDraftPurpose] = useState(
    "Answer internal policy intake questions with traceable citations.",
  );
  const [draftOwner, setDraftOwner] = useState("Risk Operations");
  const [draftKnowledgeSourceIds, setDraftKnowledgeSourceIds] = useState("");
  const [knowledgeSources, setKnowledgeSources] = useState<AgentKnowledgeSource[]>([]);
  const [selectedKnowledgeSourceIds, setSelectedKnowledgeSourceIds] = useState<string[]>([]);
  const [knowledgeSourceNotice, setKnowledgeSourceNotice] = useState(
    "Checking Knowledge API sources...",
  );
  const [isKnowledgeSourcePending, setIsKnowledgeSourcePending] = useState(true);
  const [lifecycleNotice, setLifecycleNotice] = useState(
    "Create a v1 draft or select an API version to advance its lifecycle.",
  );
  const [lifecycleError, setLifecycleError] = useState("");
  const [validationReason, setValidationReason] = useState("Lifecycle smoke validation");
  const [publishReason, setPublishReason] = useState("Lifecycle smoke publish");
  const [catalogNotice, setCatalogNotice] = useState("Checking Agent API catalog...");
  const [isCatalogPending, setIsCatalogPending] = useState(true);
  const [isChatPending, startChatTransition] = useTransition();
  const [isLifecyclePending, startLifecycleTransition] = useTransition();
  const selectedAgent = agents.find((agent) => agent.key === selectedAgentKey) ?? agents[0];
  const canTestSelectedAgent = selectedAgent.canTest;
  const canValidateSelectedAgent =
    selectedAgent.source === "api" &&
    Boolean(selectedAgent.agentVersionId) &&
    selectedAgent.lifecycleStatus === "draft";
  const canPublishSelectedAgent =
    selectedAgent.source === "api" &&
    Boolean(selectedAgent.agentVersionId) &&
    selectedAgent.lifecycleStatus === "validated";
  const traceHref = runResult ? `/trace?run_id=${encodeURIComponent(runResult.runId)}` : "/trace";
  const citationSummary = useMemo(() => {
    if (!runResult) {
      return "No test run yet";
    }

    return runResult.citations.length > 0
      ? `${runResult.citations.length} citation(s)`
      : "No citations";
  }, [runResult]);
  const draftKnowledgeIds = useMemo(
    () => mergeKnowledgeSourceIds(selectedKnowledgeSourceIds, draftKnowledgeSourceIds),
    [draftKnowledgeSourceIds, selectedKnowledgeSourceIds],
  );

  const upsertAgentOption = useCallback((option: AgentOption) => {
    setAgents((currentAgents) => [
      option,
      ...currentAgents.filter((agent) => agent.key !== option.key),
    ]);
    setSelectedAgentKey(option.key);
    setRunResult(null);
    setChatError("");
  }, []);

  const applyCatalogResult = useCallback((result: Awaited<ReturnType<typeof fetchAgentCatalog>>) => {
    if (result.ok && result.data?.length) {
      setAgents(result.data);
      setSelectedAgentKey(result.data[0].key);
      setRunResult(null);
      setChatError("");
      setCatalogNotice(
        `Loaded ${result.data.length} API-ready agent version(s) from ${result.endpoint}.`,
      );
      return;
    }

    setAgents(seedAgents);
    setSelectedAgentKey(seedAgents[0].key);
    setCatalogNotice("Using seed fallback catalog while the Agent API is unavailable.");
  }, []);

  const applyKnowledgeSourceResult = useCallback(
    (result: Awaited<ReturnType<typeof fetchKnowledgeSources>>) => {
      if (result.ok) {
        const sources = result.data ?? [];
        const sourceIds = new Set(sources.map((source) => source.id));

        setKnowledgeSources(sources);
        setSelectedKnowledgeSourceIds((currentIds) =>
          currentIds.filter((sourceId) => sourceIds.has(sourceId)),
        );
        setKnowledgeSourceNotice(
          sources.length > 0
            ? `Loaded ${sources.length} Knowledge API source(s) from ${result.endpoint}.`
            : "Knowledge API returned no sources.",
        );
        return;
      }

      setKnowledgeSources([]);
      setSelectedKnowledgeSourceIds([]);
      setKnowledgeSourceNotice(
        "Knowledge API source list unavailable; manual IDs are still available.",
      );
    },
    [],
  );

  const syncAgentCatalog = useCallback(async () => {
    setIsCatalogPending(true);
    try {
      applyCatalogResult(await fetchAgentCatalog());
    } finally {
      setIsCatalogPending(false);
    }
  }, [applyCatalogResult]);

  useEffect(() => {
    let isMounted = true;

    fetchAgentCatalog()
      .then((result) => {
        if (!isMounted) {
          return;
        }

        applyCatalogResult(result);
      })
      .finally(() => {
        if (isMounted) {
          setIsCatalogPending(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [applyCatalogResult]);

  useEffect(() => {
    let isMounted = true;

    fetchKnowledgeSources()
      .then((result) => {
        if (!isMounted) {
          return;
        }

        applyKnowledgeSourceResult(result);
      })
      .finally(() => {
        if (isMounted) {
          setIsKnowledgeSourcePending(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [applyKnowledgeSourceResult]);

  function handleAgentSelect(agentKey: string) {
    setSelectedAgentKey(agentKey);
    setRunResult(null);
    setChatError("");
    setLifecycleError("");
  }

  function handleKnowledgeSourceToggle(sourceId: string) {
    setSelectedKnowledgeSourceIds((currentIds) =>
      currentIds.includes(sourceId)
        ? currentIds.filter((currentId) => currentId !== sourceId)
        : [...currentIds, sourceId],
    );
  }

  function handleCreateDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const name = draftName.trim();
    const purpose = draftPurpose.trim();
    const ownerDepartment = draftOwner.trim();
    const knowledgeSourceIds = draftKnowledgeIds;

    if (!name || !purpose || !ownerDepartment) {
      setLifecycleError("Enter a draft name, purpose, and owner department before creating v1.");
      return;
    }

    setLifecycleError("");
    setLifecycleNotice("Creating draft agent and v1 version...");
    startLifecycleTransition(async () => {
      const result = await createDraftAgentWithVersion({
        name,
        purpose,
        ownerDepartment,
        knowledgeSourceIds,
      });

      if (result.ok && result.data) {
        upsertAgentOption(result.data);
        setLifecycleNotice(
          `Created ${result.data.name} ${result.data.version} with ${result.data.knowledge}.`,
        );
        return;
      }

      setLifecycleError(`Draft creation failed: ${result.error ?? "Agent API request failed."}`);
    });
  }

  function handleLifecycleAction(action: "validate" | "publish") {
    const agentVersionId = selectedAgent.agentVersionId;

    if (selectedAgent.source !== "api" || !agentVersionId) {
      setLifecycleError("Select an API-backed version before changing lifecycle state.");
      return;
    }

    setLifecycleError("");
    setLifecycleNotice(`${action === "validate" ? "Validating" : "Publishing"} ${selectedAgent.name}...`);
    startLifecycleTransition(async () => {
      const result =
        action === "validate"
          ? await validateAgentVersion({
              agentId: selectedAgent.id,
              agentName: selectedAgent.name,
              owner: selectedAgent.owner,
              agentVersionId,
              reason: validationReason.trim() || "Agent Studio validation",
            })
          : await publishAgentVersion({
              agentId: selectedAgent.id,
              agentName: selectedAgent.name,
              owner: selectedAgent.owner,
              agentVersionId,
              reason: publishReason.trim() || "Agent Studio publish",
            });

      if (result.ok && result.data) {
        upsertAgentOption(result.data);
        setLifecycleNotice(
          `${result.data.name} ${result.data.version} is now ${result.data.status.toLowerCase()}.`,
        );
        return;
      }

      setLifecycleError(
        `${action === "validate" ? "Validation" : "Publish"} failed: ${
          result.error ?? "Agent API request failed."
        }`,
      );
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canTestSelectedAgent) {
      setChatError("Only published agent versions can be tested from this surface.");
      return;
    }

    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setChatError("Enter a message before starting a test run.");
      return;
    }

    setChatError("");
    startChatTransition(async () => {
      const result = await submitAgentRun({
        agentId: selectedAgent.id,
        agentName: selectedAgent.name,
        agentVersionId: selectedAgent.agentVersionId,
        question: trimmedQuestion,
        knowledge: selectedAgent.knowledge,
        knowledgeSourceIds: selectedAgent.knowledgeSourceIds,
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
          <span className="badge neutral">Draft to publish</span>
        </div>
      </div>

      <section className="nextAction">
        <div>
          <span className="badge warn">Release blocker</span>
          <strong>{selectedAgent.next} is required before the pilot version is release-ready.</strong>
        </div>
        <span className="badge neutral">Budget: {selectedAgent.modelRoute}</span>
      </section>

      <section className="panel testChatPanel" aria-labelledby="lifecycle-heading">
        <div className="panelHeader">
          <div>
            <h2 id="lifecycle-heading">Lifecycle workflow</h2>
            <p>Draft creation and release gates for API-backed agent versions.</p>
          </div>
          <span className={`badge ${selectedAgent.source === "api" ? selectedAgent.tone : "warn"}`}>
            {selectedAgent.source === "api" ? selectedAgent.status : "Seed selected"}
          </span>
        </div>

        <div className="testChatGrid">
          <form className="testChatForm" onSubmit={handleCreateDraft}>
            <div className="fieldGrid">
              <label>
                Agent name
                <input
                  disabled={isLifecyclePending}
                  onChange={(event) => setDraftName(event.target.value)}
                  value={draftName}
                />
              </label>
              <label>
                Owner department
                <input
                  disabled={isLifecyclePending}
                  onChange={(event) => setDraftOwner(event.target.value)}
                  value={draftOwner}
                />
              </label>
            </div>
            <label>
              Purpose
              <textarea
                disabled={isLifecyclePending}
                onChange={(event) => setDraftPurpose(event.target.value)}
                value={draftPurpose}
              />
            </label>
            <div className="documentList" aria-labelledby="knowledge-source-picker-label">
              <div className="buttonRow">
                <strong id="knowledge-source-picker-label">Knowledge sources</strong>
                <span className={`badge ${knowledgeSources.length > 0 ? "neutral" : "warn"}`}>
                  {isKnowledgeSourcePending
                    ? "Syncing"
                    : `${draftKnowledgeIds.length} selected`}
                </span>
              </div>
              {knowledgeSources.map((source) => (
                <label className="documentRow" key={source.id}>
                  <input
                    checked={selectedKnowledgeSourceIds.includes(source.id)}
                    disabled={isLifecyclePending}
                    onChange={() => handleKnowledgeSourceToggle(source.id)}
                    type="checkbox"
                  />
                  <span className="documentMain">
                    <strong>{source.name}</strong>
                    <small>
                      {source.id} / {source.owner} / {source.confidentiality}
                    </small>
                  </span>
                  <span className={`badge ${source.status === "Ready" ? "neutral" : "warn"}`}>
                    {source.status}
                  </span>
                </label>
              ))}
              <p className="formNotice">{knowledgeSourceNotice}</p>
            </div>
            <label>
              Knowledge source IDs
              <input
                disabled={isLifecyclePending}
                onChange={(event) => setDraftKnowledgeSourceIds(event.target.value)}
                placeholder="Advanced: ks_policy, ks_security"
                value={draftKnowledgeSourceIds}
              />
            </label>
            <button className="button" disabled={isLifecyclePending} type="submit">
              {isLifecyclePending ? "Working..." : "Create draft + v1"}
            </button>
          </form>

          <div className="testChatResult" aria-live="polite">
            <dl className="detailGrid compact">
              <div>
                <dt>Selected version</dt>
                <dd>
                  {selectedAgent.name} / {selectedAgent.version}
                </dd>
              </div>
              <div>
                <dt>API version ID</dt>
                <dd>{selectedAgent.agentVersionId ?? "Seed fallback"}</dd>
              </div>
              <div>
                <dt>Lifecycle</dt>
                <dd>{selectedAgent.status}</dd>
              </div>
            </dl>

            <div className="buttonRow">
              {canValidateSelectedAgent ? (
                <label>
                  Validation reason
                  <input
                    disabled={isLifecyclePending}
                    onChange={(event) => setValidationReason(event.target.value)}
                    value={validationReason}
                  />
                </label>
              ) : null}
              {canPublishSelectedAgent ? (
                <label>
                  Publish reason
                  <input
                    disabled={isLifecyclePending}
                    onChange={(event) => setPublishReason(event.target.value)}
                    value={publishReason}
                  />
                </label>
              ) : null}
            </div>
            <div className="buttonRow">
              {canValidateSelectedAgent ? (
                <button
                  className="button secondary"
                  disabled={isLifecyclePending}
                  onClick={() => handleLifecycleAction("validate")}
                  type="button"
                >
                  Confirm validate
                </button>
              ) : null}
              {canPublishSelectedAgent ? (
                <button
                  className="button"
                  disabled={isLifecyclePending}
                  onClick={() => handleLifecycleAction("publish")}
                  type="button"
                >
                  Confirm publish
                </button>
              ) : null}
            </div>
            {lifecycleError ? (
              <p className="formNotice danger">{lifecycleError}</p>
            ) : (
              <p className="formNotice">{lifecycleNotice}</p>
            )}
          </div>
        </div>
      </section>

      <div className="agentWorkbench">
        <section className="panel agentListPanel">
          <div className="panelHeader">
            <div>
              <h2>Agent versions</h2>
              <p>Current pilot inventory and readiness state.</p>
            </div>
            <div className="buttonRow">
              <span className={`badge ${isCatalogPending || selectedAgent.source === "api" ? "neutral" : "warn"}`}>
                {isCatalogPending
                  ? "Syncing API"
                  : selectedAgent.source === "api"
                    ? "API catalog"
                    : "Seed fallback"}
              </span>
              <button className="button secondary" disabled={isCatalogPending} onClick={syncAgentCatalog} type="button">
                Sync API
              </button>
            </div>
          </div>
          <p className="formNotice">{catalogNotice}</p>
          <div className="agentRows">
            {agents.map((agent) => (
              <button
                aria-pressed={agent.key === selectedAgent.key}
                className="agentRow"
                key={agent.key}
                onClick={() => handleAgentSelect(agent.key)}
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
            <p>Send a test run against the selected published agent version.</p>
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
                disabled={!canTestSelectedAgent || isChatPending}
                onChange={(event) => setQuestion(event.target.value)}
                value={question}
              />
            </label>
            <div className="buttonRow">
              <button className="button" disabled={!canTestSelectedAgent || isChatPending} type="submit">
                {isChatPending ? "Running..." : "Send test"}
              </button>
              <button
                className="button secondary"
                disabled={!canTestSelectedAgent || isChatPending}
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

function mergeKnowledgeSourceIds(selectedIds: string[], manualValue: string) {
  return Array.from(
    new Set(
      selectedIds.concat(
        manualValue
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      ),
    ),
  );
}
