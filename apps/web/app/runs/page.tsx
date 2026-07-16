"use client";
import { useEffect, useState } from "react";
import {
  getRunHits,
  getRunSteps,
  listRuns,
  type RetrievalHit,
  type RunStep,
  type RunSummary,
} from "../lib/api";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<RunSummary | null>(null);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [hits, setHits] = useState<RetrievalHit[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listRuns()
      .then((rs) => { setRuns(rs); if (rs.length) setSelected(rs[0]); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    getRunSteps(selected.id).then(setSteps).catch(() => setSteps([]));
    getRunHits(selected.id).then(setHits).catch(() => setHits([]));
  }, [selected]);

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Governance</p>
        <h1>Runs</h1>
        <p>실행 단계 트레이스, 검색 근거(본문·점수·권한), 거부/강등 사유를 확인합니다.</p>
      </div>

      {error && <p className="error-text">{error}</p>}
      {!error && !loading && runs.length === 0 && (
        <p>아직 실행 내역이 없습니다. /chat이나 빌더 테스트에서 질문해 보세요.</p>
      )}

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", alignItems: "flex-start" }}>
        <div className="panel" style={{ flex: "1 1 280px", maxWidth: "340px" }}>
          <h3>최근 실행</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {runs.map((r) => (
              <li key={r.id} style={{ marginBottom: "6px" }}>
                <button
                  onClick={() => setSelected(r)}
                  className={`listButton${selected?.id === r.id ? " selected" : ""}`}
                >
                  <div style={{ fontSize: "var(--text-base)" }}>{r.input?.message ?? "(질문 없음)"}</div>
                  <div className="meta">
                    <span className="badge">{r.status}</span> · {r.latency_ms}ms
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel" style={{ flex: "2 1 420px" }}>
          {!selected ? (
            <p>왼쪽에서 실행을 선택하세요.</p>
          ) : (
            <>
              <h3>답변</h3>
              {renderGuardrailSignals(selected, steps)}
              <p data-testid="run-answer">{selected.answer}</p>
              {selected.citations?.length > 0 && (
                <ul>
                  {selected.citations.map((c, i) => (
                    <li key={i} style={{ fontSize: "var(--text-base)" }}>{c.title} — {c.citation_locator}</li>
                  ))}
                </ul>
              )}

              <h3 style={{ marginTop: "var(--space-4)" }}>단계 타임라인</h3>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {steps.map((s) => (
                  <li key={s.step_order} style={{ marginBottom: "var(--space-2)" }}>
                    <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                      <strong>{s.step_order}. {s.step_type}</strong>
                      <span className={`badge ${s.status === "succeeded" ? "success" : "danger"}`}>
                        {s.status}
                      </span>
                      <span className="meta">{s.latency_ms}ms</span>
                    </div>
                    {s.error_message && <div className="error-text" style={{ fontSize: "var(--text-sm)" }}>{s.error_code}: {s.error_message}</div>}
                    <details>
                      <summary>입출력</summary>
                      <pre className="pre">
{JSON.stringify({ input: s.input_summary, output: s.output_summary }, null, 2)}
                      </pre>
                    </details>
                  </li>
                ))}
              </ul>

              <h3 style={{ marginTop: "var(--space-4)" }}>검색 근거 (hits)</h3>
              {hits.length === 0 && <p style={{ fontSize: "var(--text-base)" }}>검색 결과 없음(또는 권한 거부).</p>}
              {hits.map((h, i) => (
                <article key={i} className="card" style={{ marginBottom: "var(--space-2)" }}>
                  <div style={{ fontSize: "var(--text-sm)" }}>
                    #{h.rank_original} · {h.title} · score {h.score_vector}
                    {" "}{h.used_as_citation ? <span className="badge success">인용됨</span> : <span className="badge">미인용</span>}
                  </div>
                  {h.citation_locator && <div className="meta">{h.citation_locator}</div>}
                  {h.content && (
                    <details>
                      <summary>본문</summary>
                      <p style={{ fontSize: "var(--text-sm)", whiteSpace: "pre-wrap" }}>{h.content}</p>
                    </details>
                  )}
                </article>
              ))}

              {hits[0]?.acl_filter_snapshot && (
                <details style={{ marginTop: "var(--space-2)" }}>
                  <summary>ACL 필터 스냅샷</summary>
                  <pre className="pre">
{JSON.stringify(hits[0].acl_filter_snapshot, null, 2)}
                  </pre>
                </details>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function signalBadge(testId: string, label: string, ok: boolean) {
  return (
    <span data-testid={testId} className={`badge ${ok ? "success" : "warn"}`}>
      {label}
    </span>
  );
}

// Surfaces the guardrail signals already returned by listRuns()/getRunSteps() (PII masking,
// citation validation, confidence gate, grounding guard, reranker, answerability judge) as
// glanceable badges instead of leaving them buried in the raw step JSON <details> blocks.
function renderGuardrailSignals(run: RunSummary, steps: RunStep[]) {
  const guardrail = run.guardrail ?? {};
  const guardOutput = steps.find((s) => s.step_type === "guard_output")?.output_summary ?? {};
  const retriever = steps.find((s) => s.step_type === "retriever")?.output_summary ?? {};

  const piiMasked = Boolean(guardrail.pii_masked);
  const citationPass = Boolean(guardrail.citation_validation_pass);
  const confidenceTripped = Boolean(guardOutput.confidence_gate_tripped);
  const groundingTripped = Boolean(guardOutput.guard_tripped);
  const judgeName = String(guardOutput.judge ?? "none");
  const judgeRefused = Boolean(guardOutput.judge_refused);
  const rerankerName = String(retriever.reranker ?? "none");

  return (
    <div
      data-testid="guardrail-signals"
      style={{ display: "flex", gap: "6px", flexWrap: "wrap", margin: "6px 0 var(--space-3)" }}
    >
      {signalBadge("guardrail-pii", piiMasked ? "PII 마스킹 적용" : "PII 마스킹 미적용", !piiMasked)}
      {signalBadge("guardrail-citation", citationPass ? "인용 검증 통과" : "인용 검증 실패", citationPass)}
      {signalBadge("guardrail-confidence", confidenceTripped ? "신뢰도 게이트 차단" : "신뢰도 게이트 통과", !confidenceTripped)}
      {signalBadge("guardrail-grounding", groundingTripped ? "그라운딩 가드 차단" : "그라운딩 가드 통과", !groundingTripped)}
      {judgeName !== "none" &&
        signalBadge("guardrail-judge", `판정 모델(${judgeName}) ${judgeRefused ? "거부" : "통과"}`, !judgeRefused)}
      {rerankerName !== "none" && signalBadge("guardrail-reranker", `재정렬: ${rerankerName}`, true)}
    </div>
  );
}
