"use client";
import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import {
  createSource,
  indexDocument,
  listDocuments,
  listSources,
  registerDocument,
  sha256Hex,
  type DocumentSummary,
  type KnowledgeSource,
} from "../lib/api";

export default function KnowledgePage() {
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);

  const [sourceMode, setSourceMode] = useState<"existing" | "new">("existing");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [newSourceName, setNewSourceName] = useState("");

  const [title, setTitle] = useState("");
  const [fileName, setFileName] = useState("");
  const [content, setContent] = useState("");
  const [confidentiality, setConfidentiality] = useState("internal");
  const [accessGroups, setAccessGroups] = useState("all-employees");

  const [createdSourceId, setCreatedSourceId] = useState<string | null>(null);
  const [createdDocId, setCreatedDocId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");

  function refresh() {
    listSources().then(setSources).catch(() => {});
    listDocuments().then(setDocuments).catch(() => {});
  }
  useEffect(refresh, []);

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileName(f.name);
    const reader = new FileReader();
    reader.onload = () => setContent(String(reader.result ?? ""));
    reader.readAsText(f);
    if (!title) setTitle(f.name.replace(/\.(txt|md)$/i, ""));
  }

  const sourceReady = sourceMode === "existing" ? !!selectedSourceId : newSourceName.trim().length > 0;
  const canSubmit = sourceReady && title.trim().length > 0 && content.trim().length > 0 && !busy;

  async function onSubmit() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      let sid = sourceMode === "existing" ? selectedSourceId : createdSourceId;
      if (sourceMode === "new" && !sid) {
        sid = (await createSource({ name: newSourceName, owner_department: "Operations" })).id;
        setCreatedSourceId(sid);
      }
      if (!sid) throw new Error("지식소스를 선택하거나 새로 만드세요.");

      let did = createdDocId;
      if (!did) {
        const mime = fileName.toLowerCase().endsWith(".md") ? "text/markdown" : "text/plain";
        const checksum = "sha256-" + (await sha256Hex(content));
        const groups = accessGroups.split(",").map((g) => g.trim()).filter(Boolean);
        did = (await registerDocument({
          knowledge_source_id: sid,
          title,
          mime_type: mime,
          confidentiality_level: confidentiality,
          access_groups: groups.length ? groups : ["all-employees"],
          object_uri: "inline://" + (fileName || title),
          checksum,
        })).id;
        setCreatedDocId(did);
      }

      const job = await indexDocument({ document_id: did, source_text: content });
      if (job.status === "succeeded") {
        setResult(`색인됨 ${job.chunk_count}청크 — 이제 에이전트 빌더에서 이 소스를 연결할 수 있어요.`);
        refresh();
      } else {
        setError(`색인 실패: ${job.error_code ?? ""} ${job.error_message ?? ""}`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function addAnother() {
    setTitle(""); setFileName(""); setContent("");
    setCreatedDocId(null); setResult(""); setError("");
  }

  return (
    <section className="page">
      <div>
        <p className="eyebrow">RAG data</p>
        <h1>Knowledge</h1>
        <p>지식소스에 TXT/MD 문서를 추가하면 임베딩 색인되어 에이전트가 답할 수 있습니다.</p>
      </div>

      <div style={{ display: "flex", gap: "20px", flexWrap: "wrap", alignItems: "flex-start" }}>
        <div className="panel" style={{ flex: "1 1 380px" }}>
          <h3>문서 추가</h3>

          <p className="label">지식소스</p>
          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <select value={sourceMode} onChange={(e) => setSourceMode(e.target.value as "existing" | "new")}>
              <option value="existing">기존 선택</option>
              <option value="new">새로 만들기</option>
            </select>
            {sourceMode === "existing" ? (
              <select value={selectedSourceId} onChange={(e) => setSelectedSourceId(e.target.value)}>
                <option value="">소스 선택…</option>
                {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            ) : (
              <input className="field" placeholder="새 소스 이름" value={newSourceName}
                onChange={(e) => setNewSourceName(e.target.value)} style={{ marginBottom: 0 }} />
            )}
          </div>

          <input className="field" placeholder="문서 제목" value={title}
            onChange={(e) => setTitle(e.target.value)} />
          <input type="file" accept=".txt,.md" onChange={onFile} style={{ marginBottom: "8px" }} />
          <textarea className="field" rows={6} placeholder="본문 (.txt/.md 파일 선택 시 자동 채움, 또는 직접 붙여넣기)"
            value={content} onChange={(e) => setContent(e.target.value)} />

          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <select value={confidentiality} onChange={(e) => setConfidentiality(e.target.value)}>
              <option value="public">공개</option>
              <option value="internal">내부</option>
              <option value="restricted">제한</option>
            </select>
            <input className="field" placeholder="접근그룹(쉼표)" value={accessGroups}
              onChange={(e) => setAccessGroups(e.target.value)} style={{ marginBottom: 0 }} />
          </div>

          <button className="button" data-testid="ingest" onClick={onSubmit} disabled={!canSubmit}>
            {busy ? "색인 중…" : "추가 & 색인"}
          </button>
          {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
          {result && (
            <div>
              <p style={{ color: "#15803d" }}>✓ {result}</p>
              <button className="button" onClick={addAnother}>다른 문서 추가</button>
            </div>
          )}
        </div>

        <div className="panel" style={{ flex: "1 1 320px" }}>
          <h3>지식소스 / 문서</h3>
          {sources.map((s) => (
            <div key={s.id} style={{ marginBottom: "10px" }}>
              <strong>{s.name}</strong>
              <ul style={{ margin: "4px 0", paddingLeft: "18px" }}>
                {documents.filter((d) => d.knowledge_source_id === s.id).map((d) => (
                  <li key={d.id} style={{ fontSize: "14px" }}>
                    {d.title} <span className="badge">{d.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {sources.length === 0 && <p>아직 지식소스가 없습니다.</p>}
        </div>
      </div>
    </section>
  );
}
