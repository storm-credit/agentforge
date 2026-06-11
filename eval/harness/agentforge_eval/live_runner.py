from __future__ import annotations

import json
from pathlib import Path

import httpx

from agentforge_eval.live_scorer import aggregate, score_case

_OPERATOR = {
    "X-Agent-Forge-User": "eval-operator",
    "X-Agent-Forge-Department": "Operations",
    "X-Agent-Forge-Roles": "admin",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
}


def _principal_headers(p: dict) -> dict:
    return {
        "X-Agent-Forge-User": "eval-" + p["department"],
        "X-Agent-Forge-Department": p["department"],
        "X-Agent-Forge-Roles": ",".join(p.get("roles", [])) or "employee",
        "X-Agent-Forge-Groups": ",".join(p.get("groups", [])) or "all-employees",
        "X-Agent-Forge-Clearance": p.get("clearance", "internal"),
    }


def run_live_eval(corpus_path: Path, base_url: str, prefix: str) -> dict:
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    with httpx.Client(base_url=base_url, timeout=120.0) as client:
        doc_id_map: dict[str, str] = {}
        source_ids: list[str] = []
        for doc in corpus["documents"]:
            src = client.post(
                "/knowledge/sources",
                headers=_OPERATOR,
                json={"name": f"{prefix}:{doc['doc_id']}", "owner_department": "Operations"},
            )
            src.raise_for_status()
            source_id = src.json()["id"]
            source_ids.append(source_id)

            reg = client.post(
                "/knowledge/documents",
                headers=_OPERATOR,
                json={
                    "knowledge_source_id": source_id,
                    "title": doc["title"],
                    "object_uri": f"eval://{prefix}/{doc['doc_id']}.md",
                    "checksum": f"sha256-{prefix}-{doc['doc_id']}",
                    "mime_type": "text/markdown",
                    "confidentiality_level": doc["confidentiality_level"],
                    "access_groups": doc["access_groups"],
                    "status": "registered",
                },
            )
            reg.raise_for_status()
            document_id = reg.json()["id"]
            doc_id_map[doc["doc_id"]] = document_id

            job = client.post(
                f"/knowledge/documents/{document_id}/index-jobs",
                headers=_OPERATOR,
                json={
                    "parser_profile": "default-txt-md",
                    "embedding_model": "bge-m3",
                    "source_text": doc["body"],
                },
            )
            job.raise_for_status()
            if job.json().get("status") != "succeeded":
                raise RuntimeError(f"index failed for {doc['doc_id']}: {job.json()}")

        agent = client.post(
            "/agents",
            headers=_OPERATOR,
            json={
                "name": f"{prefix} eval agent",
                "purpose": "live eval",
                "owner_department": "Operations",
                "status": "draft",
            },
        )
        agent.raise_for_status()
        agent_id = agent.json()["id"]

        ver = client.post(
            "/agents/versions",
            headers=_OPERATOR,
            json={
                "agent_id": agent_id,
                "version": 1,
                "status": "draft",
                "config": {"citation_required": True, "knowledge_source_ids": source_ids},
            },
        )
        ver.raise_for_status()
        version_id = ver.json()["id"]
        client.post(
            f"/agents/versions/{version_id}/publish", headers=_OPERATOR, json={"reason": "eval"}
        ).raise_for_status()

        scores = []
        top_scores: dict[str, float] = {}
        for case in corpus["cases"]:
            run = client.post(
                "/runs",
                headers=_principal_headers(case["principal"]),
                json={"agent_id": agent_id, "input": {"message": case["question"]}, "language": "auto"},
            )
            run.raise_for_status()
            rj = run.json()
            hits = client.get(f"/runs/{rj['id']}/retrieval-hits").json()
            top_scores[case["case_id"]] = max(
                (h.get("score_vector") or 0.0 for h in hits), default=0.0
            )
            run_result = {
                "answer": rj.get("answer", ""),
                "citations": rj.get("citations", []),
                "hit_document_ids": [h.get("document_id") for h in hits],
            }
            scores.append(score_case(case, run_result, doc_id_map))

    report = aggregate(scores)
    for case_row in report["cases"]:
        case_row["top_score"] = round(top_scores.get(case_row["case_id"], 0.0), 4)
    report["corpus_id"] = corpus["corpus_id"]
    return report
