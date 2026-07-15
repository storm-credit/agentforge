"use client";
import { useEffect, useState } from "react";
import { listEvalRuns, type EvalRunSummary } from "../lib/api";

function pct(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

export default function EvalPage() {
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  function refresh() {
    setError("");
    setLoading(true);
    listEvalRuns({ limit: 50 })
      .then(setRuns)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }
  useEffect(refresh, []);

  return (
    <section className="page">
      <div>
        <p className="eyebrow">Quality gates</p>
        <h1>Evaluation</h1>
        <p>라이브 eval 하네스가 기록한 품질 이력입니다. (harness: AGENT_FORGE_EVAL_PERSIST=true)</p>
      </div>
      <section className="panel">
        <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Eval run history</h2>
          <button className="button secondary" onClick={refresh}>새로고침</button>
        </div>
        {error && <p className="error-text" data-testid="eval-error">{error}</p>}
        {!loading && !error && runs.length === 0 && (
          <p data-testid="eval-empty">
            기록된 eval run이 없습니다. 라이브 eval을 AGENT_FORGE_EVAL_PERSIST=true로 실행하면
            여기에 이력이 쌓입니다.
          </p>
        )}
        {runs.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table data-testid="eval-run-table" className="table">
              <thead>
                <tr>
                  <th>Corpus</th>
                  <th>Label</th>
                  <th>Recorded</th>
                  <th>Cases</th>
                  <th>Citation</th>
                  <th>Useful</th>
                  <th>Refusal</th>
                  <th>Faithfulness</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} data-testid="eval-run-row">
                    <td>
                      <span className="badge info">{r.corpus_id}</span>
                    </td>
                    <td>{r.label ?? "—"}</td>
                    <td style={{ color: "var(--text-muted)" }}>
                      {r.created_at.slice(0, 19).replace("T", " ")} · {r.created_by}
                    </td>
                    <td>{r.total ?? "—"}</td>
                    <td>{pct(r.citation_pct)}</td>
                    <td>{pct(r.useful_answer_pct)}</td>
                    <td>{pct(r.refusal_discipline_pct)}</td>
                    <td>
                      {pct(r.faithfulness_pct)}
                      {r.faithfulness_threshold != null && (
                        <span style={{ color: "var(--text-muted)" }}> (≥{r.faithfulness_threshold})</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
