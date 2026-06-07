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

  useEffect(() => {
    listRuns()
      .then((rs) => { setRuns(rs); if (rs.length) setSelected(rs[0]); })
      .catch((e) => setError(String(e)));
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

      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      {!error && runs.length === 0 && (
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
                  style={{
                    width: "100%", textAlign: "left", cursor: "pointer", padding: "8px",
                    borderRadius: "6px", border: "1px solid var(--line,#cbd5e1)",
                    background: selected?.id === r.id ? "#eff6ff" : "transparent",
                  }}
                >
                  <div style={{ fontSize: "14px" }}>{r.input?.message ?? "(질문 없음)"}</div>
                  <div style={{ fontSize: "12px", color: "#64748b" }}>
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
              <p data-testid="run-answer">{selected.answer}</p>
              {selected.citations?.length > 0 && (
                <ul>
                  {selected.citations.map((c, i) => (
                    <li key={i} style={{ fontSize: "14px" }}>{c.title} — {c.citation_locator}</li>
                  ))}
                </ul>
              )}

              <h3 style={{ marginTop: "16px" }}>단계 타임라인</h3>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {steps.map((s) => (
                  <li key={s.step_order} style={{ marginBottom: "8px" }}>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <strong>{s.step_order}. {s.step_type}</strong>
                      <span className="badge" style={{ color: s.status === "succeeded" ? "#15803d" : "#b91c1c" }}>
                        {s.status}
                      </span>
                      <span style={{ fontSize: "12px", color: "#64748b" }}>{s.latency_ms}ms</span>
                    </div>
                    {s.error_message && <div style={{ color: "#b91c1c", fontSize: "13px" }}>{s.error_code}: {s.error_message}</div>}
                    <details>
                      <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer" }}>입출력</summary>
                      <pre style={{ fontSize: "12px", whiteSpace: "pre-wrap", background: "#f8fafc", padding: "8px", borderRadius: "6px" }}>
{JSON.stringify({ input: s.input_summary, output: s.output_summary }, null, 2)}
                      </pre>
                    </details>
                  </li>
                ))}
              </ul>

              <h3 style={{ marginTop: "16px" }}>검색 근거 (hits)</h3>
              {hits.length === 0 && <p style={{ fontSize: "14px", color: "#64748b" }}>검색 결과 없음(또는 권한 거부).</p>}
              {hits.map((h, i) => (
                <article key={i} className="card" style={{ marginBottom: "8px" }}>
                  <div style={{ fontSize: "13px" }}>
                    #{h.rank_original} · {h.title} · score {h.score_vector}
                    {" "}{h.used_as_citation ? <span className="badge">인용됨</span> : <span className="badge">미인용</span>}
                  </div>
                  {h.citation_locator && <div style={{ fontSize: "12px", color: "#64748b" }}>{h.citation_locator}</div>}
                  {h.content && (
                    <details>
                      <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer" }}>본문</summary>
                      <p style={{ fontSize: "13px", whiteSpace: "pre-wrap" }}>{h.content}</p>
                    </details>
                  )}
                </article>
              ))}

              {hits[0]?.acl_filter_snapshot && (
                <details style={{ marginTop: "8px" }}>
                  <summary style={{ fontSize: "12px", color: "#64748b", cursor: "pointer" }}>ACL 필터 스냅샷</summary>
                  <pre style={{ fontSize: "12px", whiteSpace: "pre-wrap", background: "#f8fafc", padding: "8px", borderRadius: "6px" }}>
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
