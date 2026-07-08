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
        <div style={{ display: "flex", gap: "8px", marginBottom: "10px", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Eval run history</h2>
          <button className="button secondary" onClick={refresh}>새로고침</button>
        </div>
        {error && <p style={{ color: "#b91c1c" }} data-testid="eval-error">{error}</p>}
        {!loading && !error && runs.length === 0 && (
          <p data-testid="eval-empty">
            기록된 eval run이 없습니다. 라이브 eval을 AGENT_FORGE_EVAL_PERSIST=true로 실행하면
            여기에 이력이 쌓입니다.
          </p>
        )}
        {runs.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table data-testid="eval-run-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "#64748b" }}>
                  <th style={{ padding: "6px 8px" }}>Corpus</th>
                  <th style={{ padding: "6px 8px" }}>Label</th>
                  <th style={{ padding: "6px 8px" }}>Recorded</th>
                  <th style={{ padding: "6px 8px" }}>Cases</th>
                  <th style={{ padding: "6px 8px" }}>Citation</th>
                  <th style={{ padding: "6px 8px" }}>Useful</th>
                  <th style={{ padding: "6px 8px" }}>Refusal</th>
                  <th style={{ padding: "6px 8px" }}>Faithfulness</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} data-testid="eval-run-row" style={{ borderTop: "1px solid #e2e8f0" }}>
                    <td style={{ padding: "6px 8px" }}>
                      <span className="badge">{r.corpus_id}</span>
                    </td>
                    <td style={{ padding: "6px 8px" }}>{r.label ?? "—"}</td>
                    <td style={{ padding: "6px 8px", color: "#64748b" }}>
                      {r.created_at.slice(0, 19).replace("T", " ")} · {r.created_by}
                    </td>
                    <td style={{ padding: "6px 8px" }}>{r.total ?? "—"}</td>
                    <td style={{ padding: "6px 8px" }}>{pct(r.citation_pct)}</td>
                    <td style={{ padding: "6px 8px" }}>{pct(r.useful_answer_pct)}</td>
                    <td style={{ padding: "6px 8px" }}>{pct(r.refusal_discipline_pct)}</td>
                    <td style={{ padding: "6px 8px" }}>
                      {pct(r.faithfulness_pct)}
                      {r.faithfulness_threshold != null && (
                        <span style={{ color: "#64748b" }}> (≥{r.faithfulness_threshold})</span>
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
