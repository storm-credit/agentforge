"use client";
import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";
import {
  archiveDocument,
  createSource,
  indexDocument,
  listDocuments,
  listSources,
  registerDocument,
  sha256Hex,
  type DocumentSummary,
  type KnowledgeSource,
  updateDocumentAcl,
  uploadDocument,
} from "../lib/api";
import { useDemoRole } from "../lib/useDemoRole";

export default function KnowledgePage() {
  // UX only: the server enforces RBAC on these mutations regardless (403 for
  // non-privileged roles) — we just hide controls the current demo role can't use.
  const { role, isPrivileged } = useDemoRole();
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);

  const [sourceMode, setSourceMode] = useState<"existing" | "new">("existing");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [newSourceName, setNewSourceName] = useState("");

  const [title, setTitle] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState("");
  const [content, setContent] = useState("");
  const [confidentiality, setConfidentiality] = useState("internal");
  const [accessGroups, setAccessGroups] = useState("all-employees");

  const [createdSourceId, setCreatedSourceId] = useState<string | null>(null);
  const [createdDocId, setCreatedDocId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");

  // ACL editing (per-document)
  const [aclEdit, setAclEdit] = useState<
    { docId: string; groups: string; level: string; reason: string } | null
  >(null);
  const [aclBusy, setAclBusy] = useState(false);

  // Archive (soft-delete, per-document)
  const [archiveEdit, setArchiveEdit] = useState<{ docId: string; reason: string } | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);

  function refresh() {
    listSources().then(setSources).catch(() => {});
    listDocuments().then(setDocuments).catch(() => {});
  }
  useEffect(refresh, []);

  function startAclEdit(d: DocumentSummary) {
    setAclEdit({
      docId: d.id,
      groups: (d.access_groups ?? []).join(", "),
      level: d.confidentiality_level,
      reason: "",
    });
  }

  async function saveAcl() {
    if (!aclEdit) return;
    setAclBusy(true);
    setError("");
    try {
      const groups = aclEdit.groups.split(",").map((g) => g.trim()).filter(Boolean);
      await updateDocumentAcl(aclEdit.docId, {
        access_groups: groups,
        confidentiality_level: aclEdit.level,
        reason: aclEdit.reason.trim() || "ACL updated via Knowledge UI",
      });
      setAclEdit(null);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setAclBusy(false);
    }
  }

  function startArchive(d: DocumentSummary) {
    setArchiveEdit({ docId: d.id, reason: "" });
  }

  async function confirmArchive() {
    if (!archiveEdit) return;
    setArchiveBusy(true);
    setError("");
    try {
      await archiveDocument(archiveEdit.docId, archiveEdit.reason.trim() || "archived via Knowledge UI");
      setArchiveEdit(null);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setArchiveBusy(false);
    }
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setSelectedFile(f);
    setFileName(f.name);
    if (isBinaryUpload(f.name)) {
      setContent("");
    } else {
      const reader = new FileReader();
      reader.onload = () => setContent(String(reader.result ?? ""));
      reader.readAsText(f);
    }
    if (!title) setTitle(f.name.replace(/\.(txt|md|pdf|docx)$/i, ""));
  }

  const sourceReady = sourceMode === "existing" ? !!selectedSourceId : newSourceName.trim().length > 0;
  const hasDocumentContent = selectedFile
    ? isBinaryUpload(selectedFile.name) || content.trim().length > 0
    : content.trim().length > 0;
  const canSubmit = sourceReady && title.trim().length > 0 && hasDocumentContent && !busy;

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

      const groups = accessGroups.split(",").map((g) => g.trim()).filter(Boolean);
      const normalizedGroups = groups.length ? groups : ["all-employees"];

      if (selectedFile && isBinaryUpload(selectedFile.name)) {
        const uploaded = await uploadDocument({
          knowledge_source_id: sid,
          title,
          file: selectedFile,
          confidentiality_level: confidentiality,
          access_groups: normalizedGroups,
        });
        setCreatedDocId(uploaded.document.id);
        const job = uploaded.index_job;
        if (job.status === "succeeded") {
          setResult(`색인됨 ${job.chunk_count}청크 — 이제 에이전트 빌더에서 이 소스를 연결할 수 있어요.`);
          refresh();
        } else {
          setError(`색인 실패: ${job.error_code ?? ""} ${job.error_message ?? ""}`);
        }
        return;
      }

      let did = createdDocId;
      if (!did) {
        const mime = fileName.toLowerCase().endsWith(".md") ? "text/markdown" : "text/plain";
        const checksum = "sha256-" + (await sha256Hex(content));
        did = (await registerDocument({
          knowledge_source_id: sid,
          title,
          mime_type: mime,
          confidentiality_level: confidentiality,
          access_groups: normalizedGroups,
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
    setTitle(""); setSelectedFile(null); setFileName(""); setContent("");
    setCreatedDocId(null); setResult(""); setError("");
  }

  return (
    <section className="page">
      <div>
        <p className="eyebrow">RAG data</p>
        <h1>Knowledge</h1>
        <p>지식소스에 TXT/MD/PDF/DOCX 문서를 추가하면 임베딩 색인되어 에이전트가 답할 수 있습니다.</p>
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
              <select data-testid="source-select" value={selectedSourceId} onChange={(e) => setSelectedSourceId(e.target.value)}>
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
          <input type="file" accept=".txt,.md,.pdf,.docx" onChange={onFile} style={{ marginBottom: "8px" }} />
          <textarea className="field" rows={6} placeholder="본문 (.txt/.md 파일 선택 시 자동 채움, PDF/DOCX는 서버에서 추출)"
            value={content} onChange={(e) => setContent(e.target.value)} />

          <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
            <select data-testid="confidentiality-select" value={confidentiality} onChange={(e) => setConfidentiality(e.target.value)}>
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
          {!isPrivileged && (
            <p data-testid="role-restricted-note" style={{ fontSize: "12px", color: "#64748b" }}>
              데모 역할 &quot;{role}&quot; — 관리 작업(ACL 편집/보관)은 숨겨지며, 목록은 이
              역할의 열람 권한(clearance/ACL) 범위만 서버에서 필터되어 표시됩니다.
            </p>
          )}
          {sources.map((s) => (
            <div key={s.id} style={{ marginBottom: "10px" }}>
              <strong>{s.name}</strong>
              <ul style={{ margin: "4px 0", paddingLeft: "18px", listStyle: "none" }}>
                {documents.filter((d) => d.knowledge_source_id === s.id).map((d) => (
                  <li key={d.id} data-testid="doc-row" style={{ fontSize: "14px", marginBottom: "6px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                      {d.title} <span className="badge">{d.status}</span>
                      <span className="badge warn" data-testid="doc-confidentiality">{d.confidentiality_level}</span>
                      <span style={{ fontSize: "12px", color: "#64748b" }} data-testid="doc-groups">
                        {(d.access_groups ?? []).join(", ")}
                      </span>
                      {isPrivileged && (
                        <>
                          <button className="button secondary" data-testid="acl-edit"
                            style={{ padding: "2px 8px", fontSize: "12px" }}
                            onClick={() => startAclEdit(d)}>ACL 편집</button>
                          <button className="button secondary" data-testid="archive-doc"
                            style={{ padding: "2px 8px", fontSize: "12px" }}
                            onClick={() => startArchive(d)}>보관</button>
                        </>
                      )}
                    </div>
                    {archiveEdit?.docId === d.id && (
                      <div className="card" data-testid="archive-form" style={{ marginTop: "6px", padding: "10px" }}>
                        <input className="field" data-testid="archive-reason" placeholder="보관 사유 (감사 기록)"
                          value={archiveEdit.reason}
                          onChange={(e) => setArchiveEdit({ ...archiveEdit, reason: e.target.value })} />
                        <div className="buttonRow">
                          <button className="button" data-testid="archive-confirm" disabled={archiveBusy}
                            onClick={confirmArchive}>
                            {archiveBusy ? "보관 중…" : "보관 확정"}
                          </button>
                          <button className="button secondary" onClick={() => setArchiveEdit(null)}>취소</button>
                        </div>
                      </div>
                    )}
                    {aclEdit?.docId === d.id && (
                      <div className="card" data-testid="acl-form" style={{ marginTop: "6px", padding: "10px" }}>
                        <select value={aclEdit.level}
                          onChange={(e) => setAclEdit({ ...aclEdit, level: e.target.value })}>
                          <option value="public">공개</option>
                          <option value="internal">내부</option>
                          <option value="restricted">제한</option>
                        </select>
                        <input className="field" data-testid="acl-groups" placeholder="접근그룹(쉼표)"
                          value={aclEdit.groups}
                          onChange={(e) => setAclEdit({ ...aclEdit, groups: e.target.value })} />
                        <input className="field" data-testid="acl-reason" placeholder="변경 사유 (감사 기록)"
                          value={aclEdit.reason}
                          onChange={(e) => setAclEdit({ ...aclEdit, reason: e.target.value })} />
                        <div className="buttonRow">
                          <button className="button" data-testid="acl-save" disabled={aclBusy} onClick={saveAcl}>
                            {aclBusy ? "저장 중…" : "저장"}
                          </button>
                          <button className="button secondary" onClick={() => setAclEdit(null)}>취소</button>
                        </div>
                      </div>
                    )}
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

function isBinaryUpload(name: string) {
  return /\.(pdf|docx)$/i.test(name);
}
